from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths

from tool.SmartHome.redmine.view_model import empty_view


_CACHE_LOCK = threading.RLock()


def cache_path(account: str) -> Path:
    account_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", account or "default").strip("._") or "default"
    base = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    root = Path(base) if base else Path.home() / "AppData" / "Local" / "Amlogic" / "SmartTest"
    return root / "redmine" / f"{account_id}_context.json"


def load_view_payload(account: str) -> dict[str, Any] | None:
    path = cache_path(account)
    with _CACHE_LOCK:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError):
            return None


def _update_payload(account: str, update) -> Path:
    path = cache_path(account)
    with _CACHE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = load_view_payload(account) or {}
        update(payload)
        handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
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


def _view_from_payload(payload: dict[str, Any] | None, *, all_projects: str, all_statuses: str) -> dict[str, Any] | None:
    if not payload:
        return None
    selected = dict(payload.get("selectedIssue") or {})
    return {
        **empty_view(all_projects, all_statuses),
        "context_payload": dict(payload.get("context") or {}),
        "filters": dict(payload.get("filters") or (payload.get("context") or {}).get("filters") or {}),
        "projectFilterLabels": list(payload.get("projectFilterLabels") or [all_projects]),
        "statusFilterLabels": list(payload.get("statusFilterLabels") or [all_statuses]),
        "typeFilterLabels": list(payload.get("typeFilterLabels") or ["All types"]),
        "issueRows": [dict(row) for row in payload.get("issueRows") or [] if isinstance(row, dict)],
        "selectedIssue": selected,
        "selectedIssueId": str(selected.get("id") or selected.get("key") or ""),
        "actionableIssues": [dict(row) for row in payload.get("actionableIssues") or [] if isinstance(row, dict)],
    }


def load_view(account: str, *, all_projects: str, all_statuses: str) -> dict[str, Any] | None:
    return _view_from_payload(load_view_payload(account), all_projects=all_projects, all_statuses=all_statuses)


def save_view(account: str, view: dict[str, Any]) -> Path:
    def update(payload):
        payload.update({
        "version": 1,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "context": view.get("context_payload", {}),
        "filters": view.get("filters", {}),
        "projectFilterLabels": view.get("projectFilterLabels", []),
        "statusFilterLabels": view.get("statusFilterLabels", []),
        "typeFilterLabels": view.get("typeFilterLabels", []),
        "issueRows": view.get("issueRows", []),
        "selectedIssue": view.get("selectedIssue", {}),
        "actionableIssues": view.get("actionableIssues", []),
        })
    return _update_payload(account, update)


def load_quick_view(account: str, quick_view_id: str, *, all_projects: str, all_statuses: str) -> dict[str, Any] | None:
    payload = load_view_payload(account) or {}
    loaded = _view_from_payload((payload.get("quickViews") or {}).get(quick_view_id), all_projects=all_projects, all_statuses=all_statuses)
    if loaded and loaded["selectedIssue"] and not any(key in loaded["selectedIssue"] for key in ("description", "detailsFields", "comments", "attachments")):
        loaded["selectedIssue"] = {}
        loaded["selectedIssueId"] = ""
    return loaded


def save_quick_view(account: str, quick_view_id: str, view: dict[str, Any]) -> Path:
    def update(payload):
        quick_views = dict(payload.get("quickViews") or {})
        quick_views[quick_view_id] = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "context": view.get("context_payload", {}),
        "filters": view.get("filters", {}),
        "projectFilterLabels": view.get("projectFilterLabels", []),
        "statusFilterLabels": view.get("statusFilterLabels", []),
        "typeFilterLabels": view.get("typeFilterLabels", []),
        "issueRows": view.get("issueRows", []),
        "selectedIssue": view.get("selectedIssue", {}),
        "actionableIssues": view.get("actionableIssues", []),
        }
        payload["quickViews"] = quick_views
    return _update_payload(account, update)


def load_project_options(account: str) -> list[dict[str, Any]]:
    payload = load_view_payload(account) or {}
    return [dict(option) for option in payload.get("projectOptions") or [] if isinstance(option, dict)]


def save_project_options(account: str, options: list[dict[str, Any]]) -> Path:
    def update(payload):
        payload["projectOptions"] = [dict(option) for option in options if isinstance(option, dict)]
    return _update_payload(account, update)


def load_filters(account: str) -> dict[str, str]:
    payload = load_view_payload(account) or {}
    filters = dict(payload.get("filters") or (payload.get("context") or {}).get("filters") or {})
    return {key: str(filters.get(key, "") or "") for key in ("project", "status", "type", "subject", "text")}


def load_watched_issue_ids(account: str) -> list[str]:
    payload = load_view_payload(account) or {}
    return [str(value) for value in payload.get("watchedIssueIds") or [] if str(value).strip()]


def save_watched_issue_ids(account: str, issue_ids: list[str]) -> Path:
    def update(payload):
        payload["watchedIssueIds"] = list(dict.fromkeys(str(value).strip() for value in issue_ids if str(value).strip()))
    return _update_payload(account, update)
