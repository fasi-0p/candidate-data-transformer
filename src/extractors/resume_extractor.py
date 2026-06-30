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
from datetime import date
from typing import Iterator

import pdfplumber

from ..models.canonical import EducationItem
from ..models.intermediate import IntermediateRecord, RawField
from .base import Extractor, register

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://[^\s,;|]+", re.IGNORECASE)
# Bare social URLs without a scheme (resumes often print "github.com/user").
_SOCIAL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:github|linkedin)\.com/[^\s,;|]+", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{7,}\d")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", re.IGNORECASE)

# --- experience date ranges (for summing total tenure) ------------------------
# Resumes rarely state "5 years" outright; the real signal is the date range on
# each role in the Experience section. We parse those ranges and sum the months.
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
           "jul", "aug", "sep", "oct", "nov", "dec")
_MONTH_IDX = {m: i + 1 for i, m in enumerate(_MONTHS)}
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
# One date endpoint, most specific form first so "2021-03" isn't read as "2021".
_DATE_TOKEN = (
    rf"{_MON}\s+\d{{4}}"          # Jan 2020 / January 2020
    r"|\d{4}[/-]\d{1,2}(?!\d)"    # 2021-03  (lookahead: not 2021-2021)
    r"|\d{1,2}[/-]\d{4}(?!\d)"    # 03/2020
    r"|\d{4}(?!\d)"              # 2020
)
_PRESENT = r"present\s*day|present|current|now|ongoing|till\s*date|to\s*date"
_RANGE_SEP = r"\s*(?:--?|–|—|to|until|through|thru)\s*"
_RANGE_RE = re.compile(
    rf"(?<!\d)({_DATE_TOKEN}){_RANGE_SEP}((?:{_DATE_TOKEN})|{_PRESENT})",
    re.IGNORECASE)
# Experience-section headers whose role dates count toward total tenure (Education
# date ranges, e.g. a degree's "2015–2019", must NOT be summed). These match the
# leading word of headers like "Experience", "Work Experience", "Employment History".
_EXPERIENCE_HEADERS = ("experience", "work", "employment")

_TITLE_WORDS = ("engineer", "developer", "scientist", "manager", "analyst",
                "designer", "architect", "consultant", "lead", "intern",
                "researcher", "specialist")
_SECTION_WORDS = ("skills", "experience", "education", "projects", "work",
                  "employment", "certifications", "summary", "contact",
                  "achievements", "interests", "languages", "publications")
_SECTION_RE = re.compile(
    r"^\s*(" + "|".join(_SECTION_WORDS) + r")\b.*:?\s*$", re.IGNORECASE)
_SKILL_SPLIT = re.compile(r"[,;•|/]| - ")
# Skills-section headers vary far more than the generic words above ("Technical
# Skills", "Tech Stack", "Core Competencies", ...); recognize the common variants
# so the skills section is actually found (and not mistaken for a headline).
_SKILL_HEADER_RE = re.compile(
    r"^\s*"
    # Optional qualifier in front of the header word: "Key Skills",
    # "Professional Skills", "Technical Proficiencies", "Software Skills"...
    r"(?:key|core|technical|professional|relevant|additional|other|primary"
    r"|software|computer|it|programming|languages?)?\s*"
    r"(?:technical\s+skills|tech\s+stack|tech\s+skills|core\s+competenc(?:y|ies)"
    r"|core\s+skills|programming\s+languages|skills\s*&?\s*tools"
    r"|tools\s*&?\s*technologies|areas?\s+of\s+expertise|technologies"
    r"|competenc(?:y|ies)|proficienc(?:y|ies)|skill\s*set|skillset|skills)"
    # End of header word -> either end-of-line (bare header) or ": inline values".
    # This accepts "Skills", "Key Skills", "Skills: Python, Go" but rejects a prose
    # line like "Technologies I have used across many roles" (no colon, has prose).
    r"\b(?:\s*:.*)?\s*$", re.IGNORECASE)
# Degree tokens used to pick the degree (vs institution) out of an education line.
_DEGREE_RE = re.compile(
    r"(?<![A-Za-z])(b\.?s|m\.?s|b\.?a|m\.?a|b\.?tech|m\.?tech|b\.?e|m\.?e|b\.?sc"
    r"|m\.?sc|ph\.?d|m\.?phil|mba|bachelor|master|diploma|associate|degree)",
    re.IGNORECASE)
_EDU_HEADER_RE = re.compile(
    r"^\s*(education|academic|qualifications?)\b", re.IGNORECASE)
# A line is *not* a location if it carries a "Label: value" colon or a tech token
# like ".js"/".py"/"socket.io" — these are skills/stack rows ("Frontend: Next.js,
# React") that otherwise look like "City, Country". `\.[a-z]` matches a dotted
# extension but spares real places ("St. Louis" -> dot+space, "U.S.A." -> dot+caps).
_NON_LOCATION_RE = re.compile(r":|\.[a-z]")


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


def parse_resume_text(text: str, source: str = "Resume",
                      today: date | None = None) -> IntermediateRecord:
    """Parse resume text into an IntermediateRecord.

    ``today`` anchors the "Present"/"Current" end of an ongoing role when summing
    experience; it defaults to the current date so live runs reflect real tenure,
    and tests pin it so results stay deterministic.
    """
    record = IntermediateRecord(source=source)
    lines = [ln.strip() for ln in text.splitlines()]
    nonempty = [ln for ln in lines if ln]

    _add_contacts(record, text)
    _add_links(record, text)
    name_idx = _add_name(record, nonempty)
    _add_headline(record, nonempty, name_idx)
    _add_location(record, nonempty, name_idx)
    _add_skills(record, lines)
    _add_education(record, lines)
    _add_years(record, text, lines, today or date.today())
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
        if _looks_like_skill_list(line):
            continue  # a skills/stack summary near the top is not the headline
        if any(word in low for word in _TITLE_WORDS):
            record.fields["headline"] = RawField(line, method="pdf_text")
            return


def _looks_like_skill_list(line: str) -> bool:
    """A real headline is a short role phrase ("Senior ML Engineer"); a skills
    summary is a many-item list ("Java, Python, SQL, AWS, Docker") or carries a
    "Label:" / tech token (".js"). Used to keep skills out of the headline."""
    if _NON_LOCATION_RE.search(line):  # ":" label or ".js"/".py" style token
        return True
    return (line.count(",") + line.count("|")) >= 3


def _add_location(record: IntermediateRecord, nonempty: list[str],
                  name_idx: int) -> None:
    start = name_idx + 1 if name_idx >= 0 else 0
    for line in nonempty[start:start + 6]:
        if "@" in line or "http" in line.lower() or _SECTION_RE.match(line):
            continue
        if _NON_LOCATION_RE.search(line):
            continue  # "Frontend: Next.js, React" and other stack rows — not a place
        if "," in line and sum(ch.isdigit() for ch in line) <= 2:
            # "City, Country" style header line.
            if any(word in line.lower() for word in _TITLE_WORDS):
                continue
            record.fields["location"] = RawField(line, method="pdf_text")
            return


def _section_kind(line: str) -> str | None:
    """Classify a line as a section header: 'skills' for a skills-section header
    (incl. variants like 'Technical Skills'), 'other' for any other section
    header, or None when it is not a header at all."""
    if _SKILL_HEADER_RE.match(line):
        return "skills"
    if _SECTION_RE.match(line):
        return "other"
    return None


def _is_categorized_skill_row(line: str) -> bool:
    """True for a "Category: a, b, c" row — a short label, a colon, then a list.
    These appear inside a skills section ("Languages: Python, Go") but can collide
    with section words ("Languages", "Technologies"), so the skills scanner must
    treat them as content rather than as a new section header."""
    head, sep, rest = line.partition(":")
    return bool(sep and rest.strip() and len(head.split()) <= 3
                and _SKILL_SPLIT.search(rest))


def _strip_skill_label(line: str) -> str:
    """Drop a leading "Category:" label from a categorized skills row so the
    category word isn't stored as a skill. "Languages: Python, Go" -> "Python, Go".
    "Python: 5 years" (not a list) is left untouched so the skill is kept."""
    if _is_categorized_skill_row(line):
        return line.partition(":")[2]
    return line


def _split_skills(text: str) -> list[str]:
    out: list[str] = []
    for part in _SKILL_SPLIT.split(text):
        cleaned = part.strip().strip("-•*▪◦· \t").strip()
        if cleaned:
            out.append(cleaned)
    return out


def _add_skills(record: IntermediateRecord, lines: list[str]) -> None:
    skills: list[str] = []
    in_skills = False
    for line in lines:
        kind = _section_kind(line)
        if kind == "skills":
            in_skills = True
            # "Skills: Python, Go" — values can sit on the header line itself.
            _, _, inline = line.partition(":")
            skills.extend(_split_skills(inline))
            continue
        if kind == "other":
            # A categorized row ("Languages: Python, Go") matches a section word
            # ("languages") yet is really skills content — keep it, don't break.
            if in_skills and _is_categorized_skill_row(line):
                skills.extend(_split_skills(_strip_skill_label(line)))
            else:
                in_skills = False
            continue
        if in_skills and line:
            skills.extend(_split_skills(_strip_skill_label(line)))
    skills = _dedup(skills)
    if skills:
        record.fields["skills"] = [
            RawField(s, method="pdf_section") for s in skills]


def _add_education(record: IntermediateRecord, lines: list[str]) -> None:
    """Collect EducationItems from the Education section. Each non-empty line in
    the section is one entry; its date range (if any) becomes start/end and a
    degree keyword tells the degree apart from the institution."""
    items: list[EducationItem] = []
    in_education = False
    for line in lines:
        if _section_kind(line) is not None or _EDU_HEADER_RE.match(line):
            in_education = bool(_EDU_HEADER_RE.match(line))
            continue
        if in_education and line:
            item = _parse_education_line(line)
            if item.institution or item.degree:
                items.append(item)
    if items:
        record.fields["education"] = [
            RawField(it, method="pdf_section") for it in items]


def _parse_education_line(line: str) -> EducationItem:
    start = end = None
    span = _RANGE_RE.search(line)
    if span:
        lo = _parse_endpoint(span.group(1), date.today())
        hi = _parse_endpoint(span.group(2), date.today())
        if lo:
            start = f"{lo[0]:04d}-{lo[1]:02d}"
        if hi:
            end = f"{hi[0]:04d}-{hi[1]:02d}"
    # Drop the "(...2014 to 2018)" date text, then split into degree/institution.
    text = re.sub(r"\([^)]*\)", " ", line)
    text = _RANGE_RE.sub(" ", text)
    parts = [p.strip(" .") for p in re.split(r",|—|–|\||•| - ", text) if p.strip(" .")]
    degree = institution = field_of_study = None
    for part in parts:
        if degree is None and _DEGREE_RE.search(part):
            degree = part
        elif institution is None:
            institution = part
        elif field_of_study is None:
            field_of_study = part
    return EducationItem(institution=institution, degree=degree,
                         field_of_study=field_of_study, start=start, end=end)


def _add_years(record: IntermediateRecord, text: str, lines: list[str],
               today: date) -> None:
    """Total years of experience. Preferred signal is the sum of role date ranges
    in the Experience section (what resumes actually carry); an explicit
    "N years of experience" phrase is the fallback when no ranges are parseable."""
    months = _sum_experience_months(lines, today)
    if months:
        years = round(months / 12, 1)
        value = str(int(years)) if years == int(years) else str(years)
        record.fields["years_experience"] = RawField(
            value, method="pdf_experience_sum")
        return
    match = _YEARS_RE.search(text)
    if match:
        record.fields["years_experience"] = RawField(
            match.group(1), method="pdf_regex")


def _sum_experience_months(lines: list[str], today: date) -> int | None:
    """Sum the months across every date range inside the Experience section.
    Overlapping ranges (concurrent roles, or a promotion listed twice) are merged
    so time is never double-counted; gaps between roles are not counted. Returns
    None when the section has no parseable date range (caller then falls back)."""
    intervals: list[tuple[int, int]] = []
    in_experience = False
    for line in lines:
        if _SECTION_RE.match(line):
            head = line.lower().lstrip()
            in_experience = head.startswith(_EXPERIENCE_HEADERS)
            continue
        if not in_experience or not line:
            continue
        for m in _RANGE_RE.finditer(line):
            start = _parse_endpoint(m.group(1), today)
            end = _parse_endpoint(m.group(2), today)
            if start and end:
                lo = start[0] * 12 + (start[1] - 1)
                hi = end[0] * 12 + (end[1] - 1)
                if hi >= lo:
                    intervals.append((lo, hi))
    return _merge_months(intervals) if intervals else None


def _parse_endpoint(token: str, today: date) -> tuple[int, int] | None:
    """A single range endpoint -> (year, month). "Present"/"Current" -> today."""
    t = token.strip().lower()
    if re.match(_PRESENT, t):
        return (today.year, today.month)
    named = re.match(rf"({_MON})\s+(\d{{4}})", t)
    if named:
        return (int(named.group(2)), _MONTH_IDX[named.group(1)[:3]])
    nums = re.findall(r"\d+", t)
    if len(nums) == 2:  # YYYY-MM or MM/YYYY, told apart by which side is the year
        a, b = nums
        year, month = (int(a), int(b)) if len(a) == 4 else (int(b), int(a))
        return (year, month) if 1 <= month <= 12 else None
    if len(nums) == 1 and len(nums[0]) == 4:
        return (int(nums[0]), 1)  # year only -> assume January
    return None


def _merge_months(intervals: list[tuple[int, int]]) -> int:
    """Total inclusive months over a set of [start, end] month-index intervals,
    merging any that overlap so concurrent time is counted once."""
    intervals.sort()
    total = 0
    cur_lo, cur_hi = intervals[0]
    for lo, hi in intervals[1:]:
        if lo <= cur_hi:          # overlap -> extend the current span
            cur_hi = max(cur_hi, hi)
        else:
            total += cur_hi - cur_lo + 1
            cur_lo, cur_hi = lo, hi
    return total + (cur_hi - cur_lo + 1)
