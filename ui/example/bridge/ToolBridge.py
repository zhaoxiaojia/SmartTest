from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, Signal

from support.logging import smart_log


def load_tool_access(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    return payload if isinstance(payload, dict) else {}


def build_tool_groups(personnel: dict[str, Any], account: str) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = [
        {
            "id": "common",
            "available": True,
            "tools": [],
        }
    ]
    clean_account = str(account or "").strip()
    employees = [item for item in personnel.get("employees", []) if isinstance(item, dict)]
    employee = next(
        (item for item in employees if str(item.get("account", "") or "") == clean_account),
        None,
    )
    is_developer = any(
        str(role or "").strip().casefold() == "developer"
        for role in (employee or {}).get("system_roles", []) or []
    )
    assigned_ids = {
        str(item.get("product_line_id", "") or "")
        for item in (employee or {}).get("assignments", []) or []
        if isinstance(item, dict)
    }
    product_lines = {
        str(item.get("id", "") or ""): item
        for item in personnel.get("product_lines", []) or []
        if isinstance(item, dict) and item.get("active", True)
    }
    for group_id in ("STB", "TV", "SmartHome", "IPTV"):
        tools = [{"id": "redmine"}] if group_id == "SmartHome" else []
        groups.append(
            {
                "id": group_id,
                "available": group_id in product_lines and (is_developer or group_id in assigned_ids),
                "tools": tools,
            }
        )

    expertise = {str(item) for item in (employee or {}).get("expertise_domains", []) or []}
    technical_centers = [
        item
        for item in personnel.get("technical_centers", []) or []
        if isinstance(item, dict) and item.get("active", True) and item.get("id") == "Wi-Fi"
    ]
    wifi_available = bool(technical_centers) and (
        is_developer
        or any(
            "Wi-Fi" in expertise or str(item.get("owner_account", "") or "") == clean_account
            for item in technical_centers
        )
    )
    groups.append(
        {
            "id": "Wi-Fi",
            "available": wifi_available,
            "tools": [],
        }
    )
    return groups


class ToolBridge(QObject):
    groupsChanged = Signal()

    def __init__(self, project_root: Path, auth_bridge: QObject):
        super().__init__(auth_bridge)
        self._auth_bridge = auth_bridge
        self._personnel_path = Path(project_root) / "config" / "personnel.json"
        self._personnel = load_tool_access(self._personnel_path)
        self._last_logged_signature: tuple[Any, ...] | None = None
        auth_bridge.authChanged.connect(self.groupsChanged)
        smart_log(
            "Tool access registry loaded (path=%s)",
            str(self._personnel_path),
            domain="ui",
            source="ToolBridge",
            extra={"personnel_path": str(self._personnel_path)},
        )
        self._groups()

    def _groups(self) -> list[dict[str, Any]]:
        account = str(getattr(self._auth_bridge, "username", "") or "").strip()
        groups = build_tool_groups(self._personnel, account)
        signature = tuple(
            (group["id"], group["available"], tuple(tool["id"] for tool in group["tools"]))
            for group in groups
        )
        if signature != self._last_logged_signature:
            summary = ",".join(
                f'{group["id"]}:{"|".join(tool["id"] for tool in group["tools"]) or "-"}'
                for group in groups
                if group["available"]
            )
            smart_log(
                "Tool groups resolved (account=%s, available=%s)",
                account or "<none>",
                summary or "<none>",
                domain="ui",
                source="ToolBridge",
            )
            self._last_logged_signature = signature
        localized = []
        for group in groups:
            row = dict(group)
            titles = {
                "common": self.tr("Common Tools"),
                "STB": self.tr("STB"),
                "TV": self.tr("TV"),
                "SmartHome": self.tr("SmartHome"),
                "IPTV": self.tr("IPTV"),
                "Wi-Fi": self.tr("Wi-Fi"),
            }
            row["title"] = titles[group["id"]]
            row["tools"] = [
                {**tool, "title": self.tr("Redmine Bug Clone"), "description": self.tr("Browse and sign in to SmartHome Redmine.")}
                for tool in row["tools"]
            ]
            localized.append(row)
        return localized

    groups = Property("QVariantList", _groups, notify=groupsChanged)
