from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Iterable

from PySide6.QtCore import QStandardPaths

from support.jira_integration.core import IssueStore, UnifiedIssue


_CACHE_LOCK = threading.RLock()
_VERSION = 2
_DEFAULT_VIEW_ID = "__default__"
_FILTER_KEYS = ("project", "status", "type", "subject", "text")
_SNAPSHOT_KEYS = {
    "version",
    "account",
    "updated_at",
    "issue_list",
    "selected_issue_id",
    "filters",
    "quick_views",
    "project_options",
    "watched_issue_ids",
}
_VIEW_KEYS = {"updated_at", "issue_ids", "selected_issue_id", "filters"}
_DETAIL_FIELDS = (
    "reporter",
    "created_at",
    "description",
    "detail_fields",
    "people_fields",
    "date_fields",
    "extra_sections",
    "comments",
    "attachments",
    "detail_state",
    "detail_error",
)
_ANALYSIS_STRING_FIELDS = (
    "risk",
    "age_text",
    "party",
    "reason",
    "responsibility_type",
    "stale_type",
)
_ANALYSIS_NUMBER_FIELDS = (
    "elapsed_hours",
    "threshold_hours",
    "overdue_hours",
    "stale_elapsed_hours",
    "stale_threshold_hours",
)
_FIELD_STRING_KEYS = {"label", "url", "kind", "avatarUrl"}
_COMMENT_STRING_KEYS = {"id", "author", "time", "body", "avatarUrl"}
_ATTACHMENT_STRING_KEYS = {
    "id",
    "filename",
    "name",
    "size",
    "author",
    "createdAt",
    "detailUrl",
    "downloadUrl",
    "url",
    "thumbnailUrl",
    "kind",
    "time",
}


def cache_path(account: str) -> Path:
    exact_account = str(account or "")
    account_id = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        exact_account or "default",
    ).strip("._") or "default"
    digest = hashlib.sha256(exact_account.encode("utf-8")).hexdigest()[:12]
    base = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    root = Path(base) if base else Path.home() / "AppData" / "Local" / "Amlogic" / "SmartTest"
    return root / "redmine" / f"{account_id}_{digest}_context.json"


def load_view_payload(account: str) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        return _read_snapshot(account)


def load_view(account: str) -> dict[str, Any] | None:
    snapshot = load_view_payload(account)
    if snapshot is None:
        return None
    return _loaded_view(snapshot, _DEFAULT_VIEW_ID)


def save_view(account: str, store: IssueStore, *, filters: dict[str, Any] | None = None) -> Path:
    return _save_issue_view(account, _DEFAULT_VIEW_ID, store, filters=filters)


def load_quick_view(account: str, quick_view_id: str) -> dict[str, Any] | None:
    snapshot = load_view_payload(account)
    if snapshot is None:
        return None
    return _loaded_view(snapshot, str(quick_view_id or ""))


def save_quick_view(
    account: str,
    quick_view_id: str,
    store: IssueStore,
    *,
    filters: dict[str, Any] | None = None,
) -> Path:
    return _save_issue_view(account, str(quick_view_id or ""), store, filters=filters)


def reconcile_issue_records(
    account: str,
    records: Iterable[UnifiedIssue],
    *,
    known_records: Iterable[UnifiedIssue] = (),
) -> list[UnifiedIssue]:
    incoming = list(IssueStore(records).issue_list)
    known = list(IssueStore(known_records).issue_list)
    with _CACHE_LOCK:
        snapshot = _read_snapshot(account) if str(account or "") else None
        cached = _issues(snapshot["issue_list"]) if snapshot is not None else []
        canonical = _merge_issues(cached, known)
        canonical = _merge_issues(canonical.values(), incoming)
    return [canonical[issue.id] for issue in incoming]


def load_project_options(account: str) -> list[dict[str, Any]]:
    snapshot = load_view_payload(account)
    if snapshot is None:
        return []
    return [dict(option) for option in snapshot["project_options"]]


def save_project_options(account: str, options: list[dict[str, Any]]) -> Path:
    if not isinstance(options, list) or not _valid_project_options(options):
        raise TypeError("project_options must contain string maps")
    clean = [dict(option) for option in options]
    return _update_snapshot(account, lambda snapshot: snapshot.update(project_options=clean))


def load_filters(account: str) -> dict[str, str]:
    snapshot = load_view_payload(account)
    return dict(snapshot["filters"]) if snapshot is not None else {}


def load_watched_issue_ids(account: str) -> list[str]:
    snapshot = load_view_payload(account)
    return list(snapshot["watched_issue_ids"]) if snapshot is not None else []


def save_watched_issue_ids(account: str, issue_ids: list[str]) -> Path:
    if not isinstance(issue_ids, list) or not _string_list(issue_ids):
        raise TypeError("watched_issue_ids must contain strings")
    clean = _unique_ids(issue_ids)
    return _update_snapshot(account, lambda snapshot: snapshot.update(watched_issue_ids=clean))


def _save_issue_view(
    account: str,
    view_id: str,
    store: IssueStore,
    *,
    filters: dict[str, Any] | None,
) -> Path:
    if not isinstance(store, IssueStore):
        raise TypeError("store must be an IssueStore")
    records = list(store.issue_list)
    selected_issue_id = str(store.selected_id or "")
    normalized_filters = _filters(filters)

    def update(snapshot: dict[str, Any]) -> None:
        merged = _merge_issues(_issues(snapshot["issue_list"]), records)
        snapshot["issue_list"] = [issue.to_dict() for issue in merged.values()]
        if view_id == _DEFAULT_VIEW_ID:
            snapshot["selected_issue_id"] = selected_issue_id
            snapshot["filters"] = normalized_filters
        quick_views = dict(snapshot["quick_views"])
        quick_views[view_id] = {
            "updated_at": _timestamp(),
            "issue_ids": [issue.id for issue in records],
            "selected_issue_id": selected_issue_id,
            "filters": normalized_filters,
        }
        snapshot["quick_views"] = quick_views

    return _update_snapshot(account, update)


def _loaded_view(snapshot: dict[str, Any], view_id: str) -> dict[str, Any] | None:
    view = snapshot["quick_views"].get(view_id)
    if not isinstance(view, dict):
        return None
    all_issues = {issue.id: issue for issue in _issues(snapshot["issue_list"])}
    issues = [all_issues[issue_id] for issue_id in view["issue_ids"] if issue_id in all_issues]
    if len(issues) != len(view["issue_ids"]):
        return None
    selected_issue_id = str(view.get("selected_issue_id") or "")
    if selected_issue_id and selected_issue_id not in {issue.id for issue in issues}:
        selected_issue_id = ""
    return {
        "issue_list": issues,
        "selected_issue_id": selected_issue_id,
        "filters": dict(view["filters"]),
    }


def _update_snapshot(account: str, update: Callable[[dict[str, Any]], None]) -> Path:
    path = cache_path(account)
    with _CACHE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = _read_snapshot(account) or _empty_snapshot(account)
        update(snapshot)
        snapshot["version"] = _VERSION
        snapshot["account"] = str(account or "")
        snapshot["updated_at"] = _timestamp()
        normalized = _normalize_snapshot(snapshot, account)
        if normalized is None:
            raise ValueError("Invalid Redmine cache snapshot")
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(normalized, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.close(handle)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
    return path


def _read_snapshot(account: str) -> dict[str, Any] | None:
    path = cache_path(account)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _normalize_snapshot(raw, account)


def _normalize_snapshot(raw: Any, account: str) -> dict[str, Any] | None:
    if (
        not isinstance(raw, dict)
        or set(raw) != _SNAPSHOT_KEYS
        or raw.get("version") != _VERSION
        or not isinstance(raw.get("account"), str)
        or str(raw.get("account") or "") != str(account or "")
        or not isinstance(raw.get("issue_list"), list)
        or not isinstance(raw.get("quick_views"), dict)
        or not isinstance(raw.get("project_options"), list)
        or not isinstance(raw.get("watched_issue_ids"), list)
    ):
        return None
    if (
        not isinstance(raw.get("updated_at"), str)
        or not isinstance(raw.get("selected_issue_id"), str)
        or not _valid_filters(raw.get("filters"))
        or not _valid_project_options(raw["project_options"])
        or not _string_list(raw["watched_issue_ids"])
        or any(not _valid_issue_record(record) for record in raw["issue_list"])
        or any(not isinstance(view_id, str) for view_id in raw["quick_views"])
    ):
        return None
    try:
        issues = _issues(raw["issue_list"])
    except (TypeError, ValueError):
        return None
    issue_ids = {issue.id for issue in issues}
    if len(issue_ids) != len(issues):
        return None
    quick_views: dict[str, dict[str, Any]] = {}
    for view_id, source in raw["quick_views"].items():
        if (
            not isinstance(source, dict)
            or set(source) != _VIEW_KEYS
            or not isinstance(source.get("updated_at"), str)
            or not isinstance(source.get("issue_ids"), list)
            or not _string_list(source["issue_ids"])
            or not isinstance(source.get("selected_issue_id"), str)
            or not _valid_filters(source.get("filters"))
        ):
            return None
        view_issue_ids = _unique_ids(source["issue_ids"])
        if any(issue_id not in issue_ids for issue_id in view_issue_ids):
            return None
        selected_id = str(source.get("selected_issue_id") or "")
        if selected_id and selected_id not in view_issue_ids:
            selected_id = ""
        quick_views[str(view_id)] = {
            "updated_at": str(source.get("updated_at") or ""),
            "issue_ids": view_issue_ids,
            "selected_issue_id": selected_id,
            "filters": _filters(source.get("filters")),
        }
    selected_issue_id = str(raw.get("selected_issue_id") or "")
    if selected_issue_id and selected_issue_id not in issue_ids:
        selected_issue_id = ""
    return {
        "version": _VERSION,
        "account": str(account or ""),
        "updated_at": str(raw.get("updated_at") or ""),
        "issue_list": [issue.to_dict() for issue in issues],
        "selected_issue_id": selected_issue_id,
        "filters": _filters(raw.get("filters")),
        "quick_views": quick_views,
        "project_options": [
            dict(option) for option in raw["project_options"] if isinstance(option, dict)
        ],
        "watched_issue_ids": _unique_ids(raw["watched_issue_ids"]),
    }


def _empty_snapshot(account: str) -> dict[str, Any]:
    return {
        "version": _VERSION,
        "account": str(account or ""),
        "updated_at": "",
        "issue_list": [],
        "selected_issue_id": "",
        "filters": _filters({}),
        "quick_views": {},
        "project_options": [],
        "watched_issue_ids": [],
    }


def _issues(records: list[Any]) -> list[UnifiedIssue]:
    return [UnifiedIssue.from_dict(record) for record in records]


def _merge_issues(
    existing_records: Iterable[UnifiedIssue],
    incoming_records: Iterable[UnifiedIssue],
) -> dict[str, UnifiedIssue]:
    merged = {issue.id: issue for issue in existing_records}
    for issue in incoming_records:
        existing = merged.get(issue.id)
        merged[issue.id] = _merge_issue(existing, issue) if existing else issue
    return merged


def _merge_issue(existing: UnifiedIssue, incoming: UnifiedIssue) -> UnifiedIssue:
    changes = {}
    if existing.detail_state == "loaded" and incoming.detail_state != "loaded":
        for field_name in _DETAIL_FIELDS:
            changes[field_name] = getattr(existing, field_name)
    incoming_checked = bool(incoming.clone.get("checked"))
    if existing.clone and not incoming_checked:
        changes["clone"] = existing.clone
    return replace(incoming, **changes) if changes else incoming


def _valid_issue_record(record: Any) -> bool:
    defaults = UnifiedIssue().to_dict()
    if not isinstance(record, dict) or set(record) != set(defaults):
        return False
    for field_name, default in defaults.items():
        value = record[field_name]
        if isinstance(default, str) and not isinstance(value, str):
            return False
        if isinstance(default, dict):
            if not isinstance(value, dict) or any(
                not isinstance(key, str) for key in value
            ):
                return False
        if isinstance(default, list):
            if not isinstance(value, list) or any(
                not isinstance(item, dict) for item in value
            ):
                return False
    if (
        not record["id"].strip()
        or not _valid_string_values(
            record["project"],
            {"id", "identifier", "name", "url"},
        )
        or not _valid_string_values(record["status"], {"name"})
        or not _valid_string_values(record["issue_type"], {"name"})
        or not _valid_string_values(record["priority"], {"name"})
        or not _valid_string_values(record["assignee"], {"name", "displayName"})
        or not _valid_string_values(record["reporter"], {"name", "displayName"})
        or not _valid_clone(record["clone"])
        or not _valid_analysis(record["analysis"])
        or not _valid_field_rows(record["detail_fields"])
        or not _valid_field_rows(record["people_fields"])
        or not _valid_field_rows(record["date_fields"])
        or not _valid_extra_sections(record["extra_sections"])
        or not _valid_scalar_rows(record["comments"], _COMMENT_STRING_KEYS)
        or not _valid_scalar_rows(record["attachments"], _ATTACHMENT_STRING_KEYS)
    ):
        return False
    try:
        UnifiedIssue.from_dict(record)
    except (TypeError, ValueError):
        return False
    return True


def _valid_string_values(value: dict[str, Any], keys: set[str]) -> bool:
    return all(key not in value or isinstance(value[key], str) for key in keys)


def _valid_clone(value: dict[str, Any]) -> bool:
    return (
        _valid_string_values(value, {"state", "issue_key", "issue_url"})
        and ("checked" not in value or isinstance(value["checked"], bool))
    )


def _valid_analysis(value: dict[str, Any]) -> bool:
    return (
        _valid_string_values(value, set(_ANALYSIS_STRING_FIELDS))
        and all(
            key not in value
            or value[key] is None
            or (
                isinstance(value[key], (int, float))
                and not isinstance(value[key], bool)
            )
            for key in _ANALYSIS_NUMBER_FIELDS
        )
    )


def _valid_field_rows(value: list[dict[str, Any]]) -> bool:
    return all(
        _valid_string_values(row, _FIELD_STRING_KEYS)
        and ("value" not in row or _safe_scalar_or_list(row["value"]))
        and (
            "values" not in row
            or isinstance(row["values"], list)
            and all(_safe_scalar(item) for item in row["values"])
        )
        and all(_safe_scalar_or_list(item) for item in row.values())
        for row in value
    )


def _valid_extra_sections(value: list[dict[str, Any]]) -> bool:
    return all(
        _valid_string_values(row, {"title"})
        and isinstance(row.get("fields", []), list)
        and _valid_field_rows(row.get("fields", []))
        and all(
            key == "fields" or _safe_scalar_or_list(item)
            for key, item in row.items()
        )
        for row in value
    )


def _valid_scalar_rows(
    value: list[dict[str, Any]],
    string_keys: set[str],
) -> bool:
    return all(
        _valid_string_values(row, string_keys)
        and all(_safe_scalar_or_list(item) for item in row.values())
        for row in value
    )


def _safe_scalar_or_list(value: Any) -> bool:
    return _safe_scalar(value) or (
        isinstance(value, list) and all(_safe_scalar(item) for item in value)
    )


def _safe_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _valid_filters(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(_FILTER_KEYS)
        and all(isinstance(value[key], str) for key in _FILTER_KEYS)
    )


def _valid_project_options(value: list[Any]) -> bool:
    return all(
        isinstance(option, dict)
        and all(isinstance(key, str) for key in option)
        and all(isinstance(item, str) for item in option.values())
        for option in value
    )


def _string_list(value: list[Any]) -> bool:
    return all(isinstance(item, str) for item in value)


def _filters(source: Any) -> dict[str, str]:
    if source is None:
        values = {}
    elif not isinstance(source, dict):
        raise TypeError("filters must be a string map")
    else:
        values = source
    if any(key not in _FILTER_KEYS for key in values) or any(
        not isinstance(value, str) for value in values.values()
    ):
        raise TypeError("filters must be a string map")
    return {key: values.get(key, "") for key in _FILTER_KEYS}


def _unique_ids(values: list[Any]) -> list[str]:
    return list(
        dict.fromkeys(
            value.strip()
            for value in values
            if value.strip()
        )
    )


def _timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
