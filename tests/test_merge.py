"""Merge engine tests — the deterministic conflict-resolution core (§4)."""

import pytest

from src.models.config import PipelineConfig
from src.models.normalized import NormalizedRecord, NormalizedValue
from src.models.value import ValueSource
from src.merger.merge import merge_cluster


def nv(value, source, method="x", malformed=False):
    return NormalizedValue(value, ValueSource(source, method, str(value), malformed))


def rec(source, **fields):
    return NormalizedRecord(source=source,
                            fields={k: v for k, v in fields.items()})


def test_higher_priority_source_wins_and_records_conflict():
    cluster = [
        rec("Resume", full_name=[nv("Jane Doe", "Resume")]),
        rec("CSV", full_name=[nv("Jane D", "CSV")]),
    ]
    c = merge_cluster(cluster, PipelineConfig())
    assert c.full_name.value == "Jane Doe"          # Resume (90) beats CSV (80)
    assert len(c.full_name.conflicts) == 1
    assert c.full_name.conflicts[0].value == "Jane D"
    assert c.full_name.conflicts[0].reason == "lower_source_priority"
    # base 0.90 - conflict 0.10 = 0.80
    assert c.full_name.confidence == pytest.approx(0.80)


def test_agreement_raises_confidence():
    cluster = [
        rec("Resume", emails=[nv("jane@x.com", "Resume")]),
        rec("GitHub", emails=[nv("jane@x.com", "GitHub")]),
    ]
    c = merge_cluster(cluster, PipelineConfig())
    assert len(c.emails) == 1
    email = c.emails[0]
    # base Resume 0.90 + agreement 0.05 = 0.95
    assert email.confidence == pytest.approx(0.95)
    assert email.sources == ("GitHub", "Resume")


def test_malformed_winner_penalised():
    cluster = [rec("Resume", phones=[nv("notaphone", "Resume", malformed=True)])]
    c = merge_cluster(cluster, PipelineConfig())
    # base 0.90 - malformed 0.20 = 0.70
    assert c.phones[0].confidence == pytest.approx(0.70)


def test_tiebreak_is_deterministic_lexicographic():
    # Same source/priority/completeness (equal length) -> smaller string wins.
    cluster = [
        rec("CSV", headline=[nv("zeta", "CSV")]),
        rec("CSV", headline=[nv("beta", "CSV")]),
    ]
    c = merge_cluster(cluster, PipelineConfig())
    assert c.full_name is None
    assert c.headline.value == "beta"   # lexicographically smaller, deterministic
    assert c.headline.conflicts[0].reason == "tiebreak_lost"


def test_collections_sorted_for_determinism():
    cluster = [rec("CSV", skills=[nv("Python", "CSV"), nv("Go", "CSV"),
                                  nv("Docker", "CSV")])]
    c = merge_cluster(cluster, PipelineConfig())
    assert [s.value for s in c.skills] == ["Docker", "Go", "Python"]
