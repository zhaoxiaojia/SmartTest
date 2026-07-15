from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class JiraBrowseRequest:
    worker_id: int
    selected_issue_index: int
    raw_jql_text: str
    project_ids_csv: str
    board_id: str
    board_label: str
    timeframe_id: str
    timeframe_label: str
    status_ids_csv: str
    priority_ids_csv: str
    issue_type_ids_csv: str
    keyword_text: str
    assignee_text: str
    reporter_text: str
    labels_text: str
    include_comments: bool
    include_links: bool
    only_mine: bool
    start_at: int
    append: bool
    translated_state: Callable[..., dict[str, Any]]


@dataclass(frozen=True, slots=True)
class JiraAnalysisRequest:
    worker_id: int
    raw_jql_text: str
    project_ids_csv: str
    board_id: str
    board_label: str
    timeframe_id: str
    timeframe_label: str
    status_ids_csv: str
    priority_ids_csv: str
    issue_type_ids_csv: str
    keyword_text: str
    assignee_text: str
    reporter_text: str
    labels_text: str
    include_comments: bool
    include_links: bool
    only_mine: bool
    include_user_message: bool
    prompt: str
    translated_state: Callable[..., dict[str, Any]]
    raw_state: Callable[[str], dict[str, Any]]
    assistant_timestamp: str
