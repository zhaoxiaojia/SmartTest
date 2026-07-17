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


def load_view(account: str, *, all_projects: str, all_statuses: str) -> dict[str, Any] | None:
    payload = load_view_payload(account)
    if not payload:
        return None
    selected = dict(payload.get("selectedIssue") or {})
    return {
        **empty_view(all_projects, all_statuses),
        "context_payload": dict(payload.get("context") or {}),
        "projectFilterLabels": list(payload.get("projectFilterLabels") or [all_projects]),
        "statusFilterLabels": list(payload.get("statusFilterLabels") or [all_statuses]),
        "issueRows": [dict(row) for row in payload.get("issueRows") or [] if isinstance(row, dict)],
        "selectedIssue": selected,
        "selectedIssueId": str(selected.get("id") or selected.get("key") or ""),
    }


def save_view(account: str, view: dict[str, Any]) -> Path:
    path = cache_path(account)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "context": view.get("context_payload", {}),
        "projectFilterLabels": view.get("projectFilterLabels", []),
        "statusFilterLabels": view.get("statusFilterLabels", []),
        "issueRows": view.get("issueRows", []),
        "selectedIssue": view.get("selectedIssue", {}),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
