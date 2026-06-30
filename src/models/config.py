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
    "Recruiter Note": 60,  # free-form text, lowest trust — used for verification
}

DEFAULT_BASE_CONFIDENCE: dict[str, float] = {
    "Resume": 0.90,
    "ATS": 0.85,
    "CSV": 0.80,
    "GitHub": 0.70,
    "Recruiter Note": 0.60,
}

# Confidence adjustments (KB §13)
AGREEMENT_BONUS = 0.05
CONFLICT_PENALTY = 0.10
MALFORMED_PENALTY = 0.20
# Skills are the primary matching signal, so wrong/inconsistent skill data is
# costlier than a generic malformed field: a "skill" that is really a stray
# number or a sentence-shaped extraction artifact is penalized harder (1.5x).
SKILL_MALFORMED_PENALTY = 0.30
# Completeness: each required section a candidate is missing lowers its overall
# record confidence by this much (an incomplete profile is less trustworthy).
COMPLETENESS_PENALTY = 0.15
REQUIRED_FIELDS: tuple[str, ...] = ("skills",)


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
    completeness_penalty: float = COMPLETENESS_PENALTY
    required_fields: tuple[str, ...] = REQUIRED_FIELDS
    skill_malformed_penalty: float = SKILL_MALFORMED_PENALTY

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
