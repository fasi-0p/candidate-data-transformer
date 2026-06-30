"""Resume PDF extractor.

Two layers, deliberately separated:
- `extract()` does the I/O: opens the PDF with pdfplumber, pulls text page by
  page (streaming, never the whole doc into one buffer), and tolerates a corrupt
  page by skipping it — a damaged resume yields a *partial* profile, never a
  crash (KB §18).
- `parse_resume_text()` is a pure function from text -> IntermediateRecord. All
  the heuristics live here so they can be unit-tested without a real PDF.

Resume is the highest-priority source (90), so on conflict its values win over
CSV/ATS/GitHub while agreements still raise confidence (docs/DESIGN.md §4).
"""

from __future__ import annotations

import re
from typing import Iterator

import pdfplumber

from ..models.intermediate import IntermediateRecord, RawField
from .base import Extractor, register

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://[^\s,;|]+", re.IGNORECASE)
# Bare social URLs without a scheme (resumes often print "github.com/user").
_SOCIAL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:github|linkedin)\.com/[^\s,;|]+", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{7,}\d")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", re.IGNORECASE)

_TITLE_WORDS = ("engineer", "developer", "scientist", "manager", "analyst",
                "designer", "architect", "consultant", "lead", "intern",
                "researcher", "specialist")
_SECTION_WORDS = ("skills", "experience", "education", "projects", "work",
                  "employment", "certifications", "summary", "contact",
                  "achievements", "interests", "languages", "publications")
_SECTION_RE = re.compile(
    r"^\s*(" + "|".join(_SECTION_WORDS) + r")\b.*:?\s*$", re.IGNORECASE)
_SKILL_SPLIT = re.compile(r"[,;•|/]| - ")


@register("resume_pdf")
class ResumeExtractor(Extractor):
    source_label = "Resume"

    def extract(self, path: str) -> Iterator[IntermediateRecord]:
        pages: list[str] = []
        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    try:
                        pages.append(page.extract_text() or "")
                    except Exception:  # noqa: BLE001 — skip a bad page (KB §18)
                        continue
        except Exception:  # noqa: BLE001 — unreadable file -> no records
            return
        text = "\n".join(pages).strip()
        if text:
            yield parse_resume_text(text, source=self.source_label)


def parse_resume_text(text: str, source: str = "Resume") -> IntermediateRecord:
    record = IntermediateRecord(source=source)
    lines = [ln.strip() for ln in text.splitlines()]
    nonempty = [ln for ln in lines if ln]

    _add_contacts(record, text)
    _add_links(record, text)
    name_idx = _add_name(record, nonempty)
    _add_headline(record, nonempty, name_idx)
    _add_location(record, nonempty, name_idx)
    _add_skills(record, lines)
    _add_years(record, text)
    return record


# --- field heuristics ---------------------------------------------------------

def _dedup(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _add_contacts(record: IntermediateRecord, text: str) -> None:
    emails = _dedup(_EMAIL_RE.findall(text))
    if emails:
        record.fields["emails"] = [RawField(e, method="pdf_regex") for e in emails]
    phones = _dedup(
        p.strip() for p in _PHONE_RE.findall(text)
        if sum(ch.isdigit() for ch in p) >= 8)
    if phones:
        record.fields["phones"] = [RawField(p, method="pdf_regex") for p in phones]


def _add_links(record: IntermediateRecord, text: str) -> None:
    urls = _dedup(_URL_RE.findall(text) + _SOCIAL_RE.findall(text))
    if urls:
        record.fields["links"] = [RawField(u, method="pdf_regex") for u in urls]


def _looks_like_name(line: str) -> bool:
    if "@" in line or "," in line or "http" in line.lower():
        return False
    words = line.split()
    if not (1 <= len(words) <= 4):
        return False
    letters = sum(ch.isalpha() for ch in line)
    return letters >= max(3, len(line) - len(words) - 2)


def _add_name(record: IntermediateRecord, nonempty: list[str]) -> int:
    for i, line in enumerate(nonempty[:5]):
        if _SECTION_RE.match(line):
            continue  # skip header-ish lines (e.g. "Contact:"); keep scanning
        if _looks_like_name(line):
            record.fields["full_name"] = RawField(line, method="pdf_text")
            return i
    return -1


def _add_headline(record: IntermediateRecord, nonempty: list[str],
                  name_idx: int) -> None:
    start = name_idx + 1 if name_idx >= 0 else 0
    for line in nonempty[start:start + 4]:
        low = line.lower()
        if "@" in line or _SECTION_RE.match(line):
            continue
        if any(word in low for word in _TITLE_WORDS):
            record.fields["headline"] = RawField(line, method="pdf_text")
            return


def _add_location(record: IntermediateRecord, nonempty: list[str],
                  name_idx: int) -> None:
    start = name_idx + 1 if name_idx >= 0 else 0
    for line in nonempty[start:start + 6]:
        if "@" in line or "http" in line.lower() or _SECTION_RE.match(line):
            continue
        if "," in line and sum(ch.isdigit() for ch in line) <= 2:
            # "City, Country" style header line.
            if any(word in line.lower() for word in _TITLE_WORDS):
                continue
            record.fields["location"] = RawField(line, method="pdf_text")
            return


def _add_skills(record: IntermediateRecord, lines: list[str]) -> None:
    skills: list[str] = []
    in_skills = False
    for line in lines:
        if _SECTION_RE.match(line):
            in_skills = line.lower().lstrip().startswith("skills")
            continue
        if in_skills and line:
            skills.extend(s.strip() for s in _SKILL_SPLIT.split(line) if s.strip())
    skills = _dedup(skills)
    if skills:
        record.fields["skills"] = [
            RawField(s, method="pdf_section") for s in skills]


def _add_years(record: IntermediateRecord, text: str) -> None:
    match = _YEARS_RE.search(text)
    if match:
        record.fields["years_experience"] = RawField(
            match.group(1), method="pdf_regex")
