"""Completeness penalty: a profile missing a required section (skills) scores lower."""

import os
import tempfile

from src.models.canonical import CanonicalCandidate
from src.models.value import TrackedValue, ValueSource
from src.pipeline import Source, run


def _note(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def test_missing_skills_lowers_record_confidence():
    path = _note("Name: A One\nEmail: a@x.com\nSkills: Python\n"
                 "---\nName: B Two\nEmail: b@x.com\n")
    res = run([Source("notes", path)])
    a = next(c for c in res.candidates if c.full_name.value == "A One")
    b = next(c for c in res.candidates if c.full_name.value == "B Two")
    assert a.skills and b.skills == ()
    assert a.completeness_penalty == 0.0
    assert b.completeness_penalty == 0.15
    assert b.record_confidence < a.record_confidence


def test_record_confidence_subtracts_penalty():
    vs = ValueSource(source="CSV", method="csv_column")
    tv = TrackedValue(value="x", confidence=0.80, primary=vs)
    full = CanonicalCandidate(candidate_id="1", full_name=tv)
    penalized = CanonicalCandidate(candidate_id="1", full_name=tv,
                                   completeness_penalty=0.15)
    assert full.record_confidence == 0.80
    assert penalized.record_confidence == 0.65
