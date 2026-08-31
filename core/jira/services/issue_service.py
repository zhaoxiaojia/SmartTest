from __future__ import annotations

from typing import Any, Iterable

from core.jira.domain import Issue, IssueDetails, IssuePage
from core.jira.fields.registry import FieldFetchPlan, FieldRegistry, build_default_registry
from core.jira.fields.specs import FieldSpec
from core.jira.mapper import JiraIssueMapper
from core.jira.repository import IssueRepository


class JiraIssueService:
    """Application service over the Jira Issue repository."""

    def __init__(self, gateway: Any, *, registry: FieldRegistry | None = None):
        self._gateway = gateway
        self._registry = registry or build_default_registry()
        self._mapper = JiraIssueMapper(gateway.config.base_url)
        self._repository = IssueRepository(gateway, self._mapper)

    def search_records(
        self,
        jql: str,
        *,
        specs: Iterable[str | FieldSpec],
        include_heavy: bool = False,
        page_size: int | None = None,
        max_workers: int | None = None,
        max_total_results: int | None = None,
    ) -> list[Issue]:
        payloads = self._gateway.search_all_payloads(
            jql,
            fields=list(self._gateway.CORE_FIELDS),
            page_size=page_size,
            max_total_results=max_total_results,
        )
        return [self._mapper.from_search(payload) for payload in payloads]

    def build_fetch_plan(self, specs: Iterable[str | FieldSpec], *, include_heavy: bool = False) -> FieldFetchPlan:
        return self._registry.build_plan(specs, include_heavy=include_heavy)

    def search_page_records(
        self,
        jql: str,
        *,
        specs: Iterable[str | FieldSpec],
        start_at: int,
        max_results: int,
        include_heavy: bool = False,
    ) -> tuple[IssuePage, list[Issue]]:
        payload = self._gateway.search_payload(jql, start_at=start_at, max_results=max_results, fields=list(self._gateway.CORE_FIELDS))
        issues = tuple(self._mapper.from_search(item) for item in payload.get("issues") or ())
        page_size = int(payload.get("maxResults") or max_results)
        page = IssuePage(issues, start_at // page_size if page_size else 0, page_size, int(payload.get("total") or len(issues)))
        return page, list(issues)

    def fetch_favourite_filters(self) -> list[dict[str, Any]]:
        return self._gateway.fetch_favourite_filters()

    def hydrate_issue(self, issue_key: str, *, specs: Iterable[str | FieldSpec]) -> Issue:
        requested = {item.name if isinstance(item, FieldSpec) else str(item) for item in specs}
        issue = self._repository.get(issue_key)
        return self._repository.load_details(
            issue,
            IssueDetails(
                description="description" in requested,
                comments="comments" in requested,
                attachments="attachments" in requested,
                links="issuelinks" in requested or "links" in requested,
            ),
        )
