"""Confidence scoring (KB §13).

Confidence is computed *only* here, during merge, and stored per field. It is a
separate axis from merge priority: priority decides *who wins*, confidence
describes *how sure we are* (docs/DESIGN.md §4). A high-priority source can still
yield low confidence if its extraction was malformed.
"""

from __future__ import annotations

from ..models.config import (
    AGREEMENT_BONUS,
    CONFLICT_PENALTY,
    MALFORMED_PENALTY,
    PipelineConfig,
)
from ..models.value import clamp_confidence


def score(
    *,
    source: str,
    cfg: PipelineConfig,
    has_agreement: bool,
    has_conflict: bool,
    malformed: bool,
    malformed_penalty: float = MALFORMED_PENALTY,
) -> float:
    value = cfg.base(source)
    if has_agreement:
        value += AGREEMENT_BONUS
    if has_conflict:
        value -= CONFLICT_PENALTY
    if malformed:
        value -= malformed_penalty
    return clamp_confidence(value)
