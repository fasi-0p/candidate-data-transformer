"""Tests for per-field normalizers and the normalization engine."""

import pytest

from src.models.canonical import Link, Location
from src.models.config import PipelineConfig
from src.models.intermediate import IntermediateRecord, RawField
from src.normalizers import fields as F
from src.normalizers.engine import normalize_record


def test_email_lowercased_and_validated():
    assert F.normalize_email("  John.Doe@Gmail.COM ") == F.NormResult("john.doe@gmail.com", True)
    assert F.normalize_email("not-an-email").ok is False


def test_phone_to_e164_india():
    r = F.normalize_phone("9876543210", "IN")
    assert r.ok and r.value == "+919876543210"


def test_phone_invalid_flagged():
    assert F.normalize_phone("123", "IN").ok is False


def test_date_to_year_month():
    assert F.normalize_date("Jan 2024") == F.NormResult("2024-01", True)
    assert F.normalize_date("present").value is None
    assert F.normalize_date("garbage-date").ok is False


def test_country_to_alpha2():
    assert F.normalize_country("India").value == "IN"
    assert F.normalize_country("US").value == "US"


def test_skill_alias_mapping():
    assert F.normalize_skill("ML").value == "Machine Learning"
    assert F.normalize_skill("reactjs").value == "React"
    # Unknown but valid skill is kept, not rejected.
    unknown = F.normalize_skill("Rust")
    assert unknown.ok and unknown.value == "Rust"


def test_skill_implausible_flagged_malformed():
    # Real but unrecognized multi-word skills stay valid...
    assert F.normalize_skill("Amazon Web Services").ok is True
    # ...while sentence-shaped noise, stray numbers, and overlong blobs are kept
    # but flagged malformed (wrong/inconsistent skill data → penalized).
    assert F.normalize_skill("I am proficient in many languages").ok is False
    assert F.normalize_skill("5+").ok is False
    assert F.normalize_skill("x" * 50).ok is False
    # The value is preserved either way (never silently dropped).
    assert F.normalize_skill("5+").value == "5+"


def test_years_extracts_number():
    assert F.normalize_years("5 years").value == 5.0
    assert F.normalize_years("3.5 yrs").value == 3.5
    assert F.normalize_years("none").ok is False


def test_location_city_country():
    loc = F.normalize_location("Bengaluru, India")
    assert isinstance(loc.value, Location)
    assert loc.value.country == "IN"
    assert loc.value.city == "Bengaluru"


def test_location_city_alias_canonicalized():
    # "Bangalore" and "Bengaluru" normalize to the same canonical city, so they
    # agree (rather than conflict) when merged across sources.
    assert F.normalize_location("Bangalore, India").value.city == "Bengaluru"
    assert (F.normalize_location("Bangalore, India").value
            == F.normalize_location("Bengaluru, India").value)


def test_link_kind_inferred_and_url_canonicalized():
    # Scheme/www/trailing-slash stripped so the same link merges across sources;
    # the github/linkedin handle is parsed out of the path.
    assert F.normalize_link("https://github.com/jane").value == Link(
        "github", "github.com/jane", "jane")
    assert F.normalize_link("https://www.GitHub.com/jane/").value.url == "github.com/jane"
    assert F.normalize_link("https://linkedin.com/in/jane").value.kind == "linkedin"


def test_link_handle_parsed_from_url():
    # github: first path segment; deeper repo paths still resolve to the user.
    assert F.normalize_link("github.com/octocat").value.handle == "octocat"
    assert F.normalize_link("https://github.com/octocat/repo").value.handle == "octocat"
    # linkedin: segment after /in/ (or /pub/).
    assert F.normalize_link("https://linkedin.com/in/jane-doe-123").value.handle == "jane-doe-123"
    # bare host or non-social URL has no handle (never invented).
    assert F.normalize_link("https://github.com").value.handle is None
    assert F.normalize_link("https://janedoe.dev").value.handle is None


def test_normalize_record_dispatches_and_flags_malformed():
    rec = IntermediateRecord(
        source="CSV",
        fields={
            "full_name": RawField("  Jane   Doe ", method="csv_column"),
            "emails": [RawField("JANE@X.COM", method="csv_column")],
            "phones": [RawField("badphone", method="csv_column")],
            "skills": [RawField("ml", method="csv_column"),
                       RawField("python3", method="csv_column")],
        },
    )
    out = normalize_record(rec, PipelineConfig())
    assert out.first_value("full_name") == "Jane Doe"
    assert out.first_value("emails") == "jane@x.com"
    # invalid phone is kept but flagged malformed
    assert out.values("phones")[0].source.malformed is True
    assert [v.value for v in out.values("skills")] == ["Machine Learning", "Python"]
