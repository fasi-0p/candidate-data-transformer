"""Tests for LinkedIn id verification (verify-only, not a data source)."""

from pathlib import Path

from src.pipeline import Source, run
from src.verify import parse_linkedin_handle

CSV = str(Path(__file__).resolve().parents[1] / "samples" / "candidates.csv")


def _jane(result):
    return next(c for c in result.candidates if c.full_name.value == "Jane Doe")


def _jane_linkedin(c):
    return next(l for l in c.links if l.value.kind == "linkedin")


def _report_for(result, c):
    return next(r for r in result.reports if r.candidate_id == c.candidate_id)


def test_parse_handle_from_url_or_bare():
    assert parse_linkedin_handle("https://linkedin.com/in/janedoe") == "janedoe"
    assert parse_linkedin_handle("linkedin.com/in/janedoe/") == "janedoe"
    assert parse_linkedin_handle("in/janedoe") == "janedoe"
    assert parse_linkedin_handle("janedoe") == "janedoe"
    assert parse_linkedin_handle("") is None
    assert parse_linkedin_handle(None) is None


def test_match_raises_confidence_and_adds_info():
    # Jane's CSV row carries linkedin.com/in/janedoe.
    baseline = _jane_linkedin(_jane(run([Source("csv", CSV)])))
    result = run([Source("csv", CSV)], linkedin_id="https://linkedin.com/in/janedoe")
    jane = _jane(result)
    li = _jane_linkedin(jane)
    assert li.confidence > baseline.confidence
    codes = {i.code for i in _report_for(result, jane).issues}
    assert "linkedin_verified" in codes
    # The verified link lists LinkedIn as an agreeing source, like a merged
    # GitHub link shows "agreed by GitHub, Resume".
    assert "LinkedIn" in li.sources


def test_mismatch_penalizes_and_warns():
    baseline = _jane_linkedin(_jane(run([Source("csv", CSV)])))
    result = run([Source("csv", CSV)], linkedin_id="someone-else")
    jane = _jane(result)
    assert _jane_linkedin(jane).confidence < baseline.confidence
    issues = _report_for(result, jane).issues
    assert any(i.code == "linkedin_mismatch" and i.severity.value == "warning"
               for i in issues)


def test_match_does_not_penalize_other_candidates():
    # Verifying Jane's id must not flag Priya (different handle) as a mismatch.
    result = run([Source("csv", CSV)], linkedin_id="janedoe")
    priya = next(c for c in result.candidates if c.full_name.value == "Priya Nair")
    codes = {i.code for i in _report_for(result, priya).issues}
    assert "linkedin_mismatch" not in codes
    assert "linkedin_unverified" not in codes


def test_no_id_is_a_noop():
    result = run([Source("csv", CSV)], linkedin_id=None)
    codes = {i.code for r in result.reports for i in r.issues}
    assert not any(c.startswith("linkedin_") for c in codes)
