from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

class AuditStatus(str, Enum):
    PASSED = "passed"
    RISK = "risk"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AuditPeriod:
    start: datetime
    end: datetime
    def contains(self, value: datetime | None) -> bool:
        return bool(value and self.start <= value.astimezone(self.start.tzinfo) < self.end)

@dataclass(frozen=True)
class ProjectCandidate:
    status_page_id: str
    project_id: str
    name: str
    status_url: str
    home_url: str
    year: int = 0
    support_mode: str = ""
    project_status: str = ""
    matching_years: tuple[int, ...] = ()
    space_key: str = ""
    page_identity: str = ""

    @property
    def project_identity(self) -> str:
        return (
            f"{self.space_key}:{self.page_identity}"
            if self.space_key and self.page_identity else self.project_id
        )


@dataclass(frozen=True)
class ConfluenceProject:
    year: int
    project_id: str
    name: str
    status_page_id: str
    status_url: str
    home_url: str
    project_status: str = ""
    current_stage: str = ""
    support_mode: str = ""
    project_owner: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    display_name: str = ""
    matching_years: tuple[int, ...] = ()
    space_key: str = ""
    page_identity: str = ""

    @property
    def project_identity(self) -> str:
        return (
            f"{self.space_key}:{self.page_identity}"
            if self.space_key and self.page_identity else self.project_id
        )


@dataclass(frozen=True)
class ProjectCollectionFilter:
    source_url: str
    years: tuple[int, ...]
    support_modes: tuple[str, ...] = ()
    project_statuses: tuple[str, ...] = ()
    current_stages: tuple[str, ...] = ()
    included_project_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectCollection:
    collection_id: str
    name: str
    filter: ProjectCollectionFilter
    discovered_at: datetime
    projects: tuple[ConfluenceProject, ...]
    excluded_counts: dict[str, int] = field(default_factory=dict)
    visible_years: tuple[int, ...] = ()
    discovery_errors: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditExecutionContext:
    trigger: Literal["manual", "scheduled"]
    plan_id: str = ""

@dataclass(frozen=True)
class AuditFinding:
    project_id: str
    page_title: str
    rule_id: str
    status: AuditStatus
    reason: str
    guidance: str = ""
    page_url: str = ""
    explanation: str = ""

@dataclass
class ProjectAudit:
    project: ProjectCandidate
    findings: list[AuditFinding] = field(default_factory=list)
    @property
    def status(self) -> AuditStatus:
        states = {f.status for f in self.findings}
        return AuditStatus.FAILED if AuditStatus.FAILED in states else (AuditStatus.RISK if AuditStatus.RISK in states else (AuditStatus.UNKNOWN if AuditStatus.UNKNOWN in states else AuditStatus.PASSED))

@dataclass
class AuditBatch:
    id: str
    period: AuditPeriod
    created_at: datetime
    projects: list[ProjectAudit] = field(default_factory=list)
    collection_filter: ProjectCollectionFilter | None = None
    execution_context: AuditExecutionContext = field(
        default_factory=lambda: AuditExecutionContext("manual"),
    )
