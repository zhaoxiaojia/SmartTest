from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .models import AuditReport


def export_audit_xlsx(
    report: AuditReport, *, downloads_dir: Path | None = None, now: datetime | None = None
) -> Path:
    directory = Path(downloads_dir) if downloads_dir else Path.home() / "Downloads"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    target = _unique_path(directory, f"jira_format_audit_{timestamp}.xlsx")
    rule_by_id = {rule.rule_id: rule for rule in report.rules}

    sheets = (
        (
            "Summary",
            ("Metric", "Value"),
            (
                ("Generated at", report.generated_at.isoformat(sep=" ", timespec="seconds")),
                ("Source", report.resolved.source_kind),
                ("Original input", report.resolved.original),
                ("JQL", report.resolved.jql),
                ("Total issues", report.total_count),
                ("Passed issues", report.passed_count),
                ("Failed issues", report.failed_count),
                ("Violations", report.violation_count),
            ),
            0,
        ),
        (
            "Rules",
            ("Rule ID", "Section", "Field", "Requirement", "Guidance"),
            (
                (
                    rule.rule_id,
                    rule.section,
                    rule.field,
                    rule.requirement,
                    rule.guidance,
                )
                for rule in report.rules
            ),
            0,
        ),
        (
            "Issues",
            ("Key", "URL", "Summary", "Reporter", "Status", "Violation count"),
            (
                (issue.key, issue.url, issue.summary, issue.reporter,
                 "PASS" if issue.passed else "FAIL", len(issue.violations))
                for issue in report.issues
            ),
            2,
        ),
        (
            "Violations",
            ("Key", "URL", "Rule ID", "Section", "Field", "Observed",
             "Requirement", "Reason", "Guidance"),
            (
                (
                    issue.key, issue.url, violation.rule_id, violation.section,
                    violation.field, violation.observed,
                    rule_by_id[violation.rule_id].requirement,
                    violation.reason, violation.guidance,
                )
                for issue in report.issues
                for violation in issue.violations
            ),
            2,
        ),
    )

    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, header, rows, hyperlink_column in sheets:
        _add_sheet(workbook, name, header, rows, hyperlink_column)

    handle, temporary_name = tempfile.mkstemp(
        prefix=".jira_format_audit_",
        suffix=".tmp",
        dir=directory,
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        workbook.save(temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target.resolve()


def _add_sheet(workbook, name, header, rows, hyperlink_column):
    sheet = workbook.create_sheet(name)
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4472C4")
    if hyperlink_column:
        for row in range(2, sheet.max_row + 1):
            cell = sheet.cell(row, hyperlink_column)
            cell.hyperlink = str(cell.value)
            cell.style = "Hyperlink"
    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max(width + 2, 12), 48)
        for cell in column:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    stem, suffix = candidate.stem, candidate.suffix
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate
