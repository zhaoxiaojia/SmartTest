from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from support.jira_integration.core.models import IssueRecord, SearchPage
from support.jira_integration.fields.extractors import project_fields
from support.jira_integration.fields.registry import FieldFetchPlan, FieldRegistry, build_default_registry
from support.jira_integration.fields.specs import FieldSpec

if TYPE_CHECKING:
    from support.jira_integration.transport.client import JiraClient


class JiraIssueService:
    def __init__(
        self,
        client: "JiraClient",
        *,
        registry: FieldRegistry | None = None,
    ):
        self._client = client
        self._registry = registry or build_default_registry()

    def search_records(
        self,
        jql: str,
        *,
        specs: Iterable[str | FieldSpec],
        include_heavy: bool = False,
        page_size: int | None = None,
        max_workers: int | None = None,
        max_total_results: int | None = None,
    ) -> list[IssueRecord]:
        plan = self._registry.build_plan(specs, include_heavy=include_heavy)
        raw_issues = self._client.search_all(
            jql,
            fields=list(plan.jira_fields),
            expand=list(plan.expand) or None,
            page_size=page_size,
            max_workers=max_workers,
            max_total_results=max_total_results,
        )
        return [self._to_record(issue, list(plan.active_specs)) for issue in raw_issues]

    def build_fetch_plan(
        self,
        specs: Iterable[str | FieldSpec],
        *,
        include_heavy: bool = False,
    ) -> FieldFetchPlan:
        return self._registry.build_plan(specs, include_heavy=include_heavy)

    def search_page_records(
        self,
        jql: str,
        *,
        specs: Iterable[str | FieldSpec],
        start_at: int,
        max_results: int,
        include_heavy: bool = False,
    ) -> tuple[SearchPage, list[IssueRecord]]:
        plan = self.build_fetch_plan(specs, include_heavy=include_heavy)
        page = self._client.search_page(
            jql,
            start_at=start_at,
            max_results=max_results,
            fields=list(plan.jira_fields),
            expand=list(plan.expand) or None,
        )
        records = [self._to_record(issue, list(plan.active_specs)) for issue in page.issues]
        return page, records

    def fetch_favourite_filters(self) -> list[dict[str, Any]]:
        return self._client.fetch_favourite_filters()

    def hydrate_issue(
        self,
        issue_key: str,
        *,
        specs: Iterable[str | FieldSpec],
    ) -> IssueRecord:
        plan = self._registry.build_plan(specs, include_heavy=True)
        raw_issue = self._client.fetch_issue(
            issue_key,
            fields=list(plan.jira_fields),
            expand=list(plan.expand) or None,
        )
        return self._to_record(raw_issue, list(plan.active_specs))

    def _to_record(self, issue: dict[str, Any], specs: list[FieldSpec]) -> IssueRecord:
        return IssueRecord(
            key=str(issue.get("key", "")),
            id=str(issue.get("id")) if issue.get("id") is not None else None,
            raw=issue,
            fields=project_fields(issue, specs),
        )
