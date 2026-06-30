"""Generate samples/resume_jane.pdf — a fixture resume for Jane Doe.

Deliberately shares Jane's email + phone with samples/candidates.csv so entity
resolution links the CSV row and this resume into one candidate, exercising
cross-source merge (agreements + conflicts). Run once:

    python scripts/make_sample_resume.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[1] / "samples" / "resume_jane.pdf"

LINES = [
    "Jane Doe",
    "Senior Machine Learning Engineer",
    "Bengaluru, India",
    "jane.doe@gmail.com  |  +91 98765 43210",
    "github.com/janedoe  |  https://linkedin.com/in/janedoe",
    "",
    "Summary",
    "Machine learning engineer with 7 years of experience building NLP systems.",
    "",
    "Skills",
    "Machine Learning, Python, TensorFlow, NLP, PyTorch, Docker",
    "",
    "Experience",
    "Lead ML Engineer, Acme AI (2021-03 to Present)",
    "Built recommendation models serving millions of requests.",
    "",
    "Education",
    "B.Tech Computer Science, BMS College of Engineering (2014 to 2018)",
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=LETTER)
    width, height = LETTER
    y = height - 72
    for line in LINES:
        c.setFont("Helvetica-Bold" if line in {"Jane Doe"} else "Helvetica",
                  16 if line == "Jane Doe" else 11)
        c.drawString(72, y, line)
        y -= 20
    c.showPage()
    c.save()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
