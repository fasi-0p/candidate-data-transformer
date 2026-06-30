"""Tests for the resume parser (pure text) and cross-source merge."""

from datetime import date
from pathlib import Path

import pytest

from src.extractors.resume_extractor import parse_resume_text
from src.pipeline import Source, run

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
RESUME_PDF = SAMPLES / "resume_jane.pdf"
CSV = str(SAMPLES / "candidates.csv")

RESUME_TEXT = """\
Jane Doe
Senior Machine Learning Engineer
Bengaluru, India
jane.doe@gmail.com  |  +91 98765 43210
github.com/janedoe  |  https://linkedin.com/in/janedoe

Summary
ML engineer with 7 years of experience.

Skills
Machine Learning, Python, TensorFlow, NLP

Experience
Lead ML Engineer, Acme AI (2021-03 to Present)
"""


def values(rec, field):
    raw = rec.fields[field]
    items = raw if isinstance(raw, list) else [raw]
    return [x.value for x in items]


def test_parser_extracts_core_fields():
    # Pin "today" so the open-ended "2021-03 to Present" role sums deterministically:
    # Mar 2021 .. Feb 2026 inclusive = 60 months = 5 years.
    rec = parse_resume_text(RESUME_TEXT, today=date(2026, 2, 1))
    assert rec.source == "Resume"
    assert values(rec, "full_name") == ["Jane Doe"]
    assert values(rec, "headline") == ["Senior Machine Learning Engineer"]
    assert values(rec, "emails") == ["jane.doe@gmail.com"]
    assert values(rec, "location") == ["Bengaluru, India"]
    assert "Python" in values(rec, "skills")
    # Summed from the Experience section's date range, not the "7 years" phrase.
    assert values(rec, "years_experience") == ["5"]


def test_years_summed_across_roles_excluding_education():
    text = (
        "Work Experience\n"
        "Senior Engineer, Foo  Jan 2020 - Present\n"
        "Engineer, Bar  Jun 2016 - Dec 2019\n"
        "Education\n"
        "B.Tech, IIT  2012 - 2016\n"  # a degree range must NOT count as tenure
    )
    rec = parse_resume_text(text, today=date(2026, 6, 1))
    # (Jan 2020..Jun 2026 = 78) + (Jun 2016..Dec 2019 = 43) = 121 months = 10.1 yrs.
    assert values(rec, "years_experience") == ["10.1"]


def test_years_merges_overlapping_roles():
    text = ("Experience\n"
            "Role A 2020-01 to 2020-12\n"
            "Role B 2020-06 to 2021-06\n")  # concurrent -> union, not 24 months
    rec = parse_resume_text(text, today=date(2026, 1, 1))
    assert values(rec, "years_experience") == ["1.5"]  # 18 months


def test_years_falls_back_to_explicit_phrase_when_no_ranges():
    text = ("Summary\n"
            "Backend engineer with 8 years of experience.\n"
            "Experience\n"
            "Built large-scale systems.\n")  # no parseable date ranges
    rec = parse_resume_text(text, today=date(2026, 1, 1))
    assert values(rec, "years_experience") == ["8"]


def test_parser_captures_bare_and_schemed_links():
    rec = parse_resume_text(RESUME_TEXT)
    urls = values(rec, "links")
    assert any("github.com/janedoe" in u for u in urls)
    assert any("linkedin.com/in/janedoe" in u for u in urls)


def test_parser_does_not_mistake_section_header_for_name():
    rec = parse_resume_text("Skills\nPython, Go\n")
    assert "full_name" not in rec.fields


def test_parser_finds_name_after_a_contact_header_line():
    # A leading "Contact:" line must not abort name detection (messy layouts).
    text = ("Contact: reach me at a@b.com or c@d.com\n"
            "Robin Fisher\nSenior Cloud Architect\n")
    rec = parse_resume_text(text)
    assert rec.fields["full_name"].value == "Robin Fisher"


def test_parser_does_not_mistake_tech_stack_for_location():
    # A skills/stack row near the top ("Frontend: Next.js, React") has a comma and
    # few digits but is not a place — it must not be picked up as location.
    text = ("Sam Rivera\n"
            "Frontend: Next.js, React\n"
            "Bengaluru, India\n")
    rec = parse_resume_text(text)
    assert values(rec, "location") == ["Bengaluru, India"]


def test_skills_found_under_nonstandard_header_and_inline():
    # "Technical Skills" header (not the bare word) + values on the header line.
    rec = parse_resume_text(
        "Pat Lee\nSoftware Engineer\n\nTechnical Skills\nPython, Go, React\n")
    assert {"Python", "Go", "React"} <= set(values(rec, "skills"))
    rec2 = parse_resume_text("Pat Lee\nEngineer\nSkills: Rust, WebAssembly\n")
    assert {"Rust", "WebAssembly"} <= set(values(rec2, "skills"))


def test_headline_skips_skill_summary_line():
    # A skills summary right under the name must not become the headline.
    rec = parse_resume_text(
        "Pat Lee\nJava Developer, Python, SQL, AWS, Docker\n"
        "\nTechnical Skills\nJava, Python\n")
    assert "headline" not in rec.fields
    assert {"Java", "Python"} <= set(values(rec, "skills"))


def test_education_extracted_with_degree_institution_and_dates():
    text = ("Avery Stone\nData Engineer\n\n"
            "Education\n"
            "B.S. Computer Science, UT Austin (2014 to 2018)\n"
            "M.S. Data Science, University of Washington (2011 to 2013)\n")
    rec = parse_resume_text(text)
    edu = values(rec, "education")
    assert len(edu) == 2
    assert edu[0].degree == "B.S. Computer Science"
    assert edu[0].institution == "UT Austin"
    assert edu[0].start == "2014-01" and edu[0].end == "2018-01"


@pytest.mark.skipif(not RESUME_PDF.exists(),
                    reason="run scripts/make_sample_resume.py to create the PDF")
def test_csv_plus_resume_merge_into_one_candidate():
    result = run([Source("csv", CSV), Source("resume_pdf", str(RESUME_PDF))])
    # 3 CSV rows + 1 resume, but Jane's resume merges with her CSV row -> 3.
    assert len(result.candidates) == 3
    jane = next(c for c in result.candidates if c.full_name.value == "Jane Doe")

    # Email agreed across CSV + Resume -> agreement bonus (0.90 + 0.05).
    assert jane.emails[0].confidence == pytest.approx(0.95)
    assert jane.emails[0].sources == ("CSV", "Resume")

    # Headline conflicts; Resume (90) wins over CSV (80), loser recorded.
    assert jane.headline.value == "Senior Machine Learning Engineer"
    assert jane.headline.confidence == pytest.approx(0.80)
    assert jane.headline.conflicts[0].value == "Senior ML Engineer"

    # Canonical link dedup: one github entry, not two.
    github = [l for l in jane.links if l.value.kind == "github"]
    assert len(github) == 1
    assert github[0].sources == ("CSV", "Resume")
