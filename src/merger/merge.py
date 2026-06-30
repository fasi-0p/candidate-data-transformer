"""Merge engine: a cluster of NormalizedRecords -> one CanonicalCandidate.

Per-field deterministic resolution (docs/DESIGN.md §4):
- **Winner** = max by (source priority, completeness, stable lexicographic
  tiebreak). Never random (KB §11).
- **Agreements** = other inputs whose value equals the winner's (raise conf).
- **Conflicts** = inputs whose value differs (recorded with a reason, lower conf).

Scalars resolve to one `TrackedValue`; collections union-and-dedup, each distinct
value becoming a `TrackedValue` carrying every source that supplied it (KB §9).
All output collections are sorted by a stable key for determinism.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from ..confidence.score import score
from ..models.canonical import CanonicalCandidate, Link, Location
from ..models.config import PipelineConfig
from ..models.normalized import NormalizedRecord, NormalizedValue
from ..models.value import Conflict, TrackedValue, ValueSource
from ..utils.ids import candidate_id

_SCALAR_FIELDS = ("full_name", "headline", "years_experience", "location")
_COLLECTION_FIELDS = ("emails", "phones", "skills", "links")


# --- helpers ------------------------------------------------------------------

def _completeness(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, Location):
        return sum(x is not None for x in (value.city, value.region, value.country))
    if isinstance(value, Link):
        return len(value.url)
    return 1


def _tiebreak(value: Any) -> str:
    return str(value)


def _win_key(nv: NormalizedValue, cfg: PipelineConfig) -> tuple:
    # Higher priority and completeness win; lexicographically smaller raw breaks
    # ties. Negate the "higher wins" terms so plain ascending sort + first works.
    return (
        -cfg.priority(nv.source.source),
        -_completeness(nv.value),
        _tiebreak(nv.value),
    )


def _collect(records: list[NormalizedRecord], field: str) -> list[NormalizedValue]:
    out: list[NormalizedValue] = []
    for rec in records:
        out.extend(rec.values(field))
    return out


def _conflict_reason(loser: NormalizedValue, winner: NormalizedValue,
                     cfg: PipelineConfig) -> str:
    if cfg.priority(loser.source.source) < cfg.priority(winner.source.source):
        return "lower_source_priority"
    if _completeness(loser.value) < _completeness(winner.value):
        return "less_complete"
    return "tiebreak_lost"


# --- scalar merge -------------------------------------------------------------

def _merge_scalar(values: list[NormalizedValue], cfg: PipelineConfig
                  ) -> TrackedValue | None:
    if not values:
        return None
    ordered = sorted(values, key=lambda nv: _win_key(nv, cfg))
    winner = ordered[0]

    agreements = [nv for nv in ordered[1:] if nv.value == winner.value]
    conflicts = [nv for nv in ordered[1:] if nv.value != winner.value]

    confidence = score(
        source=winner.source.source,
        cfg=cfg,
        has_agreement=bool(agreements),
        has_conflict=bool(conflicts),
        malformed=winner.source.malformed,
    )
    return TrackedValue(
        value=winner.value,
        confidence=confidence,
        primary=winner.source,
        agreements=tuple(sorted((a.source for a in agreements),
                                key=ValueSource.sort_key)),
        conflicts=tuple(sorted(
            (Conflict(c.value, c.source, _conflict_reason(c, winner, cfg))
             for c in conflicts),
            key=Conflict.sort_key)),
    )


# --- collection merge ---------------------------------------------------------

def _merge_collection(values: list[NormalizedValue], cfg: PipelineConfig,
                      sort_key: Callable[[Any], Any]
                      ) -> tuple[TrackedValue, ...]:
    # Group by distinct value; within a group all sources agree.
    groups: dict[Any, list[NormalizedValue]] = {}
    for nv in values:
        groups.setdefault(nv.value, []).append(nv)

    tracked: list[TrackedValue] = []
    for value, members in groups.items():
        members.sort(key=lambda nv: _win_key(nv, cfg))
        winner = members[0]
        agreements = members[1:]
        confidence = score(
            source=winner.source.source,
            cfg=cfg,
            has_agreement=bool(agreements),
            has_conflict=False,
            malformed=winner.source.malformed,
        )
        tracked.append(TrackedValue(
            value=value,
            confidence=confidence,
            primary=winner.source,
            agreements=tuple(sorted((a.source for a in agreements),
                                    key=ValueSource.sort_key)),
        ))
    tracked.sort(key=lambda tv: sort_key(tv.value))
    return tuple(tracked)


_COLLECTION_SORT: dict[str, Callable[[Any], Any]] = {
    "emails": lambda v: v,
    "phones": lambda v: v,
    "skills": lambda v: v.lower(),
    "links": lambda v: (v.kind, v.url),
}


# --- public -------------------------------------------------------------------

def merge_cluster(records: list[NormalizedRecord], cfg: PipelineConfig
                  ) -> CanonicalCandidate:
    scalars = {
        field: _merge_scalar(_collect(records, field), cfg)
        for field in _SCALAR_FIELDS
    }
    collections = {
        field: _merge_collection(_collect(records, field), cfg,
                                 _COLLECTION_SORT[field])
        for field in _COLLECTION_FIELDS
    }

    cid = _derive_id(scalars, collections)
    return CanonicalCandidate(
        candidate_id=cid,
        full_name=scalars["full_name"],
        headline=scalars["headline"],
        years_experience=scalars["years_experience"],
        location=scalars["location"],
        emails=collections["emails"],
        phones=collections["phones"],
        skills=collections["skills"],
        links=collections["links"],
    )


def _derive_id(scalars: dict, collections: dict) -> str:
    email = collections["emails"][0].value if collections["emails"] else None
    phone = collections["phones"][0].value if collections["phones"] else None
    name = scalars["full_name"].value if scalars["full_name"] else None
    loc = None
    if scalars["location"]:
        loc = scalars["location"].value.country
    return candidate_id(email=email, phone=phone, name=name, location=loc)


def merge_clusters(clusters: Iterable[list[NormalizedRecord]],
                   cfg: PipelineConfig) -> list[CanonicalCandidate]:
    return [merge_cluster(c, cfg) for c in clusters]
