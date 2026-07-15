from __future__ import annotations

from typing import Any

from support.jira_integration.services.issue_service import JiraIssueService
from jira.payloads import build_browse_result, build_detail_result, build_scope_context
from jira.presenter import record_to_issue_row
from jira.query_builder import build_base_jql
from jira.requests import JiraBrowseRequest
from jira.specs import browse_specs, detail_specs


class JiraBrowseService:
    def __init__(self, *, base_url: str, issue_service: JiraIssueService, max_display_issues: int = 50):
        self._base_url = base_url
        self._issue_service = issue_service
        self._max_display_issues = max_display_issues

    def fetch_saved_filters(self) -> list[dict[str, str]]:
        return self._normalize_saved_filters(self._issue_service.fetch_favourite_filters())

    def browse(self, request: JiraBrowseRequest) -> dict[str, Any]:
        effective_jql = build_base_jql(
            raw_jql_text=request.raw_jql_text,
            project_ids_csv=request.project_ids_csv,
            board_id=request.board_id,
            timeframe_id=request.timeframe_id,
            status_ids_csv=request.status_ids_csv,
            priority_ids_csv=request.priority_ids_csv,
            issue_type_ids_csv=request.issue_type_ids_csv,
            keyword_text=request.keyword_text,
            assignee_text=request.assignee_text,
            reporter_text=request.reporter_text,
            labels_text=request.labels_text,
            only_mine=request.only_mine,
        )
        page, records = self._issue_service.search_page_records(
            effective_jql,
            specs=browse_specs(),
            start_at=request.start_at,
            max_results=min(self._max_display_issues, 25),
        )
        issues = [record_to_issue_row(record) for record in records]
        return build_browse_result(
            worker_id=request.worker_id,
            base_url=self._base_url,
            loaded_count=request.start_at + len(issues),
            total_count=page.total,
            issues=issues,
            append=request.append,
            selected_issue_index=0 if not request.append else request.selected_issue_index,
            next_start_at=page.start_at + len(page.issues),
            can_load_more=(page.start_at + len(page.issues)) < page.total,
            scope=build_scope_context(
                raw_jql_text=request.raw_jql_text,
                project_ids_csv=request.project_ids_csv,
                board_label=request.board_label,
                timeframe_label=request.timeframe_label,
                status_ids_csv=request.status_ids_csv,
                priority_ids_csv=request.priority_ids_csv,
                issue_type_ids_csv=request.issue_type_ids_csv,
                keyword_text=request.keyword_text,
                assignee_text=request.assignee_text,
                reporter_text=request.reporter_text,
                labels_text=request.labels_text,
                include_comments=request.include_comments,
                include_links=request.include_links,
                only_mine=request.only_mine,
            ),
            translated_state=request.translated_state,
        )

    def fetch_issue_detail(self, *, worker_id: int, issue_key: str, include_comments: bool, include_links: bool):
        record = self._issue_service.hydrate_issue(
            issue_key,
            specs=detail_specs(include_comments=include_comments, include_links=include_links),
        )
        return build_detail_result(worker_id=worker_id, issue=record_to_issue_row(record))

    @staticmethod
    def _normalize_saved_filters(items: list[dict[str, Any]]) -> list[dict[str, str]]:
        normalized = []
        seen_ids = set()
        for item in items:
            filter_id = str(item.get("id", "") or "").strip()
            name = str(item.get("name", "") or "").strip()
            jql = str(item.get("jql", "") or "").strip()
            if not filter_id or not name or not jql or filter_id in seen_ids:
                continue
            seen_ids.add(filter_id)
            normalized.append({"id": filter_id, "name": name, "jql": jql})
        return normalized
