from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from jira_tool.cache.issue_store import JiraIssueStore
from jira_tool.cache.search_cache import JiraSearchCache
from jira_tool.core.models import IssueRecord, IssueStoreQuery
from jira_tool.fields.extractors import project_fields
from jira_tool.fields.registry import FieldRegistry, build_default_registry
from jira_tool.fields.specs import FieldSpec

if TYPE_CHECKING:
    from jira_tool.transport.client import JiraClient


class JiraIssueService:
    def __init__(
        self,
        client: "JiraClient",
        *,
        registry: FieldRegistry | None = None,
        cache: JiraSearchCache | None = None,
        issue_store: JiraIssueStore | None = None,
    ):
        self._client = client
        self._registry = registry or build_default_registry()
        self._cache = cache
        self._issue_store = issue_store

    def search_raw(
        self,
        jql: str,
        *,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
        page_size: int | None = None,
        max_workers: int | None = None,
        max_total_results: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._client.search_all(
            jql,
            fields=fields,
            expand=expand,
            page_size=page_size,
            max_workers=max_workers,
            max_total_results=max_total_results,
        )

    def search_records(
        self,
        jql: str,
        *,
        specs: Iterable[str | FieldSpec],
        include_heavy: bool = False,
        use_cache: bool = False,
        ttl_seconds: float | None = None,
        page_size: int | None = None,
        max_workers: int | None = None,
        max_total_results: int | None = None,
    ) -> list[IssueRecord]:
        plan = self._registry.build_plan(specs, include_heavy=include_heavy)
        spec_names = [spec.name for spec in plan.active_specs]
        if use_cache and self._cache is not None:
            cached = self._cache.get_records(
                jql=jql,
                spec_names=spec_names,
                include_heavy=include_heavy,
                ttl_seconds=ttl_seconds,
            )
            if cached is not None:
                return cached

        raw_issues = self.search_raw(
            jql,
            fields=list(plan.jira_fields),
            expand=list(plan.expand) or None,
            page_size=page_size,
            max_workers=max_workers,
            max_total_results=max_total_results,
        )
        records = [self._to_record(issue, list(plan.active_specs)) for issue in raw_issues]
        if use_cache and self._cache is not None:
            self._cache.put_records(
                jql=jql,
                spec_names=spec_names,
                include_heavy=include_heavy,
                records=records,
            )
        return records

    def project_issue(self, issue: dict[str, Any], specs: list[FieldSpec]) -> IssueRecord:
        return self._to_record(issue, specs)

    def search_local_records(
        self,
        *,
        store_query: IssueStoreQuery,
        specs: Iterable[str | FieldSpec],
    ) -> list[IssueRecord]:
        if self._issue_store is None:
            return []
        resolved_specs = self._registry.resolve(specs)
        raw_records = self._issue_store.query_records(store_query)
        return [self._project_stored_record(record, resolved_specs) for record in raw_records]

    def get_local_record(
        self,
        issue_key: str,
        *,
        specs: Iterable[str | FieldSpec],
    ) -> IssueRecord | None:
        if self._issue_store is None:
            return None
        stored = self._issue_store.get_record(issue_key)
        if stored is None:
            return None
        resolved_specs = self._registry.resolve(specs)
        return self._project_stored_record(stored, resolved_specs)

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

    @staticmethod
    def _project_stored_record(record: IssueRecord, specs: list[FieldSpec]) -> IssueRecord:
        return IssueRecord(
            key=record.key,
            id=record.id,
            raw=record.raw,
            fields=project_fields(record.raw, specs),
        )
