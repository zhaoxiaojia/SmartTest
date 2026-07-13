from __future__ import annotations

import importlib
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QObject, Signal

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ui"))
jira_bridge_module = importlib.import_module("example.bridge.JiraBridge")


class _Auth(QObject):
    authChanged = Signal()

    def __init__(self, username: str):
        super().__init__()
        self.username = username

    def currentUsername(self) -> str:
        return self.username


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    instance = jira_bridge_module.JiraBridge(_Auth("chao.li"))
    instance._issues = [
        {"keyId": "TV-1", "summary": "browse one", "labels": []},
        {"keyId": "TV-2", "summary": "browse two", "labels": []},
    ]
    return instance


@pytest.mark.parametrize("username", ["chao.li", r"DOMAIN\chao.li", "chao.li@amlogic.com"])
def test_manager_name_variants_are_allowed(bridge, username):
    bridge._auth_bridge.username = username
    assert bridge.isAuditManager()


def test_non_manager_is_denied_at_audit_and_export_boundaries(bridge):
    bridge._auth_bridge.username = "other.user"
    assert bridge.runFormatAudit() is False
    assert bridge.exportFormatAudit() == ""
    assert "Only Jira managers" in bridge.auditStatusText()


def test_audit_uses_actual_spec_current_issues_and_exports_two_sheets(bridge, monkeypatch, tmp_path):
    spec = tmp_path / "jira规范.md"
    spec.write_text("# Summary\nSummary must be formatted.\n", encoding="utf-8")
    monkeypatch.setattr(bridge, "_audit_spec_path", lambda: spec)
    description = """Problem Description:
bad
Steps to reproduce:
1. do it
Reproducibility rate:
1/2
Comparision:
old build normal, current build failing
Notes:
HW info: board
SW info: build
"""
    detail_rows = {
        "TV-1": {"keyId": "TV-1", "summary": "bad", "components": ["Video"], "description": description, "labels": [], "attachments": []},
        "TV-2": {"keyId": "TV-2", "summary": "also bad", "components": [], "description": description, "labels": [], "attachments": []},
    }
    seen = {"detail_keys": []}

    class DetailService:
        def fetch_issue_detail(self, *, issue_key, **_kwargs):
            seen["detail_keys"].append(issue_key)
            return {"issue": detail_rows[issue_key]}

    monkeypatch.setattr(bridge, "_ensure_workspace_service", lambda: DetailService())
    original_load = jira_bridge_module.jira_handler.load_markdown_rules
    original_validate = jira_bridge_module.jira_handler.validate_issues

    def capture(path):
        seen["path"] = path
        return original_load(path)

    monkeypatch.setattr(jira_bridge_module.jira_handler, "load_markdown_rules", capture)

    def validate(issues, **kwargs):
        seen["validated"] = list(issues)
        return original_validate(seen["validated"], **kwargs)

    monkeypatch.setattr(jira_bridge_module.jira_handler, "validate_issues", validate)
    assert bridge.runFormatAudit()
    assert seen["path"] == spec
    assert seen["detail_keys"] == ["TV-1", "TV-2"]
    assert seen["validated"] == [detail_rows["TV-1"], detail_rows["TV-2"]]
    assert len(bridge.auditDetailRows()) > 1
    assert {row["issueKey"] for row in bridge.auditDetailRows()} == {"TV-1", "TV-2"}
    output = bridge.exportFormatAudit()
    assert output
    with ZipFile(output) as archive:
        workbook = archive.read("xl/workbook.xml").decode()
    assert 'name="Summary"' in workbook
    assert 'name="Details"' in workbook


def test_missing_spec_is_actionable(bridge, monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "_audit_spec_path", lambda: tmp_path / "missing.md")
    assert bridge.runFormatAudit() is False
    assert "jira规范.md" in bridge.auditStatusText()
    assert "SmartTest application root" in bridge.auditStatusText()
