"""Tests for the resume parser (pure text) and cross-source merge."""

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
    rec = parse_resume_text(RESUME_TEXT)
    assert rec.source == "Resume"
    assert values(rec, "full_name") == ["Jane Doe"]
    assert values(rec, "headline") == ["Senior Machine Learning Engineer"]
    assert values(rec, "emails") == ["jane.doe@gmail.com"]
    assert values(rec, "location") == ["Bengaluru, India"]
    assert "Python" in values(rec, "skills")
    assert values(rec, "years_experience") == ["7"]


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
