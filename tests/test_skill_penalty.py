"""Skill data quality penalty, and the rule that collection multiplicity
(several phones/skills) is never itself penalized.

- A "skill" that is really sentence-shaped noise or a stray number is kept but
  penalized harder than a generic malformed field (it is the main match signal).
- Having multiple valid phone numbers does not lower any phone's confidence.
"""

import os
import tempfile

from src.models.config import (MALFORMED_PENALTY, SKILL_MALFORMED_PENALTY,
                                PipelineConfig)
from src.pipeline import Source, run


def _note(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _skill(c, value):
    return next(tv for tv in c.skills if tv.value == value)


def test_noisy_skill_penalized_harder_than_generic():
    path = _note("Name: Sara Lin\nEmail: sara@x.com\n"
                 "Skills: Python, I am proficient in many languages\n")
    res = run([Source("notes", path)])
    c = res.candidates[0]

    clean = _skill(c, "Python")
    noisy = _skill(c, "I am proficient in many languages")

    assert noisy.primary.malformed is True
    assert clean.primary.malformed is False
    # The noisy skill is docked the (larger) skill penalty, not the generic one.
    base = PipelineConfig().base("Recruiter Note")
    assert noisy.confidence == base - SKILL_MALFORMED_PENALTY
    assert clean.confidence == base
    assert SKILL_MALFORMED_PENALTY > MALFORMED_PENALTY
    assert noisy.confidence < clean.confidence
    # A profile carrying wrong skill data scores lower overall.
    assert c.record_confidence < clean.confidence


def test_multiple_phones_not_penalized():
    path = _note("Name: Two Phones\nEmail: tp@x.com\nSkills: Python\n"
                 "Phone: 9876543210\nPhone: 9988776655\n")
    res = run([Source("notes", path)])
    c = res.candidates[0]

    assert len(c.phones) == 2
    base = PipelineConfig().base("Recruiter Note")
    # Each valid phone keeps full base confidence — multiplicity costs nothing.
    for tv in c.phones:
        assert tv.primary.malformed is False
        assert tv.confidence == base
