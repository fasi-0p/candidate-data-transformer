"""Tests for the ATS JSON extractor (pure parse + cross-source merge)."""

from pathlib import Path

from src.extractors.ats_extractor import AtsExtractor, parse_ats_candidate
from src.pipeline import Source, run

ROOT = Path(__file__).resolve().parents[1]
ATS_EXPORT = str(ROOT / "dataset" / "json" / "ats_export.json")
CSV = str(ROOT / "dataset" / "csv" / "10_conflicts_vs_resume.csv")

CANDIDATE = {
    "fullName": "Jordan Blake",
    "email": "jordan.blake@example.com",
    "phone": "+1 415 555 7788",
    "currentTitle": "Software Engineer II",
    "yearsExperience": 5,
    "location": {"city": "Austin", "country": "United States"},
    "skills": ["Python", "Django", "React"],
    "links": {"github": "github.com/jordanblake", "linkedin": "linkedin.com/in/jordanblake"},
}


def values(rec, field):
    raw = rec.fields[field]
    items = raw if isinstance(raw, list) else [raw]
    return [x.value for x in items]


def test_parse_maps_ats_fields():
    rec = parse_ats_candidate(CANDIDATE)
    assert rec.source == "ATS"
    assert values(rec, "full_name") == ["Jordan Blake"]
    assert values(rec, "headline") == ["Software Engineer II"]
    assert values(rec, "years_experience") == ["5"]
    assert values(rec, "emails") == ["jordan.blake@example.com"]
    assert values(rec, "location") == ["Austin, United States"]
    assert set(values(rec, "skills")) == {"Python", "Django", "React"}
    assert set(values(rec, "links")) == {
        "github.com/jordanblake", "linkedin.com/in/jordanblake"}


def test_parse_invents_nothing_for_empty_candidate():
    assert parse_ats_candidate({}).fields == {}


def test_extract_tolerates_bad_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert list(AtsExtractor().extract(str(bad))) == []
    assert list(AtsExtractor().extract(str(tmp_path / "missing.json"))) == []


def test_ats_export_dataset_produces_candidates():
    # Subset check (not equality) so the shared dataset can gain more entries.
    result = run([Source("ats_json", ATS_EXPORT)])
    names = {c.full_name.value for c in result.candidates}
    assert {"Jordan Blake", "Nina Patel"} <= names


def test_ats_merges_with_csv_by_email():
    # Jordan Blake is in both the ATS export and the sample CSV (shared email).
    result = run([Source("csv", CSV), Source("ats_json", ATS_EXPORT)])
    jordans = [c for c in result.candidates if c.full_name.value == "Jordan Blake"]
    assert len(jordans) == 1, "ATS candidate should merge into the CSV candidate"
