from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from atlassian import Jira
except ImportError:  # pragma: no cover - dependency error is normalized at construction
    Jira = None

from core.jira.attachments import (
    AttachmentCancellation,
    AttachmentUploadCancelled,
    CreateIssueAttachment,
    JiraAttachmentMetadata,
)
from core.jira.commands import CreateIssueCommand, UpdateIssueCommand


@dataclass(frozen=True)
class JiraGatewayConfig:
    base_url: str
    page_size: int = 100


class JiraGatewayError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class JiraGateway:
    CORE_FIELDS = (
        "summary",
        "project",
        "status",
        "issuetype",
        "priority",
        "assignee",
        "reporter",
        "creator",
        "components",
        "resolution",
        "created",
        "updated",
        "labels",
    )

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        api: Any = None,
        page_size: int = 100,
    ) -> None:
        clean_url = str(base_url or "").rstrip("/")
        if not clean_url:
            raise JiraGatewayError("jira_base_url_required")
        self.config = JiraGatewayConfig(clean_url, page_size)
        if api is not None:
            self._api = api
            return
        if Jira is None:
            raise JiraGatewayError("jira_dependency_unavailable")
        try:
            self._api = Jira(url=clean_url, username=username, password=password)
        except Exception as exc:
            raise JiraGatewayError("jira_initialization_failed") from exc

    def search_issues(self, query: str, page: int = 0) -> dict[str, Any]:
        start = int(page) * self.config.page_size
        return self.search_payload(query, start_at=start, max_results=self.config.page_size, fields=list(self.CORE_FIELDS))

    def search_payload(
        self,
        query: str,
        *,
        start_at: int = 0,
        max_results: int | None = None,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            payload = self._api.jql(
                query,
                fields=fields or list(self.CORE_FIELDS),
                start=start_at,
                limit=max_results or self.config.page_size,
                expand=",".join(expand) if expand else None,
                validate_query="strict",
            )
        except Exception as exc:
            raise JiraGatewayError("jira_search_failed") from exc
        return payload if isinstance(payload, dict) else {}

    def search_all_payloads(
        self,
        query: str,
        *,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
        page_size: int | None = None,
        max_total_results: int | None = None,
    ) -> list[dict[str, Any]]:
        limit = page_size or self.config.page_size
        rows: list[dict[str, Any]] = []
        start = 0
        while True:
            remaining = None if max_total_results is None else max_total_results - len(rows)
            if remaining is not None and remaining <= 0:
                return rows
            page = self.search_payload(query, start_at=start, max_results=min(limit, remaining) if remaining is not None else limit, fields=fields, expand=expand)
            issues = [item for item in page.get("issues") or () if isinstance(item, dict)]
            rows.extend(issues)
            start += len(issues)
            if not issues or start >= int(page.get("total") or start):
                return rows

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        try:
            payload = self._api.get_issue(issue_key, fields=list(self.CORE_FIELDS), expand=None)
        except Exception as exc:
            raise JiraGatewayError("jira_issue_get_failed") from exc
        return payload if isinstance(payload, dict) else {}

    def load_issue_sections(self, issue_key: str, sections: tuple[str, ...]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if "comments" in sections:
            try:
                comments = self._api.issue_get_comments(issue_key) or {}
            except Exception as exc:
                raise JiraGatewayError("jira_comments_failed") from exc
            result["comments"] = comments.get("comments", comments if isinstance(comments, list) else [])
        field_map = {
            "description": "description",
            "attachments": "attachment",
            "links": "issuelinks",
        }
        requested_fields = [field_map[name] for name in sections if name in field_map]
        if "custom_fields" in sections:
            requested_fields.append("*all")
        if requested_fields:
            try:
                payload = self._api.get_issue(issue_key, fields=requested_fields, expand=None) or {}
            except Exception as exc:
                raise JiraGatewayError("jira_details_failed") from exc
            fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
            for section, jira_field in field_map.items():
                if section in sections:
                    result[section] = fields.get(jira_field)
            if "custom_fields" in sections:
                result["custom_fields"] = {key: value for key, value in fields.items() if str(key).startswith("customfield_")}
        return result

    def create_issue(self, command: CreateIssueCommand) -> dict[str, Any]:
        fields = self.command_fields(command)
        try:
            payload = self._api.create_issue(fields)
        except Exception as exc:
            raise JiraGatewayError("jira_create_failed") from exc
        return payload if isinstance(payload, dict) else {}

    def update_issue(self, command: UpdateIssueCommand) -> dict[str, Any]:
        try:
            self._api.issue_update(command.issue_key, command.fields)
            payload = self._api.get_issue(command.issue_key, fields=list(self.CORE_FIELDS), expand=None)
        except Exception as exc:
            raise JiraGatewayError("jira_update_failed") from exc
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def command_fields(command: CreateIssueCommand) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": command.project_key},
            "issuetype": {"name": command.issue_type},
            "summary": command.summary,
            "description": _description(command),
            "labels": _labels(command),
        }
        if command.priority:
            fields["priority"] = _field_value(command.priority, command.field_controls.get("priority", ""), default_kind="name")
        if command.assignee:
            fields["assignee"] = {"name": command.assignee}
        if command.components:
            control = command.field_controls.get("components", "")
            fields["components"] = _field_value(list(command.components), control) if control else [{"name": item} for item in command.components if item]
        fields.update({key: _field_value(value, command.field_controls.get(key, "")) for key, value in command.extra_fields.items() if value not in (None, "", [], {})})
        return fields

    def find_issue_for_source(self, command: CreateIssueCommand) -> dict[str, Any] | None:
        if not command.source_system or not command.source_id:
            return None
        jql = f'project = "{_jql(command.project_key)}" AND labels = "source_{_safe(command.source_system)}" AND description ~ "{_jql(command.source_id)}"'
        return self._first(jql)

    def find_issue_for_external_url(self, project_key: str, external_url: str) -> dict[str, Any] | None:
        clean_url = str(external_url or "").strip()
        if not project_key or not clean_url:
            return None
        for jql in (
            f'project = "{_jql(project_key)}" AND "Attachment links" = "{_jql(clean_url)}"',
            f'project = "{_jql(project_key)}" AND text ~ "{_jql(clean_url)}"',
        ):
            try:
                found = self._first(jql)
            except JiraGatewayError:
                continue
            if found:
                return found
        return None

    def _first(self, jql: str) -> dict[str, Any] | None:
        payload = self.search_payload(jql, max_results=1, fields=["summary"])
        issues = payload.get("issues") or ()
        return issues[0] if issues else None

    def fetch_filter(self, filter_id: str) -> dict[str, Any]:
        try:
            payload = self._api.get_filter(filter_id) or {}
        except Exception as exc:
            raise JiraGatewayError("jira_filter_failed") from exc
        return payload if isinstance(payload, dict) else {}

    def fetch_create_metadata(self, project_key: str, issue_type: str) -> dict[str, Any]:
        try:
            payload = self._api.issue_createmeta(project_key, expand="projects.issuetypes.fields") or {}
        except Exception as exc:
            raise JiraGatewayError("jira_create_metadata_failed") from exc
        return payload if isinstance(payload, dict) else {}

    def search_users(self, query: str, *, project_key: str = "SH") -> list[dict[str, Any]]:
        try:
            payload = self._api.get_all_assignable_users_for_project(project_key, start=0, limit=1000) or []
        except Exception as exc:
            raise JiraGatewayError("jira_user_search_failed") from exc
        needle = str(query or "").strip().casefold()
        return [
            _public_user(item)
            for item in payload
            if isinstance(item, dict)
            and (
                not needle
                or needle in str(item.get("name") or "").casefold()
                or needle in str(item.get("displayName") or "").casefold()
            )
        ]

    def current_user(self) -> dict[str, str]:
        try:
            payload = self._api.get("rest/api/2/myself") or {}
        except Exception as exc:
            raise JiraGatewayError("jira_current_user_failed") from exc
        return _public_user(payload)

    def attachment_metadata(self) -> JiraAttachmentMetadata:
        try:
            payload = self._api.get_attachment_meta() or {}
        except Exception as exc:
            raise JiraGatewayError("jira_attachment_metadata_failed") from exc
        limit = payload.get("uploadLimit")
        return JiraAttachmentMetadata(True, payload.get("enabled") if isinstance(payload.get("enabled"), bool) else None, int(limit) if isinstance(limit, int) and not isinstance(limit, bool) else None)

    def list_attachments(self, issue_key: str) -> list[dict[str, Any]]:
        try:
            payload = self._api.get_issue(issue_key, fields=["attachment"], expand=None) or {}
        except Exception as exc:
            raise JiraGatewayError("jira_attachments_list_failed") from exc
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
        return [item for item in fields.get("attachment") or () if isinstance(item, dict)]

    def upload_attachment(
        self,
        issue_key: str,
        attachment: CreateIssueAttachment,
        *,
        cancellation: AttachmentCancellation | None = None,
    ) -> dict[str, Any]:
        try:
            with attachment.path.open("rb") as source:
                payload = self._api.add_attachment_object(
                    issue_key,
                    _AttachmentStream(source, attachment.upload_filename, cancellation),
                )
        except Exception as exc:
            if isinstance(exc, AttachmentUploadCancelled):
                raise
            raise JiraGatewayError("jira_attachment_upload_failed") from exc
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
        return payload if isinstance(payload, dict) else {}


def _field_value(value: Any, control: str, *, default_kind: str = "") -> Any:
    if control in {"text", "multiline"}:
        return value
    if control == "single":
        return {"id": str(value)}
    if control == "multi":
        return [{"id": str(item)} for item in (value if isinstance(value, (list, tuple)) else [value]) if item]
    if control == "cascade":
        payload = {"id": str(value.get("parent") or "")}
        if value.get("child"):
            payload["child"] = {"id": str(value["child"])}
        return payload
    if control == "user":
        return {"name": str(value)}
    return {default_kind: value} if default_kind else value


def _labels(command: CreateIssueCommand) -> list[str]:
    labels = list(command.labels)
    if command.source_system and command.source_id:
        labels.extend(("clone_external", f"source_{_safe(command.source_system)}"))
    return list(dict.fromkeys(item for item in labels if item))


def _description(command: CreateIssueCommand) -> str:
    if command.description_includes_source_identity:
        return command.description
    lines = [command.description]
    if command.source_system and command.source_id:
        lines.extend(("", f"Source: {command.source_system}", f"Source ID: {command.source_id}"))
        if command.source_url:
            lines.append(f"Source URL: {command.source_url}")
    return "\n".join(lines).strip()


def _safe(value: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._") or "unknown"


def _jql(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def _public_user(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "account": str(payload.get("name") or payload.get("accountId") or ""),
        "display_name": str(payload.get("displayName") or payload.get("name") or ""),
        "avatar_url": str((payload.get("avatarUrls") or {}).get("48x48") or ""),
    }


class _AttachmentStream:
    def __init__(self, source: Any, filename: str, cancellation: AttachmentCancellation | None) -> None:
        self._source = source
        self.name = filename
        self._cancellation = cancellation

    def read(self, size: int = -1) -> bytes:
        if self._cancellation is not None:
            self._cancellation.raise_if_cancelled()
        return self._source.read(size)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._source, name)
