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
    ) -> list[Issue]:
        payloads = self._gateway.search_all_payloads(
            jql,
            fields=list(self._gateway.CORE_FIELDS),
        )
        return [self._mapper.from_search(payload) for payload in payloads]
