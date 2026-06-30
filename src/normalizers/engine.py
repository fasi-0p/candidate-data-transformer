"""Normalization stage: IntermediateRecord -> NormalizedRecord.

Dispatches each canonical field to its normalizer (fields.py). Scalars and
collections are handled uniformly because `IntermediateRecord` stores a
`RawField` or a `list[RawField]`; we normalize element by element either way.

A field whose normalizer reports `ok=False` is *kept* with a malformed-flagged
`ValueSource` rather than dropped — we record that we could not normalize it
(KB §18), and merge later applies the confidence penalty.
"""

from __future__ import annotations

from typing import Callable

from ..models.config import PipelineConfig
from ..models.intermediate import IntermediateRecord, RawField
from ..models.normalized import NormalizedRecord, NormalizedValue
from ..models.value import ValueSource
from . import fields as F
from .fields import NormResult

# A handler turns one raw string into a NormResult. Region-aware handlers take
# the config; the rest ignore it.
Handler = Callable[[str, PipelineConfig], NormResult]


def _wrap(fn: Callable[[str], NormResult]) -> Handler:
    return lambda raw, _cfg: fn(raw)


FIELD_HANDLERS: dict[str, Handler] = {
    "full_name": _wrap(F.normalize_name),
    "headline": _wrap(F.normalize_name),
    "emails": _wrap(F.normalize_email),
    "phones": lambda raw, cfg: F.normalize_phone(raw, cfg.default_region),
    "location": _wrap(F.normalize_location),
    "links": _wrap(F.normalize_link),
    "years_experience": _wrap(F.normalize_years),
    "skills": _wrap(F.normalize_skill),
}


def _normalize_one(
    field: str, rf: RawField, source: str, cfg: PipelineConfig
) -> NormalizedValue:
    handler = FIELD_HANDLERS.get(field)
    if handler is None:
        # Unknown field: pass through untouched (KB §18 — never crash on it).
        result = NormResult(rf.value, True)
    else:
        result = handler(str(rf.value), cfg)
    vsource = ValueSource(
        source=source,
        method=rf.method,
        raw=str(rf.value),
        malformed=rf.malformed or not result.ok,
    )
    return NormalizedValue(value=result.value, source=vsource)


def normalize_record(
    record: IntermediateRecord, cfg: PipelineConfig
) -> NormalizedRecord:
    out = NormalizedRecord(source=record.source)
    for field, raw in record.fields.items():
        raw_fields = raw if isinstance(raw, list) else [raw]
        normalized = [
            _normalize_one(field, rf, record.source, cfg) for rf in raw_fields
        ]
        # Drop empty/None scalar normalizations that produced no value.
        normalized = [nv for nv in normalized if nv.value not in (None, "")]
        if normalized:
            out.fields[field] = normalized
    return out
