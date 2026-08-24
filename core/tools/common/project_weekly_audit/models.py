from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

class AuditStatus(str, Enum):
    UPDATED = "updated"
    NOT_UPDATED = "not_updated"
    INVALID_FORMAT = "invalid_format"
    PASSED = "passed"
    RISK = "risk"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AuditAttentionPoint:
    rule_id: str
    page_kind: str
    label: str
    standard_name: str
    heading_names: tuple[str, ...] = ()
    table_fields: tuple[str, ...] = ()
    use_page_body: bool = False
    table_region_fields: tuple[str, ...] = ()
    heading_boundary: Literal["sibling", "page_end"] = "sibling"


UPDATE_MATRIX_POINTS = (
    AuditAttentionPoint(
        "status.highlights", "status", "Project Status Report.Highlights",
        "Highlights",
        ("Highlights",),
    ),
    AuditAttentionPoint(
        "status.impact", "status", "Project Status Report.Impact issues",
        "Impact", ("Impact",),
    ),
    AuditAttentionPoint(
        "test.weekly", "test_information",
        "Basic Information.Test Information.Phase Status（当前阶段测试状态）",
        "Phase Status",
        ("Phase Status", "Software Testing Status"),
        ("Phase Status",),
    ),
    AuditAttentionPoint(
        "test.summary", "test_information",
        "Basic Information.Test Information.项目整体状态Summary",
        "Summary",
        ("Summary",), ("Summary",),
    ),
    AuditAttentionPoint(
        "test.tasks", "test_information",
        "Basic Information.Test Information.Task Arrangement of Important Test（Must give ETA）",
        "Task Arrangement",
        ("Task Arrangement",),
        ("Task Arrangement",),
    ),
    AuditAttentionPoint(
        "test.blocking", "test_information",
        "Basic Information.Test Information.Blocking QA Testing Items",
        "Blocking",
        ("Blocking",),
    ),
    AuditAttentionPoint(
        "plan.test", "test_plan",
        "Basic Information.Test Information.Test Plan.Category", "Category",
        table_region_fields=("Category",),
    ),
    AuditAttentionPoint(
        "environment.setup", "environment",
        "Basic Information.Test Information.Test Environment Setup and Precautions.测试环境搭建以及注意事项",
        "测试环境",
        ("测试环境", "Test Environment"),
        heading_boundary="page_end",
    ),
    AuditAttentionPoint(
        "experience.page", "experience",
        "Basic Information.Test Information.Summary of Experience and Typical Cases",
        "Summary of Experience and Typical Cases",
        (), (), True,
    ),
    AuditAttentionPoint(
        "report.weekly", "report_store",
        "Basic Information.Test Information.Test Report Store",
        "Test Report Store", (), (), True,
    ),
)
MISSING_QA = "格式有误：查询不到QA"


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
    product_line_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductLine:
    key: str
    source_url: str
    display_name: str


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
    product_lines: tuple[ProductLine, ...] = ()


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
    owner: str = MISSING_QA

    @property
    def status(self) -> AuditStatus:
        states = {f.status for f in self.findings}
        if AuditStatus.INVALID_FORMAT in states:
            return AuditStatus.INVALID_FORMAT
        if AuditStatus.NOT_UPDATED in states:
            return AuditStatus.NOT_UPDATED
        if states and states <= {AuditStatus.UPDATED}:
            return AuditStatus.UPDATED
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
    product_lines: tuple[ProductLine, ...] = ()
