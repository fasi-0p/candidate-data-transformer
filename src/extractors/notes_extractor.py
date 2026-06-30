"""Recruiter notes source (plain-text).

A recruiter ``.txt`` holds one or more candidates. Two layouts are supported, per
block (blocks are separated by a ``---``/``===`` rule line, or by blank lines):

1. **Structured** — ``Field: value`` lines (``Name:``, ``Email:``, ``Skills:`` …).
   Reliable, so it's tried first.
2. **Prose** — free recruiter text; if a block has no recognizable ``Field:``
   lines we fall back to regex/heuristics (name, emails, phones, a title-ish
   headline, best-effort skills), like the resume parser.

This is a low-trust source (priority 60): its real value is **cross-verification**
— its name/email/phone agreeing or conflicting with CSV/ATS/Resume moves the
confidence score through the normal merge agreement/conflict machinery (KB §13).

``extract()`` does the file I/O; ``parse_notes_text()`` is the pure core. A bad or
missing file yields no records, never a crash (KB §18).
"""

from __future__ import annotations

import re
from typing import Iterator

from ..models.intermediate import IntermediateRecord, RawField
from .base import Extractor, register

_METHOD = "note_text"
_SOURCE = "Recruiter Note"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{7,}\d")
_DELIM_RE = re.compile(r"^\s*[-=_*~]{3,}\s*$")
_KV_RE = re.compile(r"^\s*([A-Za-z][A-Za-z /&_-]*?)\s*:\s*(.+?)\s*$")
_VALUE_SPLIT = re.compile(r"[,;]")

_TITLE_WORDS = ("engineer", "developer", "scientist", "manager", "analyst",
                "designer", "architect", "consultant", "lead", "intern",
                "researcher", "specialist", "dev")
# Capitalized filler that must not be mistaken for a name in prose.
_NAME_FILLER = {"spoke", "talked", "met", "with", "re", "note", "notes", "and",
                "candidate", "referral", "recommended", "via", "internal",
                "strong", "junior", "senior", "available", "contact", "phone",
                "email", "the", "a", "an"}
# Words that mark a prose token as not-a-skill.
_SKILL_STOP = {"available", "immediately", "now", "strong", "junior", "senior",
               "mid", "solid", "great", "good", "dev", "developer", "engineer",
               "years", "year", "yrs", "yr", "experience", "recommended",
               "referral", "backend", "frontend", "fullstack", "full-stack",
               "based"}

# Recruiter label -> canonical field name.
_FIELD_KEYS: dict[str, str] = {
    "name": "full_name", "full name": "full_name", "candidate": "full_name",
    "email": "emails", "e-mail": "emails", "emails": "emails",
    "phone": "phones", "mobile": "phones", "phones": "phones", "tel": "phones",
    "title": "headline", "headline": "headline", "role": "headline",
    "position": "headline", "current title": "headline",
    "years": "years_experience", "yoe": "years_experience",
    "years of experience": "years_experience", "experience": "years_experience",
    "skills": "skills", "skillset": "skills", "tech": "skills",
    "location": "location", "based in": "location", "city": "location",
    "github": "links", "linkedin": "links", "links": "links",
    "url": "links", "portfolio": "links", "website": "links",
}


@register("notes", "recruiter_notes")
class NotesExtractor(Extractor):
    source_label = _SOURCE

    def extract(self, path: str) -> Iterator[IntermediateRecord]:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:  # missing / unreadable -> no records (KB §18)
            return
        yield from parse_notes_text(text, source=self.source_label)


# --- pure parsing -------------------------------------------------------------

def parse_notes_text(text: str, source: str = _SOURCE) -> Iterator[IntermediateRecord]:
    for block in _split_blocks(text):
        record = _parse_block(block, source)
        if record.fields:
            yield record


def _split_blocks(text: str) -> list[list[str]]:
    """One candidate per block. Prefer explicit rule lines ('---'); if there are
    none, fall back to blank-line separation."""
    lines = text.splitlines()
    has_delim = any(_DELIM_RE.match(ln) for ln in lines)
    blocks: list[list[str]] = []
    current: list[str] = []
    for ln in lines:
        is_break = _DELIM_RE.match(ln) if has_delim else (ln.strip() == "")
        if is_break:
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(ln)
    if current:
        blocks.append(current)
    return [b for b in blocks if any(l.strip() for l in b)]


def _parse_block(lines: list[str], source: str) -> IntermediateRecord:
    record = IntermediateRecord(source=source)
    recognized = False
    for line in lines:
        m = _KV_RE.match(line)
        if not m:
            continue
        field = _FIELD_KEYS.get(m.group(1).strip().lower())
        if field:
            recognized = True
            _assign(record, field, m.group(1).strip().lower(), m.group(2).strip())
    if recognized:
        return record
    return _parse_prose(lines, record)


def _assign(record: IntermediateRecord, field: str, key: str, value: str) -> None:
    if field in ("full_name", "headline", "location", "years_experience"):
        record.fields.setdefault(field, RawField(value, method=_METHOD))
    elif field in ("emails", "phones", "skills"):
        parts = [p.strip() for p in _VALUE_SPLIT.split(value) if p.strip()]
        bucket = record.fields.setdefault(field, [])
        bucket.extend(RawField(p, method=_METHOD) for p in parts)
    elif field == "links":
        bucket = record.fields.setdefault("links", [])
        bucket.extend(RawField(u, method=_METHOD) for u in _link_values(key, value))


def _link_values(key: str, value: str) -> list[str]:
    """Turn a github/linkedin label value into a usable URL: a bare handle gets
    its host synthesized so the link normalizer can parse it."""
    out: list[str] = []
    for part in re.split(r"[,\s]+", value):
        part = part.strip()
        if not part:
            continue
        low = part.lower()
        if key == "github" and "github.com" not in low:
            part = f"github.com/{part.lstrip('@/')}"
        elif key == "linkedin" and "linkedin.com" not in low:
            part = f"linkedin.com/in/{part.lstrip('@/')}"
        out.append(part)
    return out


# --- prose fallback -----------------------------------------------------------

def _parse_prose(lines: list[str], record: IntermediateRecord) -> IntermediateRecord:
    text = " ".join(l.strip() for l in lines if l.strip())

    emails = _dedup(_EMAIL_RE.findall(text))
    if emails:
        record.fields["emails"] = [RawField(e, method=_METHOD) for e in emails]
    phones = _dedup(p.strip() for p in _PHONE_RE.findall(text)
                    if sum(ch.isdigit() for ch in p) >= 8)
    if phones:
        record.fields["phones"] = [RawField(p, method=_METHOD) for p in phones]

    name = _prose_name(text)
    if name:
        record.fields["full_name"] = RawField(name, method=_METHOD)
    headline = _prose_headline(text)
    if headline:
        record.fields["headline"] = RawField(headline, method=_METHOD)

    skills = _prose_skills(text, exclude=set(emails) | ({name} if name else set()))
    if skills:
        record.fields["skills"] = [RawField(s, method=_METHOD) for s in skills]
    return record


def _prose_name(text: str) -> str | None:
    """First run of >=2 capitalized words that aren't filler ('Spoke with ...')."""
    run: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z.'\-]*", text):
        if re.match(r"^[A-Z][a-z.'\-]+$", token) and token.lower() not in _NAME_FILLER:
            run.append(token)
            if len(run) == 4:
                break
        else:
            if len(run) >= 2:
                break
            run = []
    return " ".join(run) if len(run) >= 2 else None


def _prose_headline(text: str) -> str | None:
    """A short clause that mentions a job-title word (split on dashes too so the
    leading name doesn't get glued onto the headline)."""
    for clause in re.split(r"[,.;()\-]", text):
        words = clause.strip()
        low = words.lower()
        if words and any(w in low for w in _TITLE_WORDS) and len(words.split()) <= 6:
            return words
    return None


def _prose_skills(text: str, exclude: set[str]) -> list[str]:
    """Best-effort: comma/&/slash-separated tokens that look like skills (not
    filler, not the name/email, not a contact string)."""
    out: list[str] = []
    excl_low = {e.lower() for e in exclude}
    for token in re.split(r"[,;&/]| - | and ", text):
        token = token.strip(" .-~")
        low = token.lower()
        has_digit = any(ch.isdigit() for ch in token)
        if (not token or "@" in token or low in excl_low
                or len(token.split()) > 2
                or (has_digit and len(token.split()) > 1)):  # "5 yrs", "2 years"
            continue
        if any(w in _SKILL_STOP for w in low.split()):
            continue
        out.append(token)
    return _dedup(out)


def _dedup(seq) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
