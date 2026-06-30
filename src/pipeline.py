"""Pipeline composition — the whole engine as one pure-ish function.

    extract -> normalize -> resolve identity -> merge

Each stage is timed into `RunStats` (docs/DESIGN.md §9.5). I/O (file reading)
lives only in extractors; everything after is in-memory and deterministic. A
single source that fails extraction is skipped, never fatal (KB §18).
"""

from __future__ import annotations

from dataclasses import dataclass

from .extractors import get_extractor
from .extractors.github_extractor import login_for_verification
from .merger.merge import merge_clusters
from .models.canonical import CanonicalCandidate
from .models.config import PipelineConfig
from .models.intermediate import IntermediateRecord
from .models.normalized import NormalizedRecord
from .models.stats import RunStats
from .normalizers.engine import normalize_record
from .resolution.cluster import cluster_records
from .validators.validate import validate_all
from .validators.report import ValidationReport
from .verify import apply_github_verification, apply_linkedin_verification


@dataclass(slots=True)
class Source:
    type: str   # registered extractor key, e.g. "csv"
    path: str


@dataclass(slots=True)
class PipelineResult:
    candidates: list[CanonicalCandidate]
    reports: list[ValidationReport]
    stats: RunStats


def run(sources: list[Source],
        cfg: PipelineConfig | None = None,
        linkedin_id: str | None = None) -> PipelineResult:
    cfg = cfg or PipelineConfig()
    stats = RunStats()

    # Stage 1-2: extract (only place that touches the filesystem).
    raw: list[IntermediateRecord] = []
    with stats.stage("extract"):
        for src in sources:
            raw.extend(_safe_extract(src))
    stats.records_in = len(raw)

    # Stage 3: normalize.
    with stats.stage("normalize"):
        normalized: list[NormalizedRecord] = [
            normalize_record(rec, cfg) for rec in raw
        ]

    # Stage 4: entity resolution (blocking + union-find + fuzzy name).
    with stats.stage("resolve"):
        clusters = cluster_records(normalized, cfg.fuzzy_name_threshold)
    stats.clusters_out = len(clusters)

    # Stage 5: merge.
    with stats.stage("merge"):
        candidates = merge_clusters(clusters, cfg)
    stats.conflicts_found = sum(_count_conflicts(c) for c in candidates)

    # Stage 7: validation (report, never throws).
    with stats.stage("validate"):
        reports = validate_all(candidates)
        # LinkedIn id verification (not a source): cross-check the provided id
        # against each candidate's LinkedIn handle, adjusting confidence + notes.
        candidates = apply_linkedin_verification(candidates, reports, linkedin_id)
        # GitHub: the provided username(s) double as verify ids — penalize a
        # candidate whose resume GitHub handle disagrees (works even if the
        # fetched profile didn't merge into that candidate).
        github_ids = [h for s in sources if s.type in ("github", "github_json")
                      if (h := login_for_verification(s.path))]
        candidates = apply_github_verification(candidates, reports, github_ids)

    return PipelineResult(candidates=candidates, reports=reports, stats=stats)


def _safe_extract(src: Source) -> list[IntermediateRecord]:
    try:
        return list(get_extractor(src.type).extract(src.path))
    except Exception:  # noqa: BLE001 — one bad source must not kill the run
        return []


def _count_conflicts(c: CanonicalCandidate) -> int:
    total = 0
    for tv in (c.full_name, c.headline, c.years_experience, c.location):
        if tv is not None:
            total += len(tv.conflicts)
    return total
