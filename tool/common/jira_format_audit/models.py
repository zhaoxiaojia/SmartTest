from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AIReviewStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    COMPLETED = "completed"
    UNCONFIGURED = "unconfigured"
    FAILED = "failed"


@dataclass(frozen=True)
class AuditRule:
    rule_id: str
    section: str
    field: str
    requirement: str
    guidance: str


@dataclass(frozen=True)
class AuditViolation:
    rule_id: str
    section: str
    field: str
    observed: str
    reason: str
    guidance: str


@dataclass(frozen=True)
class IssueAuditResult:
    key: str
    url: str
    summary: str
    creator: str
    passed: bool
    violations: tuple[AuditViolation, ...]
    ai_review_status: AIReviewStatus = AIReviewStatus.NOT_REQUIRED


@dataclass(frozen=True)
class ResolvedAuditInput:
    source_kind: str
    original: str
    jql: str


@dataclass(frozen=True)
class AuditReport:
    resolved: ResolvedAuditInput
    generated_at: datetime
    rules: tuple[AuditRule, ...]
    issues: tuple[IssueAuditResult, ...]

    @property
    def total_count(self) -> int:
        return len(self.issues)

    @property
    def passed_count(self) -> int:
        return sum(issue.passed for issue in self.issues)

    @property
    def failed_count(self) -> int:
        return self.total_count - self.passed_count

    @property
    def violation_count(self) -> int:
        return sum(len(issue.violations) for issue in self.issues)
