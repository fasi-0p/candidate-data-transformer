"""ATS JSON source.

The assignment lists **ATS JSON** as a structured source (priority 85). An ATS
export is a JSON blob with a ``candidates`` array (or a single candidate object);
each entry uses ATS-style camelCase keys that we map onto the canonical field
names. Nested ``location`` and ``links`` objects are flattened.

Two layers, like the other extractors:
- ``extract()`` does the I/O (opens and json-parses the file).
- ``parse_ats_candidate()`` is a pure dict -> IntermediateRecord, unit-testable
  without disk.

Robustness (KB §18): a missing file or invalid JSON yields *no records* rather
than raising, so one bad export never crashes the pipeline.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

from ..models.intermediate import IntermediateRecord, RawField
from .base import Extractor, register

_METHOD = "ats_json"


@register("ats_json", "ats")
class AtsExtractor(Extractor):
    source_label = "ATS"

    def extract(self, path: str) -> Iterator[IntermediateRecord]:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):  # missing / not JSON -> no records (KB §18)
            return
        for candidate in _iter_candidates(data):
            record = parse_ats_candidate(candidate, source=self.source_label)
            if record.fields:
                yield record


# --- pure parsing -------------------------------------------------------------

def _iter_candidates(data: Any) -> Iterator[dict]:
    """Accept ``{"candidates": [...]}``, a bare list, or a single object."""
    if isinstance(data, dict) and isinstance(data.get("candidates"), list):
        items: Any = data["candidates"]
    elif isinstance(data, list):
        items = data
    else:
        items = [data]
    for item in items:
        if isinstance(item, dict):
            yield item


def parse_ats_candidate(candidate: dict, source: str = "ATS") -> IntermediateRecord:
    record = IntermediateRecord(source=source)

    name = _clean(candidate.get("fullName") or candidate.get("name"))
    if name:
        record.fields["full_name"] = RawField(name, method=_METHOD)

    title = _clean(candidate.get("currentTitle") or candidate.get("title")
                   or candidate.get("headline"))
    if title:
        record.fields["headline"] = RawField(title, method=_METHOD)

    years = candidate.get("yearsExperience", candidate.get("years_experience"))
    if years is not None and _clean(str(years)):
        record.fields["years_experience"] = RawField(str(years), method=_METHOD)

    email = _clean(candidate.get("email"))
    if email:
        record.fields["emails"] = [RawField(email, method=_METHOD)]

    phone = _clean(candidate.get("phone"))
    if phone:
        record.fields["phones"] = [RawField(phone, method=_METHOD)]

    location = _format_location(candidate.get("location"))
    if location:
        record.fields["location"] = RawField(location, method=_METHOD)

    skills = [s for s in (_clean(x) for x in candidate.get("skills") or []) if s]
    if skills:
        record.fields["skills"] = [RawField(s, method=_METHOD) for s in skills]

    links = _collect_links(candidate.get("links"))
    if links:
        record.fields["links"] = [RawField(u, method=_METHOD) for u in links]

    return record


def _format_location(loc: Any) -> str | None:
    """Flatten a ``{city, region, country}`` object (or a plain string) into the
    "City, Region, Country" form the location normalizer parses."""
    if isinstance(loc, str):
        return _clean(loc)
    if isinstance(loc, dict):
        parts = [_clean(loc.get(k)) for k in ("city", "region", "state", "country")]
        joined = ", ".join(p for p in parts if p)
        return joined or None
    return None


def _collect_links(links: Any) -> list[str]:
    """Links may be a ``{github: url, linkedin: url}`` map or a list of urls."""
    out: list[str] = []
    if isinstance(links, dict):
        values = links.values()
    elif isinstance(links, list):
        values = links
    else:
        return out
    seen: set[str] = set()
    for v in values:
        url = _clean(v)
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
