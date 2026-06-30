"""Ephemeral in-process store of pipeline runs.

Lets `POST /api/project` re-project a previous run's canonical candidates
*without re-running the pipeline* — which is exactly what demonstrates that
projection is pure and canonical data is frozen (docs/DESIGN.md §8). Intentionally
in-memory and capped (no DB — KB §4 puts persistence out of scope); runs evict
FIFO and vanish on restart.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict

from ..models.canonical import CanonicalCandidate

_MAX_RUNS = 50
_RUNS: "OrderedDict[str, list[CanonicalCandidate]]" = OrderedDict()


def put(candidates: list[CanonicalCandidate]) -> str:
    run_id = uuid.uuid4().hex[:12]
    _RUNS[run_id] = candidates
    while len(_RUNS) > _MAX_RUNS:
        _RUNS.popitem(last=False)  # evict oldest
    return run_id


def get(run_id: str) -> list[CanonicalCandidate] | None:
    return _RUNS.get(run_id)
