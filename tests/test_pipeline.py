"""End-to-end pipeline + projection tests, including the determinism invariant."""

import json
from pathlib import Path

import pytest

from src.models.config import (FieldMapping, MissingValuePolicy,
                               ProjectionConfig)
from src.pipeline import Source, run
from src.projection.engine import project

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CSV = str(SAMPLES / "candidates.csv")


def test_csv_pipeline_produces_candidates():
    result = run([Source("csv", CSV)])
    assert len(result.candidates) == 3
    jane = next(c for c in result.candidates if c.full_name.value == "Jane Doe")
    assert jane.emails[0].value == "jane.doe@gmail.com"
    assert jane.phones[0].value == "+919876543210"          # E.164
    assert jane.location.value.country == "IN"              # ISO alpha-2
    assert {s.value for s in jane.skills} == {"Machine Learning", "Python", "React"}


def test_priya_has_two_emails_split_from_cell():
    result = run([Source("csv", CSV)])
    priya = next(c for c in result.candidates if c.full_name.value == "Priya Nair")
    assert {e.value for e in priya.emails} == {
        "priya@startup.io", "priya.nair@gmail.com"}


def test_pipeline_is_deterministic_byte_for_byte():
    a = run([Source("csv", CSV)])
    b = run([Source("csv", CSV)])
    dump = lambda r: json.dumps(
        [_canon(c) for c in r.candidates], sort_keys=True)
    assert dump(a) == dump(b)


def test_projection_does_not_mutate_canonical():
    result = run([Source("csv", CSV)])
    cand = result.candidates[0]
    before = cand.full_name.value
    cfg1 = ProjectionConfig("a", (FieldMapping("full_name", "n"),),
                            include_confidence=True)
    cfg2 = ProjectionConfig("b", (FieldMapping("emails[0]", "e"),),
                            missing_value_policy=MissingValuePolicy.NULL)
    project(cand, cfg1)
    project(cand, cfg2)
    assert cand.full_name.value == before  # frozen + projection is read-only


def test_missing_value_policies():
    result = run([Source("csv", CSV)])
    john = next(c for c in result.candidates if c.full_name.value == "John Smith")
    # John has no linkedin link; project a non-existent path.
    omit = project(john, ProjectionConfig(
        "o", (FieldMapping("links[5]", "x"),),
        missing_value_policy=MissingValuePolicy.OMIT))
    assert "x" not in omit
    nul = project(john, ProjectionConfig(
        "n", (FieldMapping("links[5]", "x"),),
        missing_value_policy=MissingValuePolicy.NULL))
    assert nul == {"x": None}


def _canon(c):
    return {
        "id": c.candidate_id,
        "name": c.full_name.value if c.full_name else None,
        "emails": [e.value for e in c.emails],
        "skills": [s.value for s in c.skills],
        "conf": round(c.record_confidence, 4),
    }
