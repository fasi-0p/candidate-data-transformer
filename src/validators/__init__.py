"""Validation: rule-based, report-producing, never throwing (KB §17)."""

from .report import Issue, Severity, ValidationReport
from .validate import validate_all, validate_candidate

__all__ = ["Issue", "Severity", "ValidationReport",
           "validate_candidate", "validate_all"]
