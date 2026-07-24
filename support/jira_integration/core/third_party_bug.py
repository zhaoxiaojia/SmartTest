from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

@dataclass(frozen=True)
class ThirdPartyBugAttachment:
    id: str
    filename: str
    size: str = ""
    author: str = ""
    created_at: str = ""
    detail_url: str = ""
    download_url: str = ""


@dataclass(frozen=True)
class ThirdPartyBugComment:
    id: str
    author: str = ""
    header: str = ""
    note: str = ""
    details: tuple[str, ...] = ()
    created_at: str = ""


@dataclass(frozen=True)
class ThirdPartyBugListItem:
    id: str
    url: str
    tracker: str = ""
    status: str = ""
    priority: str = ""
    subject: str = ""
    assignee: str = ""
    updated_at: str = ""
    category: str = ""


@dataclass(frozen=True)
class ThirdPartyBugDetail:
    id: str
    url: str
    project_identifier: str = ""
    tracker: str = ""
    subject: str = ""
    description: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    comments: tuple[ThirdPartyBugComment, ...] = ()
    attachments: tuple[ThirdPartyBugAttachment, ...] = ()
    list_item: ThirdPartyBugListItem | None = None

    def attr(self, key: str, default: str = "") -> str:
        return str(self.attributes.get(key, default) or "").strip()

@dataclass(frozen=True)
class ThirdPartyBugProject:
    name: str
    identifier: str
    url: str
    project_id: str = ""
    issues: tuple[ThirdPartyBugListItem, ...] = ()


@dataclass(frozen=True)
class ThirdPartyBugContext:
    account: str = ""
    projects: tuple[ThirdPartyBugProject, ...] = ()
    issues: tuple[ThirdPartyBugDetail, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    def item_for_issue(self, issue_id: str) -> tuple[ThirdPartyBugProject | None, ThirdPartyBugListItem | None]:
        for project in self.projects:
            for issue in project.issues:
                if issue.id == issue_id:
                    return project, issue
        return None, None

    def with_detail(self, detail: ThirdPartyBugDetail) -> "ThirdPartyBugContext":
        details = tuple([existing for existing in self.issues if existing.id != detail.id] + [detail])
        return replace(self, issues=details)
