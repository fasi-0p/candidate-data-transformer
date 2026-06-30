"""Canonical data model and configuration types.

This package is the contract every later pipeline stage signs (docs/DESIGN.md §2).
Import everything you need from here rather than the submodules.
"""

from .canonical import (
    CanonicalCandidate,
    EducationItem,
    ExperienceItem,
    Link,
    Location,
)
from .config import (
    AGREEMENT_BONUS,
    CONFLICT_PENALTY,
    DEFAULT_BASE_CONFIDENCE,
    DEFAULT_SOURCE_PRIORITY,
    MALFORMED_PENALTY,
    FieldMapping,
    MissingValuePolicy,
    PipelineConfig,
    ProjectionConfig,
)
from .intermediate import IntermediateRecord, RawField
from .normalized import NormalizedRecord, NormalizedValue
from .stats import RunStats
from .value import Conflict, TrackedValue, ValueSource, clamp_confidence

__all__ = [
    # value atom
    "TrackedValue",
    "ValueSource",
    "Conflict",
    "clamp_confidence",
    # canonical
    "CanonicalCandidate",
    "Location",
    "Link",
    "ExperienceItem",
    "EducationItem",
    # intermediate
    "IntermediateRecord",
    "RawField",
    # normalized
    "NormalizedRecord",
    "NormalizedValue",
    # config
    "PipelineConfig",
    "ProjectionConfig",
    "FieldMapping",
    "MissingValuePolicy",
    "DEFAULT_SOURCE_PRIORITY",
    "DEFAULT_BASE_CONFIDENCE",
    "AGREEMENT_BONUS",
    "CONFLICT_PENALTY",
    "MALFORMED_PENALTY",
    # stats
    "RunStats",
]
