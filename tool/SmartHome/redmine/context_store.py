from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths

from tool.SmartHome.redmine.view_model import empty_view


def cache_path(account: str) -> Path:
    account_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", account or "default").strip("._") or "default"
    base = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    root = Path(base) if base else Path.home() / "AppData" / "Local" / "Amlogic" / "SmartTest"
    return root / "redmine" / f"{account_id}_context.json"


def load_view_payload(account: str) -> dict[str, Any] | None:
    path = cache_path(account)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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
    path = cache_path(account)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_view_payload(account) or {}
    payload = {
        **existing,
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
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_quick_view(account: str, quick_view_id: str, *, all_projects: str, all_statuses: str) -> dict[str, Any] | None:
    payload = load_view_payload(account) or {}
    loaded = _view_from_payload((payload.get("quickViews") or {}).get(quick_view_id), all_projects=all_projects, all_statuses=all_statuses)
    if loaded and loaded["selectedIssue"] and not any(key in loaded["selectedIssue"] for key in ("description", "detailsFields", "comments", "attachments")):
        loaded["selectedIssue"] = {}
        loaded["selectedIssueId"] = ""
    return loaded


def save_quick_view(account: str, quick_view_id: str, view: dict[str, Any]) -> Path:
    path = cache_path(account)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = load_view_payload(account) or {}
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_project_options(account: str) -> list[dict[str, Any]]:
    payload = load_view_payload(account) or {}
    return [dict(option) for option in payload.get("projectOptions") or [] if isinstance(option, dict)]


def save_project_options(account: str, options: list[dict[str, Any]]) -> Path:
    path = cache_path(account)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = load_view_payload(account) or {}
    payload["projectOptions"] = [dict(option) for option in options if isinstance(option, dict)]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_filters(account: str) -> dict[str, str]:
    payload = load_view_payload(account) or {}
    filters = dict(payload.get("filters") or (payload.get("context") or {}).get("filters") or {})
    return {key: str(filters.get(key, "") or "") for key in ("project", "status", "type", "text")}
