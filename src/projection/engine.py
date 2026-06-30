"""Projection engine: canonical model -> output dict per a runtime config.

Reads a frozen `CanonicalCandidate` and builds a *new* dict. It never mutates
canonical data (KB §3, §15). Field selection, rename, confidence/provenance
toggles, and missing-value policy are all driven by `ProjectionConfig` data, so
a new output schema is configuration, not code (docs/DESIGN.md §6).

Path mini-syntax for `FieldMapping.canonical`:
    full_name              scalar field
    emails[0]              one element of a collection
    skills                 whole collection -> list
    location.country       dig into a nested value (Location/Link attribute)
    emails[0].value        index + nested attribute
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from ..models.canonical import CanonicalCandidate
from ..models.config import MissingValuePolicy, ProjectionConfig
from ..models.value import TrackedValue

_PATH_RE = re.compile(r"^(?P<name>\w+)(?:\[(?P<idx>\d+)\])?(?:\.(?P<attr>\w+))?$")

_MISSING = object()


def project(candidate: CanonicalCandidate, config: ProjectionConfig) -> dict:
    out: dict[str, Any] = {}
    for mapping in config.fields:
        rendered = _resolve(candidate, mapping.canonical, config)
        if rendered is _MISSING:
            _apply_missing(out, mapping.out, config.missing_value_policy)
        else:
            out[mapping.out] = rendered
    return out


def _resolve(candidate: CanonicalCandidate, path: str,
             config: ProjectionConfig) -> Any:
    m = _PATH_RE.match(path)
    if not m:
        return _MISSING
    name, idx, attr = m["name"], m["idx"], m["attr"]

    field = getattr(candidate, name, None)
    if field is None:
        return _MISSING

    if isinstance(field, tuple):  # collection
        if idx is not None:
            i = int(idx)
            if i >= len(field):
                return _MISSING
            return _render(field[i], attr, config)
        if not field:
            return _MISSING
        return [_render(tv, attr, config) for tv in field]

    # scalar TrackedValue
    return _render(field, attr, config)


def _render(tv: TrackedValue, attr: str | None,
            config: ProjectionConfig) -> Any:
    value = tv.value
    if attr:
        value = getattr(value, attr, None)
    payload: Any = _jsonable(value)

    if config.include_confidence or config.include_provenance:
        payload = {"value": payload}
        if config.include_confidence:
            payload["confidence"] = round(tv.confidence, 4)
        if config.include_provenance:
            payload["source"] = tv.primary.source
            payload["method"] = tv.primary.method
            payload["sources"] = list(tv.sources)
    return payload


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: v for k, v in dataclasses.asdict(value).items() if v is not None}
    return value


def _apply_missing(out: dict, key: str, policy: MissingValuePolicy) -> None:
    if policy is MissingValuePolicy.OMIT:
        return
    out[key] = None if policy is MissingValuePolicy.NULL else ""
