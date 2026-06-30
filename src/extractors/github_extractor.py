"""GitHub profile source.

The assignment lists **GitHub Profile** as an unstructured source, so the input
is a **GitHub profile URL** (e.g. ``https://github.com/octocat``). The extractor:

1. derives the login from the URL,
2. fetches the public GitHub REST profile (``https://api.github.com/users/<login>``)
   — a public API, *not* scraping, and no auth needed, and
3. parses that JSON into an IntermediateRecord.

It also accepts a **local JSON file** of the same shape, which is the
deterministic/offline path (live data can change between runs and unauthenticated
GitHub is rate-limited to 60 req/hr per IP).

Robustness (KB §18, graceful degradation): a failed fetch — rate limit, offline,
404, bad JSON — never raises. We fall back to a minimal record carrying just the
profile link + parsed handle, so the source still contributes identity and the
pipeline keeps running.

Two layers, like the resume extractor:
- ``extract()`` does the I/O (HTTP or file).
- ``parse_github_profile()`` is a pure dict -> IntermediateRecord, unit-testable
  without any network or disk.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Iterator

from ..models.intermediate import IntermediateRecord, RawField
from .base import Extractor, register

_METHOD = "github_api"
_API = "https://api.github.com/users/"
_TIMEOUT = 8.0
# GitHub usernames: 1-39 chars, alphanumeric or single hyphens (no dots/slashes),
# which is exactly what lets us tell a bare handle apart from a file path.
_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


@register("github", "github_json")
class GithubExtractor(Extractor):
    source_label = "GitHub"

    def extract(self, source: str) -> Iterator[IntermediateRecord]:
        clean = source.strip()
        if _is_url(clean):
            yield from self._extract_login(_login_from_url(clean), fallback=clean)
        elif os.path.isfile(clean):
            yield from self._extract_file(clean)
        elif _looks_like_username(clean):
            yield from self._extract_login(clean.lstrip("@"), fallback=None)
        else:
            yield from self._extract_file(clean)

    def _extract_login(self, login: str | None,
                       fallback: str | None) -> Iterator[IntermediateRecord]:
        """Resolve a login (from a URL or a bare username) to a profile record;
        on a failed fetch still contribute the link + handle so identity survives."""
        profile = _fetch_github_profile(login) if login else None
        if profile:
            record = parse_github_profile(profile, source=self.source_label)
        else:
            url = fallback or (f"https://github.com/{login}" if login else "")
            record = _link_only_record(url, source=self.source_label)
        if record.fields:
            yield record

    def _extract_file(self, path: str) -> Iterator[IntermediateRecord]:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):  # missing / not JSON -> no records (KB §18)
            return
        for profile in _iter_profiles(data):
            record = parse_github_profile(profile, source=self.source_label)
            if record.fields:
                yield record


# --- I/O helpers (network) ----------------------------------------------------

def _is_url(source: str) -> bool:
    return source.strip().lower().startswith(("http://", "https://"))


def _looks_like_username(source: str) -> bool:
    """A bare GitHub handle (optionally @-prefixed) — never a path or filename."""
    return bool(_USERNAME_RE.match(source.lstrip("@")))


def login_for_verification(source: str) -> str | None:
    """The GitHub login a ``github`` source identifies (from a URL or a bare
    username), or None for a local JSON file — which is data, not a verify id."""
    clean = source.strip()
    if _is_url(clean):
        return _login_from_url(clean)
    if not os.path.isfile(clean) and _looks_like_username(clean):
        return clean.lstrip("@")
    return None


def _login_from_url(url: str) -> str | None:
    """First path segment of a github.com URL is the user/org login."""
    cleaned = url.strip().rstrip("/")
    marker = "github.com/"
    idx = cleaned.lower().find(marker)
    if idx == -1:
        return None
    rest = cleaned[idx + len(marker):]
    if not rest:
        return None
    login = rest.split("/")[0].split("?")[0].split("#")[0]
    return login or None


def _fetch_github_profile(login: str) -> dict | None:
    """GET the public GitHub user profile. Returns None on any failure so the
    caller can degrade gracefully (KB §18). Isolated here so tests can patch it."""
    req = urllib.request.Request(
        f"{_API}{login}",
        headers={"User-Agent": "candidate-data-transformer",
                 "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    return data if isinstance(data, dict) and data.get("login") else None


# --- pure parsing -------------------------------------------------------------

def _iter_profiles(data: Any) -> Iterator[dict]:
    """Accept either one profile object or a list of them (local file path)."""
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
    elif isinstance(data, dict):
        yield data


def parse_github_profile(profile: dict, source: str = "GitHub") -> IntermediateRecord:
    record = IntermediateRecord(source=source)

    name = _clean(profile.get("name"))
    if name:
        record.fields["full_name"] = RawField(name, method=_METHOD)

    email = _clean(profile.get("email"))
    if email:
        record.fields["emails"] = [RawField(email, method=_METHOD)]

    location = _clean(profile.get("location"))
    if location:
        record.fields["location"] = RawField(location, method=_METHOD)

    links = _collect_links(profile)
    if links:
        record.fields["links"] = [RawField(u, method=_METHOD) for u in links]

    skills = _collect_skills(profile)
    if skills:
        record.fields["skills"] = [RawField(s, method=_METHOD) for s in skills]

    return record


def _link_only_record(url: str, source: str) -> IntermediateRecord:
    """Minimal record when profile data can't be fetched: just the link (the
    normalizer parses its handle). Identity without invented data (Principle 1)."""
    record = IntermediateRecord(source=source)
    record.fields["links"] = [RawField(url.strip(), method="github_url")]
    return record


def _collect_links(profile: dict) -> list[str]:
    """Profile/blog URLs, plus a github.com URL synthesized from `login` when the
    profile omits `html_url`. Order-preserving dedup keeps output deterministic."""
    urls: list[str] = []
    html_url = _clean(profile.get("html_url"))
    if html_url:
        urls.append(html_url)
    login = _clean(profile.get("login"))
    if login and not html_url:
        urls.append(f"https://github.com/{login}")
    blog = _clean(profile.get("blog"))
    if blog:
        urls.append(blog)
    return _dedup(urls)


def _collect_skills(profile: dict) -> list[str]:
    """`top_languages` plus any languages on pinned repos — both are real skill
    signal. Deduped (order-preserving) so merge sees each language once."""
    skills: list[str] = []
    for lang in profile.get("top_languages") or []:
        if cleaned := _clean(lang):
            skills.append(cleaned)
    for repo in profile.get("pinned_repos") or []:
        if isinstance(repo, dict) and (cleaned := _clean(repo.get("language"))):
            skills.append(cleaned)
    return _dedup(skills)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedup(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
