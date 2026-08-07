from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property

def load_tool_access(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    return payload if isinstance(payload, dict) else {}


def amlogic_employees(personnel: dict[str, Any]) -> list[dict[str, Any]]:
    employees = []
    departments = ((personnel.get("amlogic") or {}).get("departments") or {})
    for department, node in departments.items():
        for source in (node or {}).get("employees") or []:
            if not isinstance(source, dict):
                continue
            employee = dict(source)
            organization = dict(employee.get("organization") or {})
            organization["department"] = str(department or "")
            employee["organization"] = organization
            employees.append(employee)
    return employees


def employee_department(personnel: dict[str, Any], account: str) -> str:
    clean_account = str(account or "").strip()
    if not clean_account:
        return ""
    matches = [
        str((employee.get("organization") or {}).get("department") or "")
        for employee in amlogic_employees(personnel)
        if str(employee.get("account") or "").strip() == clean_account
    ]
    return matches[0] if len(matches) == 1 else ""


def build_tool_groups() -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = [
        {
            "id": "common",
            "available": True,
            "tools": [
                {"id": "jira_audit"},
                {"id": "confluence_audit"},
                {"id": "daily_report"},
            ],
        }
    ]
    for group_id in ("STB", "TV", "SmartHome", "IPTV"):
        groups.append(
            {
                "id": group_id,
                "available": True,
                "tools": [{"id": "redmine"}] if group_id == "SmartHome" else [],
            }
        )
    groups.append(
        {
            "id": "Wi-Fi",
            "available": True,
            "tools": [],
        }
    )
    return groups


class ToolBridge(QObject):
    def __init__(self):
        super().__init__()

    def _groups(self) -> list[dict[str, Any]]:
        groups = build_tool_groups()
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
            row["tools"] = [self._localized_tool(tool) for tool in row["tools"]]
            localized.append(row)
        return localized

    def _localized_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        if tool.get("id") == "jira_audit":
            return {
                **tool,
                "title": self.tr("Jira Format Audit"),
                "description": self.tr("Review Jira issues against the FAE-QA format rules."),
            }
        if tool.get("id") == "confluence_audit":
            return {
                **tool,
                "title": self.tr("Project Weekly Audit"),
                "description": self.tr("Check every A-level project in development against the project page content standards."),
            }
        if tool.get("id") == "daily_report":
            return {
                **tool,
                "title": self.tr("Daily Report"),
                "description": self.tr(
                    "Generate, review, and send the fixed four-project status reports."
                ),
            }
        return {
            **tool,
            "title": self.tr("redmine"),
            "description": self.tr("Browse and sign in to SmartHome Redmine."),
        }

    groups = Property("QVariantList", _groups, constant=True)
