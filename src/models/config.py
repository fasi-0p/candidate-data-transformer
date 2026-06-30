"""Runtime configuration: pipeline behavior and projection schemas.

Two kinds of config:
- `PipelineConfig`: knobs for the engine (merge priorities, confidence bases,
  fuzzy threshold, default phone region). Sensible defaults from the KB.
- `ProjectionConfig`: a declarative output schema interpreted at runtime, so a
  new output format is data, not code (docs/DESIGN.md §6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# --- Merge / confidence defaults (KB §11, §13) --------------------------------

DEFAULT_SOURCE_PRIORITY: dict[str, int] = {
    "Resume": 90,
    "ATS": 85,
    "CSV": 80,
    "GitHub": 70,
}

DEFAULT_BASE_CONFIDENCE: dict[str, float] = {
    "Resume": 0.90,
    "ATS": 0.85,
    "CSV": 0.80,
    "GitHub": 0.70,
}

# Confidence adjustments (KB §13)
AGREEMENT_BONUS = 0.05
CONFLICT_PENALTY = 0.10
MALFORMED_PENALTY = 0.20


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    source_priority: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_SOURCE_PRIORITY))
    base_confidence: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_BASE_CONFIDENCE))
    default_region: str = "IN"          # E.164 default (docs/DESIGN.md §7)
    fuzzy_name_threshold: int = 90      # rapidfuzz cutoff (docs/DESIGN.md §3)
    unknown_source_priority: int = 50   # for sources not in the table
    unknown_base_confidence: float = 0.50

    def priority(self, source: str) -> int:
        return self.source_priority.get(source, self.unknown_source_priority)

    def base(self, source: str) -> float:
        return self.base_confidence.get(source, self.unknown_base_confidence)


# --- Projection (KB §15, §16) -------------------------------------------------

class MissingValuePolicy(str, Enum):
    OMIT = "omit"                  # leave the key out entirely
    NULL = "null"                  # emit null
    EMPTY_STRING = "empty_string"  # emit ""


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """Map a canonical path to an output key.

    `canonical` is a small path expression: a field name, optionally indexed for
    collections, e.g. "full_name", "emails[0]", "skills". Resolution lives in
    the projection engine.
    """

    canonical: str
    out: str


@dataclass(frozen=True, slots=True)
class ProjectionConfig:
    name: str
    fields: tuple[FieldMapping, ...]
    include_confidence: bool = False
    include_provenance: bool = False
    missing_value_policy: MissingValuePolicy = MissingValuePolicy.OMIT
