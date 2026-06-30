"""Handle verification — cross-checks, not data sources.

A provided **LinkedIn** id (LinkedIn can't be fetched/scraped, KB §4) or **GitHub**
username is verified against the handle a candidate already carries from another
source (typically the resume):

- **match**    -> for LinkedIn, the link gains an agreement-style confidence bonus
                  and an INFO note. (GitHub matches need no bonus — the link merge
                  already rewarded a real agreement.)
- **mismatch** -> the candidate's links of that kind take a confidence penalty and
                  a WARNING is recorded.
- **nothing to compare** -> a neutral INFO note.

Crucially this compares the provided id against the *record's* handle directly, so
it works even when a fetched GitHub profile (often emailless, hence unmerged) lands
in a different candidate than the resume. A GitHub link contributed solely by the
GitHub fetch is excluded from "the record's handle" so it isn't compared to itself.
"""

from __future__ import annotations

from dataclasses import replace

from .models.canonical import CanonicalCandidate
from .models.config import AGREEMENT_BONUS, CONFLICT_PENALTY
from .models.value import ValueSource, clamp_confidence
from .normalizers.fields import normalize_link
from .validators.report import Severity, ValidationReport


def parse_handle(kind: str, raw: str | None) -> str | None:
    """Extract a github/linkedin handle from a URL, or accept a bare handle."""
    text = (raw or "").strip()
    if not text:
        return None
    if f"{kind}.com" in text.lower():
        return normalize_link(text).value.handle
    text = text.strip("/").lower().lstrip("@")
    if kind == "linkedin" and text.startswith(("in/", "pub/")):
        text = text.split("/", 1)[1]
    return text.split("/")[0] or None


def parse_linkedin_handle(linkedin_id: str | None) -> str | None:
    return parse_handle("linkedin", linkedin_id)


def _record_handle(c: CanonicalCandidate, kind: str,
                   exclude_source: str | None) -> str | None:
    """The candidate's handle for ``kind`` to verify against, preferring a
    resume-supplied one and skipping a link contributed *solely* by
    ``exclude_source`` (the verified source's own echo)."""
    fallback: str | None = None
    for tv in c.links:
        if tv.value.kind != kind or not tv.value.handle:
            continue
        sources = set(tv.sources)
        if exclude_source and sources == {exclude_source}:
            continue
        if "Resume" in sources:
            return tv.value.handle.lower()
        if fallback is None:
            fallback = tv.value.handle.lower()
    return fallback


def _verify_kind(candidates: list[CanonicalCandidate],
                 reports: list[ValidationReport], kind: str,
                 provided: set[str], *, exclude_source: str | None,
                 bonus_on_match: bool,
                 verify_label: str | None = None) -> list[CanonicalCandidate]:
    provided = {p.lower() for p in provided if p}
    if not provided:
        return candidates

    # A provided id refers to one person; if it matches some candidate, the
    # others simply aren't the subject — don't flag them.
    matched_any = any((h := _record_handle(c, kind, exclude_source)) and h in provided
                      for c in candidates)
    reports_by_id = {r.candidate_id: r for r in reports}
    shown = sorted(provided)
    out: list[CanonicalCandidate] = []
    for c in candidates:
        report = reports_by_id.get(c.candidate_id)
        handle = _record_handle(c, kind, exclude_source)

        if handle and handle in provided:
            if bonus_on_match:
                if report is not None:
                    report.add("links", f"{kind}_verified",
                               f"{kind} id matches record", Severity.INFO)
                out.append(_mark_verified(c, kind, provided,
                                          verify_label or kind.capitalize()))
            else:
                out.append(c)  # match needs no action (merge already rewarded it)
        elif matched_any:
            out.append(c)
        elif handle is not None:
            if report is not None:
                report.add("links", f"{kind}_mismatch",
                           f"provided {kind} {shown} does not match record "
                           f"{handle!r}", Severity.WARNING)
            out.append(_adjust(c, kind, -CONFLICT_PENALTY))
        else:
            if report is not None:
                report.add("links", f"{kind}_unverified",
                           f"no {kind} handle on record to verify {shown}",
                           Severity.INFO)
            out.append(c)
    return out


def _adjust(c: CanonicalCandidate, kind: str, delta: float) -> CanonicalCandidate:
    """Return a copy with every link of ``kind`` shifted by ``delta`` confidence."""
    links = tuple(tv.with_confidence(tv.confidence + delta)
                  if tv.value.kind == kind else tv for tv in c.links)
    return replace(c, links=links)


def _mark_verified(c: CanonicalCandidate, kind: str, provided: set[str],
                   label: str) -> CanonicalCandidate:
    """On a verified match, bonus the matched link AND record ``label`` as an
    agreeing source, so the inspector shows e.g. "agreed by LinkedIn, Resume"
    (mirroring how a merged GitHub link shows "agreed by GitHub, Resume")."""
    links = []
    for tv in c.links:
        if (tv.value.kind == kind and tv.value.handle
                and tv.value.handle.lower() in provided
                and label not in tv.sources):
            agreement = ValueSource(source=label, method=f"{kind}_verify")
            links.append(replace(
                tv,
                confidence=clamp_confidence(tv.confidence + AGREEMENT_BONUS),
                agreements=tuple(sorted(tv.agreements + (agreement,),
                                        key=ValueSource.sort_key))))
        else:
            links.append(tv)
    return replace(c, links=tuple(links))


def apply_linkedin_verification(candidates: list[CanonicalCandidate],
                                reports: list[ValidationReport],
                                linkedin_id: str | None) -> list[CanonicalCandidate]:
    provided = {parse_handle("linkedin", linkedin_id)} if linkedin_id else set()
    return _verify_kind(candidates, reports, "linkedin", provided,
                        exclude_source=None, bonus_on_match=True,
                        verify_label="LinkedIn")


def apply_github_verification(candidates: list[CanonicalCandidate],
                              reports: list[ValidationReport],
                              github_inputs: list[str]) -> list[CanonicalCandidate]:
    provided = {parse_handle("github", g) for g in github_inputs}
    return _verify_kind(candidates, reports, "github", provided,
                        exclude_source="GitHub", bonus_on_match=False)
