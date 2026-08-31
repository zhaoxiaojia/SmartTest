from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.confluence.project import ConfluencePageRef, Project


class AuditStatus(str, Enum):
    UPDATED = "updated"
    NOT_UPDATED = "not_updated"
    INVALID_FORMAT = "invalid_format"
    FAILED = "failed"
    UNKNOWN = "unknown"


MISSING_QA = "格式有误：查询不到QA"


@dataclass(frozen=True)
class AuditPeriod:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError("invalid_input")

    def contains(self, value: datetime | None) -> bool:
        return bool(
            value
            and self.start <= value.astimezone(self.start.tzinfo) < self.end
        )


@dataclass(frozen=True)
class ConfluencePageDocument:
    page_id: str
    title: str
    url: str
    body: str
    view_body: str
    version: int
    updated_at: datetime | None


@dataclass(frozen=True)
class AuditFinding:
    project_id: str
    page_title: str
    rule_id: str
    status: AuditStatus
    reason: str
    page_url: str = ""


@dataclass(frozen=True)
class ProjectAudit:
    project: Project
    findings: tuple[AuditFinding, ...]
    owners: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuditBatch:
    id: str
    period: AuditPeriod
    created_at: datetime
    projects: tuple[ProjectAudit, ...]


@dataclass(frozen=True)
class AuditPointMaterial:
    rule_id: str
    page: ConfluencePageRef
    current_region: str
    period_versions: tuple[ConfluencePageDocument, ...]
    changed_regions: tuple[str, ...]


@dataclass(frozen=True)
class ProjectAuditMaterial:
    project: Project
    period: AuditPeriod
    points: tuple[AuditPointMaterial, ...]
