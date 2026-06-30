"""Deterministic identifiers.

`candidate_id` must be reproducible: the same candidate (same strongest stable
identifier) always hashes to the same id, so re-running the pipeline yields
diff-able output (docs/DESIGN.md §5).
"""

from __future__ import annotations

import hashlib
import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    """Lowercase, collapse non-alphanumerics to single hyphens, trim."""
    return _SLUG_RE.sub("-", text.strip().lower()).strip("-")


def candidate_id(
    *,
    email: str | None = None,
    phone: str | None = None,
    name: str | None = None,
    location: str | None = None,
) -> str:
    """Deterministic id from the strongest available identifier.

    Priority mirrors entity-resolution signal strength: email > phone >
    name+location. The chosen key is hashed so ids are uniform and opaque but
    stable.
    """
    if email:
        basis = f"email:{email.strip().lower()}"
    elif phone:
        basis = f"phone:{phone.strip()}"
    elif name:
        basis = f"name:{slug(name)}|loc:{slug(location or '')}"
    else:
        basis = "anonymous"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return digest[:16]
