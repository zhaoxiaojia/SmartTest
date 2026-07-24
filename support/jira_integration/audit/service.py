from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from .models import AuditReport, ResolvedAuditInput
from .rules import active_rules
from .validator import audit_issue


class _AuditClient(Protocol):
    def search_page(self, jql: str, **kwargs): ...


class JiraAuditService:
    _FIELDS = [
        "summary",
        "description",
        "reporter",
        "components",
        "labels",
        "attachment",
    ]

    def __init__(self, client: _AuditClient, *, base_url: str):
        self._client = client
        self._base_url = str(base_url or "").rstrip("/")

    def run(
        self,
        resolved: ResolvedAuditInput,
        progress: Callable[[str, int, int], None],
    ) -> AuditReport:
        raw_issues = []
        start_at = 0
        total = 0
        while True:
            page = self._client.search_page(
                resolved.jql,
                start_at=start_at,
                fields=self._FIELDS,
                validate_query="strict",
            )
            raw_issues.extend(page.issues)
            total = page.total
            progress("fetching", len(raw_issues), total)
            if page.is_last or not page.issues or len(raw_issues) >= total:
                break
            start_at = page.start_at + len(page.issues)

        results = []
        for index, issue in enumerate(raw_issues, start=1):
            results.append(audit_issue(issue, base_url=self._base_url))
            progress("auditing", index, len(raw_issues))
        return AuditReport(
            resolved=resolved,
            generated_at=datetime.now(),
            rules=active_rules(),
            issues=tuple(results),
        )
