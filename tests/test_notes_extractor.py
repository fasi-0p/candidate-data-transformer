"""Tests for the recruiter-notes extractor (structured + prose, multi-candidate)."""

from pathlib import Path

from src.extractors.notes_extractor import NotesExtractor, parse_notes_text
from src.pipeline import Source, run

ROOT = Path(__file__).resolve().parents[1]
NOTES = str(ROOT / "dataset" / "notes" / "recruiter_notes.txt")
CSV = str(ROOT / "samples" / "candidates.csv")


def fields(rec):
    out = {}
    for k, v in rec.fields.items():
        out[k] = [x.value for x in v] if isinstance(v, list) else v.value
    return out


def test_structured_blocks_parsed():
    text = ("Name: Jane Doe\nEmail: jane@x.com\nTitle: ML Engineer\n"
            "Years: 5\nSkills: Python, TensorFlow\nLinkedIn: linkedin.com/in/janedoe\n"
            "---\nName: Sam Rivera\nEmail: sam@y.com\nSkills: Go, Postgres\n")
    recs = list(parse_notes_text(text))
    assert len(recs) == 2
    a = fields(recs[0])
    assert a["full_name"] == "Jane Doe"
    assert a["emails"] == ["jane@x.com"]
    assert a["headline"] == "ML Engineer"
    assert a["years_experience"] == "5"
    assert a["skills"] == ["Python", "TensorFlow"]
    assert a["links"] == ["linkedin.com/in/janedoe"]
    assert recs[0].source == "Recruiter Note"


def test_prose_fallback_extracts_name_email_phone():
    text = "Spoke with Jane Doe (jane@x.com, +91 98765 43210). Strong ML engineer."
    rec = list(parse_notes_text(text))[0]
    f = fields(rec)
    assert f["full_name"] == "Jane Doe"        # 'Spoke'/'with' filler skipped
    assert f["emails"] == ["jane@x.com"]
    assert f["phones"] == ["+91 98765 43210"]
    assert "engineer" in f["headline"].lower()


def test_blank_line_separates_when_no_rule_lines():
    text = "Name: A One\nEmail: a@x.com\n\nName: B Two\nEmail: b@y.com\n"
    recs = list(parse_notes_text(text))
    assert {fields(r)["full_name"] for r in recs} == {"A One", "B Two"}


def test_extract_tolerates_missing_file(tmp_path):
    assert list(NotesExtractor().extract(str(tmp_path / "nope.txt"))) == []


def test_notes_cross_verify_merges_with_csv():
    # A note carrying Jane's CSV email merges into her candidate and contributes
    # "Recruiter Note" as an agreeing source on the shared email.
    note = tmp_note()
    result = run([Source("csv", CSV), Source("notes", note)])
    jane = next(c for c in result.candidates if c.full_name.value == "Jane Doe")
    email = next(e for e in jane.emails if e.value == "jane.doe@gmail.com")
    assert "Recruiter Note" in email.sources


def tmp_note():
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".txt")
    import os
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("Name: Jane Doe\nEmail: jane.doe@gmail.com\nSkills: Python\n")
    return path
