"""Scaling benchmark — makes the efficiency claim observable (docs/DESIGN.md §9.5).

Generates N synthetic candidates plus a fraction of cross-source duplicates
(some linked by an exact email key, some name-only so fuzzy matching runs), then
times the in-memory algorithmic stages (normalize -> resolve -> merge ->
validate) across growing N. Extraction is deliberately excluded — that is disk
I/O, not the scaling story.

The headline number is **resolve µs per record**: if blocking + union-find work,
it stays roughly flat as N grows (near-linear total time), instead of climbing
the way an O(n²) all-pairs resolver would.

    python scripts/benchmark.py
    python scripts/benchmark.py --sizes 1000 4000 16000 64000
"""

from __future__ import annotations

import argparse
import gc
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root

from src.models.config import PipelineConfig
from src.models.intermediate import IntermediateRecord, RawField
from src.models.stats import RunStats
from src.merger.merge import merge_clusters
from src.normalizers.engine import normalize_record
from src.resolution.cluster import cluster_records
from src.validators.validate import validate_all

_FIRST = ["Jane", "John", "Priya", "Alan", "Mei", "Omar", "Sara", "Liam"]
_SKILLS = ["ml", "python3", "reactjs", "k8s", "postgres", "nlp", "tensorflow",
           "golang", "docker", "aws", "typescript", "graphql"]


def _primary(i: int, rng: random.Random) -> IntermediateRecord:
    first = _FIRST[i % len(_FIRST)]
    skills = rng.sample(_SKILLS, k=3)
    return IntermediateRecord(source="CSV", fields={
        "full_name": RawField(f"{first} Sur{i}", method="csv_column"),
        "emails": [RawField(f"user{i}@example.com", method="csv_column")],
        "phones": [RawField(f"+91{9000000000 + i}", method="csv_column")],
        "headline": RawField("Software Engineer", method="csv_column"),
        "years_experience": RawField(str(i % 15), method="csv_column"),
        "skills": [RawField(s, method="csv_column") for s in skills],
        "location": RawField("Bengaluru, India", method="csv_column"),
    })


def _duplicate(i: int, rng: random.Random) -> IntermediateRecord:
    """A second record for person i. Even i -> exact email dup (Resume);
    odd i -> name-only dup (recruiter note, exercises fuzzy matching)."""
    first = _FIRST[i % len(_FIRST)]
    if i % 2 == 0:
        return IntermediateRecord(source="Resume", fields={
            "full_name": RawField(f"{first} Sur{i}", method="pdf_text"),
            "emails": [RawField(f"user{i}@example.com", method="pdf_regex")],
            "skills": [RawField(rng.choice(_SKILLS), method="pdf_section")],
        })
    return IntermediateRecord(source="Recruiter Note", fields={
        "full_name": RawField(f"{first} Sur{i}", method="note_text"),
        "headline": RawField("Backend Engineer", method="note_text"),
    })


def generate(n: int, dup_fraction: float = 0.3) -> list[IntermediateRecord]:
    rng = random.Random(42)
    records: list[IntermediateRecord] = []
    for i in range(n):
        records.append(_primary(i, rng))
        if rng.random() < dup_fraction:
            records.append(_duplicate(i, rng))
    return records


def run_stages(records: list[IntermediateRecord],
               cfg: PipelineConfig) -> tuple[RunStats, int]:
    stats = RunStats()
    stats.records_in = len(records)
    gc.collect()
    gc.disable()  # remove GC pauses from the timing signal
    try:
        with stats.stage("normalize"):
            normalized = [normalize_record(r, cfg) for r in records]
        with stats.stage("resolve"):
            clusters = cluster_records(normalized, cfg.fuzzy_name_threshold)
        with stats.stage("merge"):
            candidates = merge_clusters(clusters, cfg)
        with stats.stage("validate"):
            validate_all(candidates)
    finally:
        gc.enable()
    return stats, len(clusters)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+",
                        default=[1000, 2000, 4000, 8000, 16000])
    args = parser.parse_args(argv)
    cfg = PipelineConfig()

    header = (f"{'N':>7} {'records':>8} {'clusters':>8} "
              f"{'normalize':>10} {'resolve':>9} {'merge':>8} "
              f"{'validate':>9} {'total':>8} {'resolve_us/rec':>14}")
    print(header)
    print("-" * len(header))

    prev = None
    for n in args.sizes:
        records = generate(n)
        # warm caches (pycountry fuzzy lookup) so the first row isn't skewed.
        run_stages(records[:50], cfg)
        stats, clusters = run_stages(records, cfg)
        t = stats.stage_timings_ms
        resolve_us = t["resolve"] * 1000.0 / len(records)
        scale = ""
        if prev is not None:
            n_ratio = n / prev[0]
            r_ratio = t["resolve"] / prev[1] if prev[1] else float("inf")
            scale = f"  (Nx{n_ratio:.0f} -> resolve x{r_ratio:.1f})"
        print(f"{n:>7} {len(records):>8} {clusters:>8} "
              f"{t['normalize']:>10.1f} {t['resolve']:>9.2f} {t['merge']:>8.2f} "
              f"{t['validate']:>9.2f} {stats.total_ms:>8.1f} "
              f"{resolve_us:>14.2f}{scale}")
        prev = (n, t["resolve"])

    print("\nresolve_us/rec roughly flat + 'resolve xN' tracking 'NxN' => "
          "near-linear resolution (blocking + union-find, not O(n^2)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
