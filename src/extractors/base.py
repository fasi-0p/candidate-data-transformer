"""Extractor contract and registry.

Adding a new source is "new class + one registration line" (KB §22): subclass
`Extractor`, decorate with `@register("source_type")`, done. No existing module
changes. Extractors emit `IntermediateRecord`s lazily and must never raise out
to the pipeline — a bad input yields fewer records, never a crash (KB §18).
"""

from __future__ import annotations

import abc
from typing import Iterator

from ..models.intermediate import IntermediateRecord

_REGISTRY: dict[str, type["Extractor"]] = {}


def register(source_type: str):
    def deco(cls: type["Extractor"]) -> type["Extractor"]:
        _REGISTRY[source_type] = cls
        return cls
    return deco


def get_extractor(source_type: str) -> "Extractor":
    try:
        cls = _REGISTRY[source_type]
    except KeyError as exc:
        raise ValueError(
            f"No extractor registered for source type {source_type!r}. "
            f"Known: {sorted(_REGISTRY)}"
        ) from exc
    return cls()


def known_sources() -> list[str]:
    return sorted(_REGISTRY)


class Extractor(abc.ABC):
    #: Human-facing source label stamped onto every value's provenance.
    source_label: str = "Unknown"

    @abc.abstractmethod
    def extract(self, path: str) -> Iterator[IntermediateRecord]:
        """Yield one IntermediateRecord per logical candidate in the source."""
        raise NotImplementedError
