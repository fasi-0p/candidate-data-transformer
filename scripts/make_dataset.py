"""Generate the resume PDF fixtures in dataset/resumes/.

Covers the unstructured-source aspects and edge cases (KB §18-19):
- a resume that MATCHES a CSV candidate (cross-source merge + conflicts)
- a complete, well-structured resume
- name-only "recruiter note" (fuzzy name merge against CSV)
- messy layout (name not at top, scattered contacts, bullet skills)
- URL-heavy (every link format)
- no skills section
- unicode / international
- corrupted PDF (invalid bytes) and a blank no-text PDF (error handling)

    python scripts/make_dataset.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[1] / "dataset" / "resumes"

RESUMES: dict[str, list[str]] = {
    # Shares email + phone with dataset/csv/10_conflicts_vs_resume.csv (Jordan
    # Blake). Headline and years DISAGREE with the CSV -> conflict resolution
    # (Resume wins, loser recorded), agreements raise confidence on email/phone.
    "jordan_blake_match": [
        "Jordan Blake",
        "Senior Software Engineer",
        "Austin, Texas, United States",
        "jordan.blake@example.com  |  +1 415 555 7788",
        "github.com/jordanblake  |  https://linkedin.com/in/jordanblake  |  https://jordanblake.dev",
        "",
        "Summary",
        "Engineer with 6 years of experience building web platforms.",
        "",
        "Skills",
        "Python, Django, React, PostgreSQL, Docker, AWS",
        "",
        "Experience",
        "Senior Software Engineer, Acme Corp (2020-01 to Present)",
        "",
        "Education",
        "B.S. Computer Science, UT Austin (2014 to 2018)",
    ],
    "alex_morgan_complete": [
        "Alex Morgan",
        "Principal Data Engineer",
        "Seattle, Washington, United States",
        "alex.morgan@example.com  |  alex.morgan@work.example.com  |  +1 206 555 0142",
        "github.com/alexmorgan  |  https://www.linkedin.com/in/alexmorgan/  |  https://alexmorgan.io",
        "",
        "Summary",
        "Data engineer with 11 years of experience across ML and large-scale ETL.",
        "",
        "Skills",
        "ml, python3, k8s, postgres, tensorflow, golang, aws, graphql",
        "",
        "Experience",
        "Principal Data Engineer, BigData Inc (2019-06 to Present)",
        "Staff Engineer, DataWorks (2015-01 to 2019-05)",
        "",
        "Education",
        "M.S. Data Science, University of Washington (2011 to 2013)",
    ],
    # Name-only: matches "Sam Rivera" in 10_conflicts_vs_resume.csv by fuzzy name.
    # The CSV row has an email; this note has none, so the contradiction guard
    # allows the merge.
    "sam_rivera_note": [
        "Sam Rivera",
        "Strong junior developer, available immediately.",
        "Recommended via internal referral.",
    ],
    "robin_fisher_messy": [
        "Contact: reach me at messy.candidate@example.com or backup@example.org",
        "Robin Fisher",
        "Phone +1 312 555 0190 / alt +1 312 555 0191",
        "Senior Cloud Architect, based in Chicago, Illinois",
        "Find me: github.com/robinfisher   linkedin.com/in/robinfisher",
        "",
        "SKILLS",
        "AWS, Kubernetes, Terraform, Go, Python",
        "",
        "WORK",
        "Cloud Architect at Cloudy (2018 to now)",
    ],
    "casey_stone_urls": [
        "Casey Stone",
        "Open Source Developer",
        "Remote",
        "casey.stone@example.com",
        "github.com/caseystone",
        "https://www.github.com/caseystone-alt/",
        "https://linkedin.com/in/caseystone",
        "http://caseystone.dev",
        "https://blog.caseystone.dev/about",
        "",
        "Skills",
        "Rust, WebAssembly, C++, Python",
    ],
    "dana_white_no_skills": [
        "Dana White",
        "Product Designer",
        "Portland, Oregon, United States",
        "dana.white@example.com  |  +1 503 555 0167",
        "https://github.com/danawhite  |  https://linkedin.com/in/danawhite",
        "",
        "Summary",
        "Designer with 9 years of experience in product and UX.",
        "",
        "Experience",
        "Lead Product Designer, DesignCo (2017 to Present)",
    ],
    "jose_muller_unicode": [
        "Jose Muller-Celik",
        "Senior Software Engineer",
        "Sao Paulo, Brazil",
        "jose.muller@example.com.br  |  +55 11 95555 1234",
        "github.com/josemuller  |  https://linkedin.com/in/josemuller",
        "",
        "Skills",
        "Python, Go, Kubernetes",
    ],
}


def render(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=LETTER)
    _, height = LETTER
    y = height - 72
    for i, line in enumerate(lines):
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 16 if i == 0 else 11)
        c.drawString(72, y, line)
        y -= 20
    c.showPage()
    c.save()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, lines in RESUMES.items():
        render(OUT / f"{name}.pdf", lines)

    # Blank PDF: valid file, no extractable text -> extractor yields nothing.
    blank = canvas.Canvas(str(OUT / "blank_no_text.pdf"), pagesize=LETTER)
    blank.showPage()
    blank.save()

    # Corrupted: a .pdf that is not a valid PDF -> extractor returns no records,
    # the pipeline does not crash (KB §18).
    (OUT / "corrupted.pdf").write_bytes(
        b"%PDF-1.4\nthis file is intentionally corrupted and not valid PDF\n%%EOF")

    print(f"wrote {len(RESUMES) + 2} PDFs to {OUT}")


if __name__ == "__main__":
    main()
