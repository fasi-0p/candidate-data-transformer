"""Smoke tests for the model layer — the contract every stage signs.

These assert the structural guarantees the design relies on: immutability of
canonical data, confidence clamping, derived record confidence, and the
provenance carried by each value.
"""

import dataclasses

import pytest

from src.models import (
    CanonicalCandidate,
    Conflict,
    PipelineConfig,
    RunStats,
    TrackedValue,
    ValueSource,
    clamp_confidence,
)


def make_tv(value, source="CSV", conf=0.8):
    return TrackedValue(
        value=value,
        confidence=conf,
        primary=ValueSource(source=source, method="csv_column", raw=str(value)),
    )


def test_clamp_confidence_bounds():
    assert clamp_confidence(-0.5) == 0.0
    assert clamp_confidence(1.5) == 1.0
    assert clamp_confidence(0.42) == 0.42


def test_canonical_is_immutable():
    c = CanonicalCandidate(candidate_id="abc", full_name=make_tv("Jane"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.full_name = make_tv("Other")  # type: ignore[misc]


def test_tracked_value_is_immutable():
    tv = make_tv("Jane")
    with pytest.raises(dataclasses.FrozenInstanceError):
        tv.confidence = 0.1  # type: ignore[misc]


def test_with_confidence_returns_copy_and_clamps():
    tv = make_tv("Jane", conf=0.8)
    updated = tv.with_confidence(1.7)
    assert tv.confidence == 0.8           # original untouched
    assert updated.confidence == 1.0      # clamped copy
    assert updated.value == "Jane"


def test_sources_unions_primary_and_agreements():
    tv = TrackedValue(
        value="Python",
        confidence=0.95,
        primary=ValueSource("Resume", "pdf_text", "Python"),
        agreements=(ValueSource("GitHub", "api", "python"),),
    )
    assert tv.sources == ("GitHub", "Resume")  # sorted, deduped


def test_record_confidence_is_mean_of_fields():
    c = CanonicalCandidate(
        candidate_id="abc",
        full_name=make_tv("Jane", conf=0.9),
        emails=(make_tv("jane@x.com", conf=0.7),),
    )
    assert c.record_confidence == pytest.approx((0.9 + 0.7) / 2)


def test_record_confidence_empty_is_zero():
    assert CanonicalCandidate(candidate_id="x").record_confidence == 0.0


def test_pipeline_config_defaults_and_unknown_source():
    cfg = PipelineConfig()
    assert cfg.priority("Resume") == 90
    assert cfg.base("ATS") == 0.85
    assert cfg.priority("Twitter") == cfg.unknown_source_priority
    assert cfg.base("Twitter") == cfg.unknown_base_confidence


def test_runstats_times_stages():
    stats = RunStats()
    with stats.stage("extract"):
        sum(range(1000))
    assert "extract" in stats.stage_timings_ms
    assert stats.stage_timings_ms["extract"] >= 0.0
    assert stats.total_ms >= 0.0


def test_conflict_sort_key_is_stable():
    s = ValueSource("CSV", "csv_column", "a@x.com")
    c = Conflict(value="a@x.com", source=s, reason="lower_source_priority")
    assert isinstance(c.sort_key(), tuple)
