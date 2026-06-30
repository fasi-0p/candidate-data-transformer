"""Loosely-typed records produced by extractors, before normalization.

Extractors emit `IntermediateRecord`s: raw strings keyed by canonical field
name, plus the source label and per-value extraction methods. Normalization
turns these into the typed canonical values. Keeping extraction output loose is
deliberate — extractors never normalize and never crash the pipeline (KB §18).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RawField:
    """A single extracted value with how it was obtained."""

    value: Any            # raw string (or list of strings for collections)
    method: str = "exact"  # "csv_column", "regex", "pdf_text", ...
    malformed: bool = False


@dataclass(slots=True)
class IntermediateRecord:
    """One logical candidate as seen by a single source.

    `fields` maps a canonical field name -> RawField (scalar) or list[RawField]
    (collection). Unknown source fields are simply absent (KB §18: ignore
    unknown fields).
    """

    source: str  # "Resume", "ATS", "CSV", "GitHub"
    fields: dict[str, RawField | list[RawField]] = field(default_factory=dict)

    def get(self, name: str) -> RawField | list[RawField] | None:
        return self.fields.get(name)
