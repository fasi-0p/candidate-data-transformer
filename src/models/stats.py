"""Per-run observability: stage timings and counts.

Makes the engine's efficiency *observable* rather than merely asserted
(docs/DESIGN.md §9.5). Returned alongside the pipeline result and surfaced by
`/api/run` so the demo can show "resolution: 12ms for 5k records".

This is the one deliberately *mutable* model — it is an accumulator, not
canonical data, so it does not need to be frozen.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(slots=True)
class RunStats:
    records_in: int = 0
    clusters_out: int = 0
    conflicts_found: int = 0
    stage_timings_ms: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Time a pipeline stage: `with stats.stage("resolve"): ...`."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            # Accumulate so a stage timed twice sums rather than overwrites.
            self.stage_timings_ms[name] = (
                self.stage_timings_ms.get(name, 0.0) + elapsed_ms)

    @property
    def total_ms(self) -> float:
        return sum(self.stage_timings_ms.values())
