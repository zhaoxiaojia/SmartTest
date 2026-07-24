from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditRule:
    rule_id: str
    section: str
    field: str
    requirement: str
    guidance: str


@dataclass(frozen=True)
class AuditAttachment:
    filename: str
    size: int


@dataclass(frozen=True)
class AuditIssue:
    key: str
    url: str
    summary: str
    description: str
    reporter: str
    components: tuple[str, ...]
    labels: tuple[str, ...]
    attachments: tuple[AuditAttachment, ...]


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
    reporter: str
    passed: bool
    violations: tuple[AuditViolation, ...]
