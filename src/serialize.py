"""Shared JSON serialization for canonical candidates and reports.

Used by both the CLI and the API so the "full canonical dump with provenance"
shape is defined once. This is a *debug/inspection* view (every TrackedValue with
its sources and conflicts) — distinct from the configurable projection output.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .models.canonical import CanonicalCandidate
from .models.value import TrackedValue


def jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: v for k, v in dataclasses.asdict(value).items() if v is not None}
    return value


def tracked_to_dict(tv: TrackedValue | None) -> dict | None:
    if tv is None:
        return None
    out: dict[str, Any] = {
        "value": jsonable(tv.value),
        "confidence": round(tv.confidence, 4),
        "source": tv.primary.source,
        "method": tv.primary.method,
        "sources": list(tv.sources),
    }
    if tv.primary.malformed:
        out["malformed"] = True
    if tv.conflicts:
        out["conflicts"] = [
            {"value": jsonable(c.value), "source": c.source.source,
             "reason": c.reason} for c in tv.conflicts]
    return out


def candidate_to_dict(c: CanonicalCandidate) -> dict:
    return {
        "candidate_id": c.candidate_id,
        "full_name": tracked_to_dict(c.full_name),
        "headline": tracked_to_dict(c.headline),
        "years_experience": tracked_to_dict(c.years_experience),
        "location": tracked_to_dict(c.location),
        "emails": [tracked_to_dict(x) for x in c.emails],
        "phones": [tracked_to_dict(x) for x in c.phones],
        "skills": [tracked_to_dict(x) for x in c.skills],
        "links": [tracked_to_dict(x) for x in c.links],
        "record_confidence": round(c.record_confidence, 4),
    }
