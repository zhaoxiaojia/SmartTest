from __future__ import annotations

from typing import Any, Callable

from jira_tool.services.requests import JiraAnalysisRequest, JiraBrowseRequest


class JiraWorkspaceService:
    def __init__(self, *, browse_service, analysis_service):
        self._browse_service = browse_service
        self._analysis_service = analysis_service

    def fetch_saved_filters(self) -> list[dict[str, str]]:
        return self._browse_service.fetch_saved_filters()

    def browse(
        self,
        *,
        worker_id: int,
        selected_issue_index: int,
        raw_jql_text: str,
        project_ids_csv: str,
        board_id: str,
        board_label: str,
        timeframe_id: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        include_comments: bool,
        include_links: bool,
        only_mine: bool,
        start_at: int,
        append: bool,
        translated_state: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        request_values = locals().copy()
        request_values.pop("self")
        return self._browse_service.browse(JiraBrowseRequest(**request_values))

    def fetch_issue_detail(
        self,
        *,
        worker_id: int,
        issue_key: str,
        include_comments: bool,
        include_links: bool,
    ) -> dict[str, Any]:
        return self._browse_service.fetch_issue_detail(
            worker_id=worker_id,
            issue_key=issue_key,
            include_comments=include_comments,
            include_links=include_links,
        )

    def analyze(
        self,
        *,
        worker_id: int,
        raw_jql_text: str,
        project_ids_csv: str,
        board_id: str,
        board_label: str,
        timeframe_id: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        include_comments: bool,
        include_links: bool,
        only_mine: bool,
        include_user_message: bool,
        prompt: str,
        translated_state: Callable[..., dict[str, Any]],
        raw_state: Callable[[str], dict[str, Any]],
        assistant_timestamp: str,
    ) -> dict[str, Any]:
        request_values = locals().copy()
        request_values.pop("self")
        return self._analysis_service.analyze(JiraAnalysisRequest(**request_values))
