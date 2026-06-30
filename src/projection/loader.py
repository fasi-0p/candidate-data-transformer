"""Load a ProjectionConfig from a YAML/JSON document.

Output schemas live in data files, not code (docs/DESIGN.md §6). Supports the
two `fields` spellings:
    fields:
      - {canonical: full_name, out: candidateName}
      - canonical: emails[0]      # 'out' defaults to the canonical name
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from ..models.config import FieldMapping, MissingValuePolicy, ProjectionConfig


def load_projection(path: str | Path) -> ProjectionConfig:
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)  # YAML is a superset of JSON
    return from_dict(data)


def from_dict(data: dict[str, Any]) -> ProjectionConfig:
    fields = tuple(_field(f) for f in data.get("fields", []))
    policy = MissingValuePolicy(data.get("missing_value_policy", "omit"))
    return ProjectionConfig(
        name=data.get("name", "unnamed"),
        fields=fields,
        include_confidence=bool(data.get("include_confidence", False)),
        include_provenance=bool(data.get("include_provenance", False)),
        missing_value_policy=policy,
    )


def _field(spec: Any) -> FieldMapping:
    canonical = spec["canonical"]
    return FieldMapping(canonical=canonical, out=spec.get("out", canonical))
