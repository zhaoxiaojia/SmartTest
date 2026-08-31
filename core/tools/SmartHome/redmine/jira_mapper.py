from __future__ import annotations

from typing import Any

from core.jira.commands import CreateIssueCommand


class RedmineToJiraMapper:
    def to_create_command(
        self,
        *,
        project_key: str,
        issue_type: str,
        summary: str,
        description: str = "",
        priority: str = "",
        assignee: str = "",
        labels: tuple[str, ...] = (),
        components: tuple[str, ...] = (),
        source_id: str,
        source_url: str,
        description_includes_source_identity: bool = False,
        extra_fields: dict[str, Any] | None = None,
        field_controls: dict[str, str] | None = None,
        attachments: tuple[Any, ...] = (),
    ) -> CreateIssueCommand:
        return CreateIssueCommand(
            project_key=project_key,
            issue_type=issue_type,
            summary=summary,
            description=description,
            priority=priority,
            assignee=assignee,
            labels=labels,
            components=components,
            source_system="redmine",
            source_id=source_id,
            source_url=source_url,
            description_includes_source_identity=description_includes_source_identity,
            extra_fields=extra_fields or {},
            field_controls=field_controls or {},
            attachments=attachments,
        )
