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
    raw_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ThirdPartyBugDetail:
    id: str
    url: str
    project_identifier: str = ""
    project_name: str = ""
    tracker: str = ""
    subject: str = ""
    description: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    comments: tuple[ThirdPartyBugComment, ...] = ()
    attachments: tuple[ThirdPartyBugAttachment, ...] = ()
    list_item: ThirdPartyBugListItem | None = None

    def attr(self, key: str, default: str = "") -> str:
        return str(self.attributes.get(key, default) or "").strip()

    def labels(self) -> list[str]:
        labels: list[str] = []
        for source in (self.project_identifier, self.attr("Category"), self.tracker):
            text = str(source or "").strip()
            if text and text not in labels:
                labels.append(text)
        return labels

    def to_jira_transition(
        self,
        *,
        project: ThirdPartyBugProject | None = None,
        project_key: str = "",
        source_system: str = "third_party_bug",
        issue_type: str = "Bug",
    ) -> dict[str, Any]:
        project_id = project.project_id if project else ""
        project_identifier = project.identifier if project else self.project_identifier
        project_name = project.name if project else self.project_name
        return {
            "source": {
                "system": source_system,
                "id": self.id,
                "url": self.url,
                "project_identifier": project_identifier,
                "project_id": project_id,
            },
            "fields": {
                "project": {
                    "key": project_key,
                    "redmine_project_id": project_id,
                    "redmine_identifier": project_identifier,
                    "name": project_name,
                },
                "issuetype": {"name": issue_type or self.tracker or "Bug"},
                "summary": self.subject,
                "description": self.description,
                "priority": {"name": self.attr("Priority")},
                "assignee": {"displayName": self.attr("Assignee")},
                "status": {"name": self.attr("Status")},
                "components": [{"name": self.attr("Category")}] if self.attr("Category") else [],
                "labels": self.labels(),
                "custom_fields": {
                    "redmine_id": self.id,
                    "redmine_tracker": self.tracker,
                    "redmine_project_id": project_id,
                    "redmine_start_date": self.attr("Start date"),
                    "redmine_due_date": self.attr("Due date"),
                    "redmine_done_ratio": self.attr("% Done"),
                    "redmine_estimated_time": self.attr("Estimated time"),
                },
            },
            "comments": [
                {
                    "source_id": comment.id,
                    "author": comment.author,
                    "created_at": comment.created_at,
                    "body": comment.note,
                    "property_changes": list(comment.details),
                }
                for comment in self.comments
                if comment.note or comment.details
            ],
            "attachments": [
                {
                    "source_id": attachment.id,
                    "filename": attachment.filename,
                    "size": attachment.size,
                    "author": attachment.author,
                    "created_at": attachment.created_at,
                    "detail_url": attachment.detail_url,
                    "download_url": attachment.download_url,
                }
                for attachment in self.attachments
            ],
        }


@dataclass(frozen=True)
class ThirdPartyBugProject:
    name: str
    identifier: str
    url: str
    project_id: str = ""
    parent_identifier: str = ""
    level: int = 0
    children: tuple[str, ...] = ()
    issues: tuple[ThirdPartyBugListItem, ...] = ()


@dataclass(frozen=True)
class ThirdPartyBugContext:
    account: str = ""
    source_url: str = ""
    projects: tuple[ThirdPartyBugProject, ...] = ()
    issues: tuple[ThirdPartyBugDetail, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)
    jira: dict[str, Any] = field(default_factory=dict)

    def item_for_issue(self, issue_id: str) -> tuple[ThirdPartyBugProject | None, ThirdPartyBugListItem | None]:
        for project in self.projects:
            for issue in project.issues:
                if issue.id == issue_id:
                    return project, issue
        return None, None

    def project_for_detail(self, detail: ThirdPartyBugDetail | None) -> ThirdPartyBugProject | None:
        if detail is None:
            return None
        return next((project for project in self.projects if project.identifier == detail.project_identifier), None)

    def with_detail(self, detail: ThirdPartyBugDetail, *, jira_issue: dict[str, Any] | None = None) -> "ThirdPartyBugContext":
        details = tuple([existing for existing in self.issues if existing.id != detail.id] + [detail])
        jira_issues = list(self.jira.get("issues") or [])
        if jira_issue is not None:
            jira_issues = [item for item in jira_issues if str(item.get("source", {}).get("id") or item.get("key") or "") != detail.id]
            jira_issues.append(jira_issue)
        return replace(
            self,
            issues=details,
            jira={**self.jira, "issues": jira_issues},
            raw={**self.raw, "selected_issue_id": detail.id},
        )
