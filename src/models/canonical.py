"""The canonical candidate model — the stable internal schema.

Every consumer (validation, projection, UI) reads this shape. It is a tree of
`TrackedValue`s: scalars hold one, collections hold a tuple of them, each element
carrying its own provenance and confidence. There is deliberately no separate
`confidence` or `provenance` field — that information is distributed into the
values themselves (docs/DESIGN.md §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .value import TrackedValue


@dataclass(frozen=True, slots=True)
class Location:
    city: str | None = None
    region: str | None = None
    country: str | None = None  # ISO-3166 alpha-2 (KB §10)


@dataclass(frozen=True, slots=True)
class Link:
    kind: str  # "github", "linkedin", "portfolio", ...
    url: str


@dataclass(frozen=True, slots=True)
class ExperienceItem:
    title: str | None = None
    company: str | None = None
    start: str | None = None  # YYYY-MM (KB §10)
    end: str | None = None    # YYYY-MM or None (present)
    description: str | None = None


@dataclass(frozen=True, slots=True)
class EducationItem:
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start: str | None = None  # YYYY-MM
    end: str | None = None    # YYYY-MM


@dataclass(frozen=True, slots=True)
class CanonicalCandidate:
    """One merged, immutable candidate profile.

    `candidate_id` is a deterministic hash of the strongest stable identifier
    (docs/DESIGN.md §5) so the same inputs always yield the same id.
    """

    candidate_id: str
    full_name: TrackedValue[str] | None = None
    emails: tuple[TrackedValue[str], ...] = field(default=())
    phones: tuple[TrackedValue[str], ...] = field(default=())
    location: TrackedValue[Location] | None = None
    links: tuple[TrackedValue[Link], ...] = field(default=())
    headline: TrackedValue[str] | None = None
    years_experience: TrackedValue[float] | None = None
    skills: tuple[TrackedValue[str], ...] = field(default=())
    experience: tuple[TrackedValue[ExperienceItem], ...] = field(default=())
    education: tuple[TrackedValue[EducationItem], ...] = field(default=())

    @property
    def record_confidence(self) -> float:
        """Derived, never stored — the mean of all field confidences.

        Kept as a computed property so it cannot drift from the underlying
        values it summarizes (docs/DESIGN.md §5).
        """
        scores: list[float] = []
        if self.full_name:
            scores.append(self.full_name.confidence)
        if self.location:
            scores.append(self.location.confidence)
        if self.headline:
            scores.append(self.headline.confidence)
        if self.years_experience:
            scores.append(self.years_experience.confidence)
        for collection in (self.emails, self.phones, self.links,
                           self.skills, self.experience, self.education):
            scores.extend(tv.confidence for tv in collection)
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
