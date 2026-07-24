from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zipfile import ZipFile


def _report():
    from support.jira_integration.audit import (
        AuditReport,
        AuditViolation,
        IssueAuditResult,
        ResolvedAuditInput,
        active_rules,
    )

    violation = AuditViolation(
        rule_id="SUMMARY-001",
        section="Summary",
        field="summary",
        observed="bad summary",
        reason="Summary 结构不符合规范。",
        guidance="按规则修改。",
    )
    issue = IssueAuditResult(
        key="SH-1",
        url="https://jira.example.com/browse/SH-1",
        summary="bad summary",
        reporter="Coco",
        passed=False,
        violations=(violation,),
    )
    return AuditReport(
        resolved=ResolvedAuditInput("jql", "project = SH", "project = SH"),
        generated_at=datetime(2026, 7, 24, 10, 11, 12),
        rules=active_rules(),
        issues=(issue,),
    )


def _workbook_text(path: Path) -> str:
    with ZipFile(path) as archive:
        return "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".xml")
        )


def test_export_creates_unique_xlsx_with_four_sheets_and_hyperlink(tmp_path):
    from support.jira_integration.audit.exporter import export_audit_xlsx

    now = datetime(2026, 7, 24, 10, 11, 12)
    first = export_audit_xlsx(_report(), downloads_dir=tmp_path, now=now)
    second = export_audit_xlsx(_report(), downloads_dir=tmp_path, now=now)

    assert first.name == "jira_format_audit_20260724_101112.xlsx"
    assert second.name == "jira_format_audit_20260724_101112_2.xlsx"
    assert first.exists() and second.exists()
    assert not list(tmp_path.glob("*.tmp"))

    with ZipFile(first) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        assert all(f'name="{name}"' in workbook for name in ("Summary", "Rules", "Issues", "Violations"))
        assert archive.testzip() is None

    text = _workbook_text(first)
    for expected in (
        "project = SH",
        "SUMMARY-001",
        "SH-1",
        "bad summary",
        "Summary 结构不符合规范。",
        "https://jira.example.com/browse/SH-1",
        "HYPERLINK",
    ):
        assert expected in text
