"""Diagnose resume extraction on a specific PDF.

    python scripts/diagnose_resume.py path/to/your_resume.pdf

Prints the raw extracted lines (so we can see the actual layout) and what each
heuristic produced (name/headline/location/skills/education), plus which lines
the parser classified as section headers. Share this output to debug a resume
whose fields aren't extracting.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.extractors.resume_extractor import (  # noqa: E402
    _EDU_HEADER_RE, _section_kind, parse_resume_text)


def main(path: str) -> None:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    text = "\n".join(pages).strip()

    print("=" * 70)
    print("RAW EXTRACTED LINES (what the heuristics see)")
    print("=" * 70)
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        tag = ""
        kind = _section_kind(stripped)
        if kind == "skills":
            tag = "  <-- detected: SKILLS header"
        elif _EDU_HEADER_RE.match(stripped):
            tag = "  <-- detected: EDUCATION header"
        elif kind == "other":
            tag = "  <-- detected: section header"
        print(f"{i:3} | {stripped}{tag}")

    print()
    print("=" * 70)
    print("EXTRACTED FIELDS")
    print("=" * 70)
    rec = parse_resume_text(text)

    def show(field):
        raw = rec.fields.get(field)
        if raw is None:
            return "(empty)"
        if isinstance(raw, list):
            return [x.value for x in raw]
        return raw.value

    for f in ("full_name", "headline", "location", "skills",
              "years_experience", "education", "emails", "phones", "links"):
        print(f"{f:18}: {show(f)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/diagnose_resume.py path/to/resume.pdf")
        raise SystemExit(2)
    main(sys.argv[1])
