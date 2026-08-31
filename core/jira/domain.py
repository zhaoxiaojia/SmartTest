from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import core.domain.values as domain_values
from core.domain.detail import DetailSection


@dataclass(frozen=True)
class RichText:
    value: Any = ""


@dataclass(frozen=True)
class IssueIdentity:
    id: str
    key: str
    web_url: str


@dataclass(frozen=True)
class JiraProjectRef:
    key: str
    id: str = ""
    name: str = ""


@dataclass(frozen=True)
class IssueComment:
    id: str
    body: Any
    author: domain_values.PersonRef | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class IssueAttachment:
    id: str
    filename: str
    url: str = ""
    size: int | None = None
    author: domain_values.PersonRef | None = None


@dataclass(frozen=True)
class IssueLink:
    id: str
    link_type: str
    direction: str
    issue: "IssueRef"


@dataclass(frozen=True)
class IssueRef:
    id: str = ""
    key: str = ""
    web_url: str = ""
    summary: str = ""


@dataclass(frozen=True)
class Issue:
    identity: IssueIdentity
    summary: str
    project: JiraProjectRef
    status: domain_values.NamedValue
    issue_type: domain_values.NamedValue
    priority: domain_values.NamedValue | None = None
    assignee: domain_values.PersonRef | None = None
    reporter: domain_values.PersonRef | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    labels: tuple[str, ...] = ()
    revision: domain_values.SourceRevision = field(default_factory=domain_values.SourceRevision)
    creator: domain_values.PersonRef | None = None
    components: tuple[domain_values.NamedValue, ...] = ()
    resolution: domain_values.NamedValue | None = None
    description: DetailSection[RichText] = field(default_factory=DetailSection)
    comments: DetailSection[tuple[IssueComment, ...]] = field(default_factory=DetailSection)
    attachments: DetailSection[tuple[IssueAttachment, ...]] = field(default_factory=DetailSection)
    links: DetailSection[tuple[IssueLink, ...]] = field(default_factory=DetailSection)
    custom_fields: DetailSection[domain_values.FieldBag] = field(default_factory=DetailSection)


@dataclass(frozen=True)
class IssueDetails:
    description: bool = False
    comments: bool = False
    attachments: bool = False
    links: bool = False
    custom_fields: bool = False

    def sections(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in ("description", "comments", "attachments", "links", "custom_fields")
            if getattr(self, name)
        )


@dataclass(frozen=True)
class IssuePage:
    issues: tuple[Issue, ...]
    page: int
    page_size: int
    total: int

    @property
    def start_at(self) -> int:
        return self.page * self.page_size
