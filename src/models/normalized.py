"""Normalized records: the bridge between extraction and merge.

Normalization turns loose `IntermediateRecord`s (raw strings) into typed values,
each paired with its `ValueSource`. Every field maps to a *list* of
`NormalizedValue` (uniform handling of scalars and collections), so merge can
collect across records without special-casing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .value import ValueSource


@dataclass(slots=True)
class NormalizedValue:
    value: Any
    source: ValueSource


@dataclass(slots=True)
class NormalizedRecord:
    source: str
    fields: dict[str, list[NormalizedValue]] = field(default_factory=dict)

    def values(self, name: str) -> list[NormalizedValue]:
        return self.fields.get(name, [])

    def first_value(self, name: str) -> Any | None:
        vals = self.fields.get(name)
        return vals[0].value if vals else None
