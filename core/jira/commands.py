from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.jira.attachments import CreateIssueAttachment
from core.jira.domain import IssueRef


@dataclass(frozen=True)
class CreateIssueCommand:
    project_key: str
    issue_type: str
    summary: str
    description: str = ""
    priority: str = ""
    assignee: str = ""
    labels: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    source_system: str = ""
    source_id: str = ""
    source_url: str = ""
    description_includes_source_identity: bool = False
    extra_fields: dict[str, Any] = field(default_factory=dict)
    field_controls: dict[str, str] = field(default_factory=dict)
    attachments: tuple[CreateIssueAttachment, ...] = ()


@dataclass(frozen=True)
class UpdateIssueCommand:
    issue_key: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class CreateIssueResult:
    created: bool
    issue_state: str = ""
    issue: IssueRef | None = None
    issue_error: str = ""
    attachment_state: str = "none"
    attachment_results: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if not self.issue_state:
            object.__setattr__(self, "issue_state", "created" if self.created else ("duplicate" if self.issue else "create_failed"))

    @property
    def issue_key(self) -> str:
        return self.issue.key if self.issue else ""

    @property
    def issue_id(self) -> str:
        return self.issue.id if self.issue else ""

    @property
    def issue_url(self) -> str:
        return self.issue.web_url if self.issue else ""

    @property
    def existing_key(self) -> str:
        return self.issue.key if self.issue_state == "duplicate" and self.issue else ""
