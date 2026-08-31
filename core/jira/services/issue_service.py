from __future__ import annotations

from typing import Any

from core.jira.domain import Issue
from core.jira.mapper import JiraIssueMapper


class JiraIssueService:
    """Lightweight full-result Issue queries used by Daily Report."""

    def __init__(self, gateway: Any):
        self._gateway = gateway
        self._mapper = JiraIssueMapper(gateway.config.base_url)

    def search_records(
        self,
        jql: str,
        *,
        page_size: int | None = None,
        max_total_results: int | None = None,
    ) -> list[Issue]:
        payloads = self._gateway.search_all_payloads(
            jql,
            fields=list(self._gateway.CORE_FIELDS),
            page_size=page_size,
            max_total_results=max_total_results,
        )
        return [self._mapper.from_search(payload) for payload in payloads]
