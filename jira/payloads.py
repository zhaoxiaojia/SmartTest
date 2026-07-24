from __future__ import annotations

from typing import Any, Callable

from jira.conversation import is_safe_template


def build_scope_context(
    *,
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
) -> dict[str, Any]:
    return {
        "raw_jql_text": raw_jql_text,
        "project_ids_csv": project_ids_csv,
        "board_id": board_id,
        "board_label": board_label,
        "timeframe_id": timeframe_id,
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
        "analysis_summary": "",
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
        "analysis_summary": analysis_text,
        "analysis_actions": [],
        "assistant_message": analysis_text,
        "assistant_timestamp": assistant_timestamp,
        "append": append,
        "next_start_at": next_start_at,
        "can_load_more": can_load_more,
        "scope": scope,
    }


def validate_workspace_result(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Jira workspace result must be a mapping")
    result = dict(payload)
    mode = result.get("mode")
    if mode not in {"browse", "analyze"}:
        raise ValueError("mode must be 'browse' or 'analyze'")
    result["worker_id"] = _integer_field(result, "worker_id")
    result["selected_issue_index"] = _integer_field(result, "selected_issue_index")
    result["displayed_total"] = _integer_field(result, "displayed_total")
    result["next_start_at"] = _integer_field(result, "next_start_at")
    for field in ("append", "can_load_more", "connected"):
        if not isinstance(result.get(field), bool):
            raise ValueError(f"{field} must be a boolean")

    issues = result.get("issues")
    if not isinstance(issues, list):
        raise ValueError("issues must be a list")
    result["issues"] = [
        safe_issue
        for issue in issues
        if (safe_issue := _safe_issue_row(issue)) is not None
    ]
    scope = result.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("scope must be a mapping")
    result["scope"] = _json_safe_copy(scope, field="scope")
    result["status_state"] = _display_state(result.get("status_state"), field="status_state")
    result["analysis_summary_state"] = _display_state(
        result.get("analysis_summary_state"),
        field="analysis_summary_state",
    )
    for field in (
        "analysis_summary",
        "assistant_message",
        "assistant_timestamp",
    ):
        if not isinstance(result.get(field), str):
            raise ValueError(f"{field} must be text")
    if "status_text" in result and not isinstance(result["status_text"], str):
        raise ValueError("status_text must be text")
    actions = result.get("analysis_actions")
    if not isinstance(actions, list) or not all(isinstance(item, str) for item in actions):
        raise ValueError("analysis_actions must be a list of text values")
    result["analysis_actions"] = list(actions)
    return result


def _integer_field(payload: dict[str, Any], field: str) -> int:
    if field not in payload:
        raise ValueError(f"{field} is required")
    value = payload[field]
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        clean = value.strip()
        if clean and clean.lstrip("+-").isdigit():
            return int(clean)
    raise ValueError(f"{field} must be an integer")


def _safe_issue_row(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    issue_key = str(value.get("keyId", "") or "").strip()
    if not issue_key:
        return None
    try:
        row = _json_safe_copy(value, field="issue")
    except ValueError:
        return None
    row["keyId"] = issue_key
    return row


def _display_state(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a display-state mapping")
    kind = value.get("kind")
    if kind == "translated":
        if not is_safe_template(value.get("template"), value.get("values")):
            raise ValueError(f"{field} translated state is invalid")
    elif kind == "raw":
        if not isinstance(value.get("text"), str):
            raise ValueError(f"{field} raw state is invalid")
    else:
        raise ValueError(f"{field} kind is invalid")
    return _json_safe_copy(value, field=field)


def _json_safe_copy(value: Any, *, field: str) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_json_safe_copy(item, field=field) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError(f"{field} mapping keys must be text")
        return {
            key: _json_safe_copy(item, field=field)
            for key, item in value.items()
        }
    raise ValueError(f"{field} contains a non-JSON value")
