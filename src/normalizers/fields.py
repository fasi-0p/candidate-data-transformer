"""Per-field normalizers.

Each returns a `NormResult(value, ok)`:
- `ok=True`  -> value is the canonical, normalized form.
- `ok=False` -> value could not be fully parsed; we return the cleaned original
  and flag it malformed (drives the -0.20 confidence penalty, KB §13). We record
  that we could not normalize rather than silently dropping the value.

Regexes are compiled once at module load; library lookups are memoized
(docs/DESIGN.md §9.3).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import phonenumbers
import pycountry
from dateutil import parser as date_parser

from ..models.canonical import Link, Location

_DATA_DIR = Path(__file__).parent / "data"
# RFC-5322-lite: good enough for validation without false rejects.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class NormResult:
    value: Any
    ok: bool


# --- email --------------------------------------------------------------------

def normalize_email(raw: str) -> NormResult:
    cleaned = raw.strip().lower()
    return NormResult(cleaned, bool(_EMAIL_RE.match(cleaned)))


# --- phone --------------------------------------------------------------------

def normalize_phone(raw: str, region: str = "IN") -> NormResult:
    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return NormResult(raw.strip(), False)
    if not phonenumbers.is_valid_number(parsed):
        return NormResult(raw.strip(), False)
    e164 = phonenumbers.format_number(
        parsed, phonenumbers.PhoneNumberFormat.E164)
    return NormResult(e164, True)


# --- date ---------------------------------------------------------------------

def normalize_date(raw: str) -> NormResult:
    """Parse a fuzzy date to YYYY-MM (KB §10). Day precision is intentionally
    dropped — the canonical granularity is month."""
    text = raw.strip()
    if not text or text.lower() in {"present", "current", "now"}:
        return NormResult(None, text.lower() in {"present", "current", "now"})
    try:
        dt = date_parser.parse(text, default=date_parser.parse("2000-01-01"))
    except (ValueError, OverflowError):
        return NormResult(text, False)
    return NormResult(f"{dt.year:04d}-{dt.month:02d}", True)


# --- country ------------------------------------------------------------------

@lru_cache(maxsize=512)
def _lookup_country(token: str) -> str | None:
    token = token.strip()
    if not token:
        return None
    # Already an alpha-2 code?
    if len(token) == 2 and token.isalpha():
        rec = pycountry.countries.get(alpha_2=token.upper())
        if rec:
            return rec.alpha_2
    try:
        matches = pycountry.countries.search_fuzzy(token)
    except LookupError:
        return None
    return matches[0].alpha_2 if matches else None


def normalize_country(raw: str) -> NormResult:
    code = _lookup_country(raw)
    return NormResult(code, code is not None) if code else NormResult(
        raw.strip(), False)


# --- skill --------------------------------------------------------------------

@lru_cache(maxsize=1)
def _skill_aliases() -> dict[str, str]:
    path = _DATA_DIR / "skill_aliases.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# A real skill is short and word-like ("Rust", "Amazon Web Services"). A stray
# number, a sentence, or an overlong blob extracted as a "skill" is wrong/noisy
# information — we keep it (never drop) but flag it malformed so it is penalized
# and surfaced, without rejecting legitimate skills we simply don't recognize.
_MAX_SKILL_WORDS = 4
_MAX_SKILL_LEN = 40


def _is_plausible_skill(text: str) -> bool:
    if len(text) > _MAX_SKILL_LEN:
        return False
    if len(text.split()) > _MAX_SKILL_WORDS:
        return False
    return any(ch.isalpha() for ch in text)  # must contain a letter, not just digits


def normalize_skill(raw: str) -> NormResult:
    """Map a skill alias to its canonical name (KB §10). A recognized alias is
    always valid. An unrecognized token is kept (a real skill we don't know is
    still a skill) but flagged malformed when it doesn't look like a skill at
    all — that signals wrong/inconsistent skill data, which is penalized."""
    key = raw.strip().lower()
    if not key:
        return NormResult(raw.strip(), False)
    canonical = _skill_aliases().get(key)
    if canonical:
        return NormResult(canonical, True)
    cleaned = raw.strip()
    return NormResult(cleaned, _is_plausible_skill(cleaned))


# --- plain text ---------------------------------------------------------------

def normalize_name(raw: str) -> NormResult:
    cleaned = " ".join(raw.split())  # collapse internal whitespace
    return NormResult(cleaned, bool(cleaned))


# --- years of experience ------------------------------------------------------

_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)")


def normalize_years(raw: str) -> NormResult:
    match = _YEARS_RE.search(raw)
    if not match:
        return NormResult(raw.strip(), False)
    return NormResult(float(match.group(1)), True)


# --- location -----------------------------------------------------------------

@lru_cache(maxsize=1)
def _city_aliases() -> dict[str, str]:
    path = _DATA_DIR / "city_aliases.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _canonical_city(name: str | None) -> str | None:
    """Map a city alias to its canonical name (e.g. "Bangalore" -> "Bengaluru")
    so the same city from different sources merges instead of conflicting."""
    if not name:
        return name
    cleaned = name.strip()
    return _city_aliases().get(cleaned.lower(), cleaned)


def normalize_location(raw: str) -> NormResult:
    """Parse "City, Region, Country" loosely. The last comma-part is treated as
    the country and normalized to ISO alpha-2; earlier parts fill city/region.
    The city is canonicalized through a small alias map (Bangalore -> Bengaluru)."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return NormResult(Location(), False)
    country_code = None
    if len(parts) >= 1:
        country_code = _lookup_country(parts[-1])
    city = _canonical_city(parts[0]) if len(parts) >= 2 or country_code is None else None
    region = parts[1] if len(parts) >= 3 else None
    if country_code is not None and len(parts) >= 2:
        loc = Location(city=city, region=region, country=country_code)
    elif country_code is not None:
        loc = Location(country=country_code)
    else:
        loc = Location(city=city, region=region)
    ok = country_code is not None or bool(city)
    return NormResult(loc, ok)


# --- link ---------------------------------------------------------------------

_URL_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)


def _canonical_url(url: str) -> str:
    """Canonical form so the same link from different sources merges: drop
    scheme and leading www., strip a trailing slash, lowercase the whole thing
    (paths on github/linkedin are case-insensitive in practice)."""
    cleaned = _URL_SCHEME_RE.sub("", url.strip())
    if cleaned.lower().startswith("www."):
        cleaned = cleaned[4:]
    return cleaned.rstrip("/").lower()


def _parse_handle(kind: str, canonical_url: str) -> str | None:
    """Pull the username out of a canonicalized github/linkedin URL.

    GitHub: the first path segment is the user/org (``github.com/<handle>``).
    LinkedIn: the segment after ``/in/`` or ``/pub/`` (``linkedin.com/in/<handle>``).
    Returns None when the URL is just the bare host or has no recognizable handle
    (we never invent one — KB §3, Principle 1).
    """
    segments = [s for s in canonical_url.split("/") if s]
    path = segments[1:]  # drop the host
    if kind == "github":
        return path[0] if path else None
    if kind == "linkedin":
        for i, seg in enumerate(path):
            if seg in ("in", "pub") and i + 1 < len(path):
                return path[i + 1]
    return None


def normalize_link(raw: str) -> NormResult:
    """Infer link kind from the URL host, canonicalize the URL so identical links
    from different sources deduplicate on merge, and parse the github/linkedin
    handle out of the path (KB has GitHub/LinkedIn)."""
    url = raw.strip()
    if not url:
        return NormResult(Link(kind="unknown", url=url), False)
    low = url.lower()
    if "github.com" in low:
        kind = "github"
    elif "linkedin.com" in low:
        kind = "linkedin"
    elif low.startswith("http"):
        kind = "portfolio"
    else:
        kind = "unknown"
    canonical = _canonical_url(url)
    return NormResult(
        Link(kind=kind, url=canonical, handle=_parse_handle(kind, canonical)),
        kind != "unknown",
    )
