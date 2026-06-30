"""Guards for the benchmark generator — keeps the scaling demo honest."""

from scripts.benchmark import generate, run_stages
from src.models.config import PipelineConfig


def test_generator_emits_primaries_plus_some_duplicates():
    recs = generate(100)
    primaries = [r for r in recs if r.source == "CSV"]
    assert len(primaries) == 100
    assert 100 < len(recs) <= 200  # some, but not all, get a duplicate


def test_each_synthetic_person_resolves_to_one_cluster():
    # The invariant the benchmark depends on: unique ids per person => every
    # duplicate merges back, so clusters == N exactly (no accidental collisions).
    recs = generate(300)
    stats, clusters = run_stages(recs, PipelineConfig())
    assert clusters == 300
    assert stats.records_in == len(recs)
    assert stats.total_ms >= 0.0
