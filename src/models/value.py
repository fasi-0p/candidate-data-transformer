"""The provenance-carrying value atom.

Every field in the canonical model is a `TrackedValue`. Provenance, confidence,
and conflict history travel *with* the value through every pipeline stage rather
than living in a side table — this is what makes explainability, immutability,
and determinism structural facts instead of manual effort (see docs/DESIGN.md §1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


def clamp_confidence(value: float) -> float:
    """Clamp a confidence score into the valid 0..1 range (KB §13)."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@dataclass(frozen=True, slots=True)
class ValueSource:
    """Where a value came from and how it was obtained.

    `raw` preserves the pre-normalization string for auditability — so the
    Inspector can show "the resume literally said 'Jan 2024' and we normalized
    it to 2024-01".
    """

    source: str             # "Resume", "ATS", "CSV", "GitHub"
    method: str             # "exact", "regex", "fuzzy_name", "csv_column", ...
    raw: str | None = None  # pre-normalization value, if any
    malformed: bool = False  # extraction/normalization could not fully parse it

    def sort_key(self) -> tuple[str, str, str]:
        """Stable ordering key — never rely on insertion order (determinism)."""
        return (self.source, self.method, self.raw or "")


@dataclass(frozen=True, slots=True)
class Conflict:
    """A value that lost during merge, plus the reason it lost.

    Recorded rather than discarded so conflict resolution is fully explainable
    (KB §12) and so the confidence penalty is auditable.
    """

    value: Any
    source: ValueSource
    reason: str  # "lower_source_priority", "less_complete", "tiebreak_lost"

    def sort_key(self) -> tuple:
        return (*self.source.sort_key(), str(self.value), self.reason)


@dataclass(frozen=True, slots=True)
class TrackedValue(Generic[T]):
    """A canonical value together with its full provenance and confidence.

    Collections in the canonical model hold *tuples* of these (one per distinct
    value); scalars hold a single one. Tuples (not lists) keep the object
    immutable and the structure hashable-friendly.
    """

    value: T
    confidence: float
    primary: ValueSource
    agreements: tuple[ValueSource, ...] = field(default=())
    conflicts: tuple[Conflict, ...] = field(default=())

    def with_confidence(self, confidence: float) -> "TrackedValue[T]":
        """Return a copy with a clamped confidence (canonical stays immutable)."""
        from dataclasses import replace

        return replace(self, confidence=clamp_confidence(confidence))

    @property
    def sources(self) -> tuple[str, ...]:
        """All distinct source names that contributed to this value (KB §9)."""
        names = {self.primary.source}
        names.update(a.source for a in self.agreements)
        return tuple(sorted(names))
