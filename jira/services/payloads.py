from __future__ import annotations

from typing import Any, Callable


def build_scope_context(
    *,
    raw_jql_text: str,
    project_ids_csv: str,
    board_label: str,
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
) -> dict[str, Any]:
    return {
        "raw_jql_text": raw_jql_text,
        "project_ids_csv": project_ids_csv,
        "board_label": board_label,
        "timeframe_label": timeframe_label,
        "status_ids_csv": status_ids_csv,
        "priority_ids_csv": priority_ids_csv,
        "issue_type_ids_csv": issue_type_ids_csv,
        "keyword_text": keyword_text,
        "assignee_text": assignee_text,
        "reporter_text": reporter_text,
        "labels_text": labels_text,
        "include_comments": include_comments,
        "include_links": include_links,
        "only_mine": only_mine,
    }


def build_browse_result(
    *,
    worker_id: int,
    base_url: str,
    loaded_count: int,
    total_count: int,
    issues: list[dict[str, Any]],
    append: bool,
    selected_issue_index: int,
    next_start_at: int,
    can_load_more: bool,
    scope: dict[str, Any],
    translated_state: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    return {
        "mode": "browse",
        "worker_id": worker_id,
        "connected": True,
        "status_state": translated_state(
            "Connected to {base_url} | loaded {loaded} of {total}",
            base_url=base_url,
            loaded=loaded_count,
            total=total_count,
        ),
        "issues": issues,
        "selected_issue_index": selected_issue_index,
        "displayed_total": total_count,
        "analysis_summary_state": translated_state(
            "Loaded {loaded} of {total} issues for browsing. Select an issue or ask a question for deeper analysis.",
            loaded=loaded_count,
            total=total_count,
        ),
        "analysis_actions": [],
        "assistant_message": "",
        "assistant_timestamp": "",
        "append": append,
        "next_start_at": next_start_at,
        "can_load_more": can_load_more,
        "scope": scope,
    }


def build_detail_result(
    *,
    worker_id: int,
    issue: dict[str, Any],
) -> dict[str, Any]:
    return {
        "worker_id": worker_id,
        "issue": issue,
    }


def build_analysis_result(
    *,
    worker_id: int,
    base_url: str,
    returned_count: int,
    total_count: int,
    issues: list[dict[str, Any]],
    analysis_text: str,
    append: bool,
    next_start_at: int,
    can_load_more: bool,
    scope: dict[str, Any],
    translated_state: Callable[..., dict[str, Any]],
    raw_state: Callable[[str], dict[str, Any]],
    assistant_timestamp: str,
) -> dict[str, Any]:
    return {
        "mode": "analyze",
        "worker_id": worker_id,
        "connected": True,
        "status_state": translated_state(
            "Connected to {base_url} | analyzed {returned} of {total}",
            base_url=base_url,
            returned=returned_count,
            total=total_count,
        ),
        "issues": issues,
        "selected_issue_index": 0,
        "displayed_total": total_count,
        "analysis_summary_state": raw_state(analysis_text),
        "assistant_message": analysis_text,
        "assistant_timestamp": assistant_timestamp,
        "append": append,
        "next_start_at": next_start_at,
        "can_load_more": can_load_more,
        "scope": scope,
    }
