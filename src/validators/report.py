"""Validation report types.

Validation never throws (KB §18, docs/DESIGN.md Stage 7). It returns a
`ValidationReport` — a list of issues, each with a severity — so a record can be
"valid with warnings". `is_valid` means "no ERROR-level issues"; warnings are
informational (e.g. a value we deliberately kept but couldn't normalize).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"  # informational, never affects validity (e.g. a passed check)


@dataclass(frozen=True, slots=True)
class Issue:
    field: str
    code: str
    message: str
    severity: Severity

    def to_dict(self) -> dict:
        return {"field": self.field, "code": self.code,
                "message": self.message, "severity": self.severity.value}


@dataclass(slots=True)
class ValidationReport:
    candidate_id: str
    issues: list[Issue] = field(default_factory=list)

    def add(self, field: str, code: str, message: str,
            severity: Severity) -> None:
        self.issues.append(Issue(field, code, message, severity))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "is_valid": self.is_valid,
            "issues": [i.to_dict() for i in sorted(
                self.issues, key=lambda x: (x.severity.value, x.field, x.code))],
        }
