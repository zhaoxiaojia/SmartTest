from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from support.jira_integration.core.errors import JiraRequestError
from support.jira_integration.core.models import CreateIssueRequest, CreateIssueResult, ExistingIssue

if TYPE_CHECKING:
    from support.jira_integration.transport.client import JiraClient


class CreateIssueService:
    def __init__(self, client: "JiraClient", *, browse_base_url: str = ""):
        self._client = client
        self._browse_base_url = browse_base_url.rstrip("/")

    def check_issue(self, request: CreateIssueRequest) -> ExistingIssue | None:
        if not request.source_system or not request.source_id:
            return None
        page = self._client.search_page(
            self._third_party_jql(request),
            start_at=0,
            max_results=1,
            fields=["summary"],
        )
        return self._existing_issue(page.issues[0]) if page.issues else None

    def check_issue_by_external_url(self, *, project_key: str, external_url: str) -> ExistingIssue | None:
        clean_url = str(external_url or "").strip()
        if not project_key or not clean_url:
            return None
        for jql in self._external_url_jqls(project_key=project_key, external_url=clean_url):
            try:
                page = self._client.search_page(jql, start_at=0, max_results=1, fields=["summary"])
            except JiraRequestError:
                continue
            if page.issues:
                return self._existing_issue(page.issues[0])
        return None

    def create_issue(self, request: CreateIssueRequest) -> CreateIssueResult:
        existing = self.check_issue(request)
        if existing:
            return CreateIssueResult(created=False, existing_key=existing.key, issue_url=existing.web_url, raw=existing.raw)
        created = self._client.create_issue(self._payload(request))
        return CreateIssueResult(
            created=True,
            issue_key=str(created.get("key", "")),
            issue_id=str(created.get("id", "")),
            issue_url=str(created.get("self", "")),
            raw=created,
        )

    def _payload(self, request: CreateIssueRequest) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": request.project_key},
            "issuetype": {"name": request.issue_type},
            "summary": request.summary,
            "description": self._description(request),
            "labels": self._labels(request),
        }
        if request.priority:
            fields["priority"] = {"name": request.priority}
        if request.assignee:
            fields["assignee"] = {"name": request.assignee}
        if request.components:
            fields["components"] = [{"name": component} for component in request.components if component]
        fields.update({key: value for key, value in request.extra_fields.items() if value not in (None, "", [], {})})
        return {"fields": fields}

    def _labels(self, request: CreateIssueRequest) -> list[str]:
        labels = list(request.labels)
        if request.source_system and request.source_id:
            labels.extend(["clone_external", f"source_{_safe_label(request.source_system)}", self._source_id_label(request)])
        return list(dict.fromkeys(label for label in labels if label))

    def _description(self, request: CreateIssueRequest) -> str:
        lines = [request.description]
        if request.source_system and request.source_id:
            lines.extend(["", f"Source: {request.source_system}", f"Source ID: {request.source_id}"])
            if request.source_url:
                lines.append(f"Source URL: {request.source_url}")
        return "\n".join(lines).strip()

    def _third_party_jql(self, request: CreateIssueRequest) -> str:
        return (
            f'project = "{_jql_quote(request.project_key)}" '
            f'AND labels = "source_{_safe_label(request.source_system)}" '
            f'AND labels = "{self._source_id_label(request)}"'
        )

    def _external_url_jqls(self, *, project_key: str, external_url: str) -> list[str]:
        project = _jql_quote(project_key)
        url = _jql_quote(external_url)
        return [
            f'project = "{project}" AND "Attachment links" = "{url}"',
            f'project = "{project}" AND text ~ "{url}"',
        ]

    @staticmethod
    def _source_id_label(request: CreateIssueRequest) -> str:
        return f"{_safe_label(request.source_system)}_{_safe_label(request.source_id)}"

    def _existing_issue(self, issue: dict[str, Any]) -> ExistingIssue:
        key = str(issue.get("key", ""))
        fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
        return ExistingIssue(
            key=key,
            web_url=f"{self._browse_base_url}/browse/{key}" if self._browse_base_url and key else "",
            summary=str(fields.get("summary", "")),
            raw=issue,
        )


def _safe_label(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._") or "unknown"


def _jql_quote(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')
