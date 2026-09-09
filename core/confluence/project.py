from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.domain.detail import DetailSection
from core.domain.values import FieldBag, NamedValue, PersonRef, SourceRevision


@dataclass(frozen=True)
class ProjectIdentity:
    confluence_id: str
    project_id: str


@dataclass(frozen=True)
class ProductSpaceRef:
    key: str
    name: str = ""
    url: str = ""


@dataclass(frozen=True)
class ConfluencePageRef:
    page_id: str
    title: str = ""
    url: str = ""
    version: int = 0


@dataclass(frozen=True)
class ProjectRole:
    role: NamedValue
    people: tuple[PersonRef, ...]


@dataclass(frozen=True)
class ProjectMilestones:
    values: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SourceEvidence:
    source: str
    page: ConfluencePageRef


@dataclass(frozen=True)
class Project:
    identity: ProjectIdentity
    name: str
    product_space: ProductSpaceRef
    catalog_page: ConfluencePageRef
    status: NamedValue | None = None
    stage: NamedValue | None = None
    support_mode: NamedValue | None = None
    customer_summary: str = ""
    owner_summary: tuple[PersonRef, ...] = ()
    revision: SourceRevision = field(default_factory=SourceRevision)
    roles: DetailSection[tuple[ProjectRole, ...]] = field(default_factory=DetailSection)
    milestones: DetailSection[ProjectMilestones] = field(default_factory=DetailSection)
    hardware: DetailSection[FieldBag] = field(default_factory=DetailSection)
    software: DetailSection[FieldBag] = field(default_factory=DetailSection)
    facts: DetailSection[FieldBag] = field(default_factory=DetailSection)
    evidence: DetailSection[tuple[SourceEvidence, ...]] = field(default_factory=DetailSection)


@dataclass(frozen=True)
class ProjectDetails:
    roles: bool = False
    milestones: bool = False
    hardware: bool = False
    software: bool = False
    facts: bool = False
    evidence: bool = False

    def sections(self) -> tuple[str, ...]:
        return tuple(name for name in ("roles", "milestones", "hardware", "software", "facts", "evidence") if getattr(self, name))


@dataclass(frozen=True)
class ProjectQuery:
    filters: tuple[tuple[str, tuple[str, ...]], ...] = ()
    search: str = ""
    include_inactive: bool = False

    @classmethod
    def from_filters(cls, filters: dict[str, Any] | None = None, *, search: str = "", include_inactive: bool = False) -> "ProjectQuery":
        return cls(
            tuple(
                (str(key), tuple(str(item) for item in (value if isinstance(value, (list, tuple, set)) else (value,))))
                for key, value in (filters or {}).items()
            ),
            str(search or ""),
            include_inactive,
        )


@dataclass(frozen=True)
class ProjectPage:
    projects: tuple[Project, ...]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class ProjectSyncScope:
    product_space_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectSyncResult:
    projects: tuple[Project, ...]
    failed_product_spaces: tuple[str, ...] = ()
