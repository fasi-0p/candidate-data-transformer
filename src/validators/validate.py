"""Canonical-record validation (KB §17).

Rule-based by design: Pydantic aborts on the first error and has no notion of a
"warning", which fights the "valid with warnings, never throw" requirement
(docs/DESIGN.md Stage 7). These explicit rules give per-issue severity,
deterministic ordering, and provenance-aware messages.

Checks: email format, E.164 phone format, confidence range, ISO country code,
YYYY-MM dates, duplicate collection values, presence of an id, and a warning for
any value we kept but could not normalize (malformed).
"""

from __future__ import annotations

import re
from typing import Iterator

from ..models.canonical import (CanonicalCandidate, EducationItem,
                               ExperienceItem)
from ..models.value import TrackedValue
from .report import Severity, ValidationReport

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_E164_RE = re.compile(r"^\+\d{7,15}$")
_ALPHA2_RE = re.compile(r"^[A-Z]{2}$")
_YYYY_MM_RE = re.compile(r"^\d{4}-\d{2}$")

_SCALARS = ("full_name", "headline", "years_experience", "location")
_COLLECTIONS = ("emails", "phones", "skills", "links", "experience", "education")


def validate_candidate(c: CanonicalCandidate) -> ValidationReport:
    report = ValidationReport(candidate_id=c.candidate_id)

    if not c.candidate_id:
        report.add("candidate_id", "missing_id", "candidate_id is empty",
                   Severity.ERROR)

    _check_confidence_and_malformed(c, report)
    _check_emails(c, report)
    _check_phones(c, report)
    _check_country(c, report)
    _check_dates(c, report)
    _check_duplicates(c, report)
    return report


def _all_values(c: CanonicalCandidate) -> Iterator[tuple[str, TrackedValue]]:
    for name in _SCALARS:
        tv = getattr(c, name)
        if tv is not None:
            yield name, tv
    for name in _COLLECTIONS:
        for tv in getattr(c, name):
            yield name, tv


def _check_confidence_and_malformed(c: CanonicalCandidate,
                                    report: ValidationReport) -> None:
    for name, tv in _all_values(c):
        if not (0.0 <= tv.confidence <= 1.0):
            report.add(name, "confidence_range",
                       f"confidence {tv.confidence} outside [0, 1]",
                       Severity.ERROR)
        if tv.primary.malformed:
            report.add(name, "malformed",
                       f"value kept but could not be normalized: "
                       f"{tv.primary.raw!r}", Severity.WARNING)


def _check_emails(c: CanonicalCandidate, report: ValidationReport) -> None:
    for tv in c.emails:
        if not _EMAIL_RE.match(str(tv.value)):
            report.add("emails", "email_format",
                       f"invalid email format: {tv.value!r}", Severity.ERROR)


def _check_phones(c: CanonicalCandidate, report: ValidationReport) -> None:
    for tv in c.phones:
        if not _E164_RE.match(str(tv.value)):
            report.add("phones", "phone_format",
                       f"phone not in E.164: {tv.value!r}", Severity.ERROR)


def _check_country(c: CanonicalCandidate, report: ValidationReport) -> None:
    if c.location and c.location.value.country is not None:
        code = c.location.value.country
        if not _ALPHA2_RE.match(code):
            report.add("location", "country_format",
                       f"country not ISO-3166 alpha-2: {code!r}",
                       Severity.WARNING)


def _check_dates(c: CanonicalCandidate, report: ValidationReport) -> None:
    for field_name, items in (("experience", c.experience),
                              ("education", c.education)):
        for tv in items:
            item = tv.value
            for attr in ("start", "end"):
                value = getattr(item, attr, None)
                if value is not None and not _YYYY_MM_RE.match(str(value)):
                    report.add(field_name, "date_format",
                               f"{attr} not YYYY-MM: {value!r}", Severity.ERROR)


def _check_duplicates(c: CanonicalCandidate, report: ValidationReport) -> None:
    for name in ("emails", "phones", "skills"):
        seen: set = set()
        for tv in getattr(c, name):
            if tv.value in seen:
                report.add(name, "duplicate",
                           f"duplicate value: {tv.value!r}", Severity.WARNING)
            seen.add(tv.value)


def validate_all(candidates: list[CanonicalCandidate]) -> list[ValidationReport]:
    return [validate_candidate(c) for c in candidates]
