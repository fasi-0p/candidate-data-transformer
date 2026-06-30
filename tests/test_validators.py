"""Validation tests — report semantics, never throwing (KB §17)."""

from pathlib import Path

from src.models.canonical import CanonicalCandidate, Location
from src.models.value import TrackedValue, ValueSource
from src.pipeline import Source, run
from src.validators.report import Severity
from src.validators.validate import validate_candidate

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def tv(value, conf=0.8, malformed=False):
    return TrackedValue(value, conf,
                        ValueSource("CSV", "x", str(value), malformed))


def test_clean_candidate_is_valid():
    c = CanonicalCandidate(
        candidate_id="abc",
        full_name=tv("Jane Doe"),
        emails=(tv("jane@x.com"),),
        phones=(tv("+919876543210"),),
        location=tv(Location(city="Bengaluru", country="IN")),
    )
    report = validate_candidate(c)
    assert report.is_valid
    assert report.issues == []


def test_bad_email_is_error():
    c = CanonicalCandidate(candidate_id="abc", emails=(tv("not-an-email"),))
    report = validate_candidate(c)
    assert not report.is_valid
    assert any(i.code == "email_format" and i.severity is Severity.ERROR
               for i in report.errors)


def test_non_e164_phone_is_error():
    c = CanonicalCandidate(candidate_id="abc", phones=(tv("9876543210"),))
    report = validate_candidate(c)
    assert any(i.code == "phone_format" for i in report.errors)


def test_confidence_out_of_range_is_error():
    c = CanonicalCandidate(candidate_id="abc", full_name=tv("Jane", conf=1.5))
    report = validate_candidate(c)
    assert any(i.code == "confidence_range" for i in report.errors)


def test_malformed_value_is_warning_not_error():
    c = CanonicalCandidate(
        candidate_id="abc",
        full_name=tv("Jane"),
        years_experience=tv(0.0, malformed=True),
    )
    report = validate_candidate(c)
    assert report.is_valid  # warnings don't invalidate
    assert any(i.code == "malformed" and i.severity is Severity.WARNING
               for i in report.warnings)


def test_duplicate_email_is_warning():
    c = CanonicalCandidate(
        candidate_id="abc", emails=(tv("jane@x.com"), tv("jane@x.com")))
    report = validate_candidate(c)
    assert any(i.code == "duplicate" for i in report.warnings)


def test_missing_id_is_error():
    report = validate_candidate(CanonicalCandidate(candidate_id=""))
    assert any(i.code == "missing_id" for i in report.errors)


def test_pipeline_emits_valid_reports_for_samples():
    result = run([Source("csv", str(SAMPLES / "candidates.csv"))])
    assert len(result.reports) == len(result.candidates)
    assert all(r.is_valid for r in result.reports)
    assert "validate" in result.stats.stage_timings_ms
