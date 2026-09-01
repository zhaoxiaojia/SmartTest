from __future__ import annotations

import os
from pathlib import Path

from core.domain.detail import DetailState
from core.jira.audit import (
    JiraAuditUseCase,
    export_audit_xlsx,
    resolve_audit_input,
)
from core.jira.domain import Issue, IssueDetails
from core.jira.gateway import JiraGateway
from core.jira.mapper import JiraIssueMapper

from ..task_manager import WEB_TASKS
from ..database import WebDatabase
from ..jira.cache_service import JiraIssueCacheService
from ..jira.issue_repository import JiraIssueRepository
from ..session import default_web_database_path


class WebJiraAuditOwner:
    def __init__(self, gateway, cache_service: JiraIssueCacheService):
        self._gateway = gateway
        self._cache = cache_service

    @classmethod
    def from_credentials(cls, username: str, password: str):
        base_url = os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
        gateway = JiraGateway(base_url, username, password)
        cache = JiraIssueCacheService(
            gateway, JiraIssueMapper(base_url),
            JiraIssueRepository(WebDatabase(default_web_database_path())),
        )
        return cls(gateway, cache)

    def resolve(self, text):
        return resolve_audit_input(
            text,
            base_url=self._gateway.config.base_url,
            fetch_filter=self._gateway.fetch_filter,
            validate_jql=lambda jql: self._gateway.search_payload(
                jql, start_at=0, max_results=1,
            ),
        )

    def run(self, scope, cancellation, progress):
        return JiraAuditUseCase(self).run(
            scope, cancellation=cancellation, progress=progress,
            task_manager=WEB_TASKS, parent_task_id=getattr(cancellation, "task_id", ""),
        )

    def list_issues(self, scope, cancellation) -> tuple[Issue, ...]:
        issues = []
        page = 0
        while True:
            cancellation.raise_if_cancelled()
            result = self._cache.refresh_issues(scope.jql, page=page)
            cancellation.raise_if_cancelled()
            if result["failed"]:
                raise RuntimeError("mapping_failed")
            issues.extend(result["issues"])
            if not result["issues"] or len(issues) >= result["total"]:
                return tuple(issues)
            page += 1

    def load_details(self, issue: Issue, details: IssueDetails) -> Issue:
        loaded = self._cache.get_issue(issue.identity.key, details)
        if loaded is None:
            raise RuntimeError("not_found")
        if any(
            getattr(loaded, name).state in {DetailState.STALE, DetailState.FAILED}
            for name in details.sections()
        ):
            loaded = self._cache.refresh_issue(issue.identity.key, details)
        if any(
            getattr(loaded, name).state is DetailState.FAILED
            for name in details.sections()
        ):
            raise RuntimeError("remote_unavailable")
        return loaded

    @staticmethod
    def export(report, output_path: Path):
        return export_audit_xlsx(report, output_path=output_path)
