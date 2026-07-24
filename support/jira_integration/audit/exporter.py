from __future__ import annotations

import ctypes
import os
import tempfile
from ctypes import wintypes
from datetime import datetime
from html import escape
from pathlib import Path
from string import ascii_uppercase
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from .models import AuditReport


def export_audit_xlsx(
    report: AuditReport,
    *,
    downloads_dir: Path | None = None,
    now: datetime | None = None,
) -> Path:
    target_dir = Path(downloads_dir) if downloads_dir is not None else _windows_downloads_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    target = _unique_path(target_dir, f"jira_format_audit_{timestamp}", ".xlsx")
    fd, temporary_name = tempfile.mkstemp(prefix=".jira_format_audit_", suffix=".tmp", dir=target_dir)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        _write_workbook(temporary, report)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target.resolve()


def _write_workbook(path: Path, report: AuditReport) -> None:
    summary = [
        ["Metric", "Value"],
        ["Generated at", report.generated_at.isoformat(sep=" ", timespec="seconds")],
        ["Source", report.resolved.source_kind],
        ["Original input", report.resolved.original],
        ["JQL", report.resolved.jql],
        ["Total issues", report.total_count],
        ["Passed issues", report.passed_count],
        ["Failed issues", report.failed_count],
        ["Violations", report.violation_count],
    ]
    rules = [["Rule ID", "Section", "Field", "Requirement", "Guidance"]]
    rules.extend(
        [rule.rule_id, rule.section, rule.field, rule.requirement, rule.guidance]
        for rule in report.rules
    )
    issues = [["Key", "URL", "Summary", "Reporter", "Status", "Violation count"]]
    issues.extend(
        [
            issue.key,
            _Hyperlink(issue.url),
            issue.summary,
            issue.reporter,
            "PASS" if issue.passed else "FAIL",
            len(issue.violations),
        ]
        for issue in report.issues
    )
    violations = [
        [
            "Key",
            "URL",
            "Rule ID",
            "Section",
            "Field",
            "Observed",
            "Requirement",
            "Reason",
            "Guidance",
        ]
    ]
    rule_by_id = {rule.rule_id: rule for rule in report.rules}
    for issue in report.issues:
        for violation in issue.violations:
            violations.append(
                [
                    issue.key,
                    _Hyperlink(issue.url),
                    violation.rule_id,
                    violation.section,
                    violation.field,
                    violation.observed,
                    rule_by_id.get(violation.rule_id).requirement
                    if violation.rule_id in rule_by_id
                    else "",
                    violation.reason,
                    violation.guidance,
                ]
            )

    sheets = [
        ("Summary", summary),
        ("Rules", rules),
        ("Issues", issues),
        ("Violations", violations),
    ]
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(len(sheets)))
        archive.writestr("_rels/.rels", _package_relationships())
        archive.writestr("xl/workbook.xml", _workbook_xml(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships(len(sheets)))
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, (_name, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))


class _Hyperlink(str):
    pass


def _sheet_xml(rows) -> str:
    rendered_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            reference = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, _Hyperlink):
                safe_url = str(value).replace('"', '""')
                formula = escape(f'HYPERLINK("{safe_url}","{safe_url}")')
                cells.append(f'<c r="{reference}"><f>{formula}</f><v></v></c>')
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">'
                    f"{escape(str(value or ''))}</t></is></c>"
                )
        rendered_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rendered_rows)}</sheetData></worksheet>'
    )


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, len(ascii_uppercase))
        result = ascii_uppercase[remainder] + result
    return result


def _content_types(sheet_count: int) -> str:
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{sheet_overrides}</Types>"
    )


def _package_relationships() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )


def _workbook_xml(sheets) -> str:
    rows = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _rows) in enumerate(sheets, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{rows}</sheets></workbook>"
    )


def _workbook_relationships(sheet_count: int) -> str:
    relationships = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    relationships += (
        f'<Relationship Id="rId{sheet_count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationships}</Relationships>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
        '<cellXfs count="1"><xf xfId="0"/></cellXfs>'
        '</styleSheet>'
    )


def _unique_path(directory: Path, stem: str, suffix: str) -> Path:
    candidate = directory / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def _windows_downloads_dir() -> Path:
    if os.name != "nt":
        return Path.home() / "Downloads"

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

        @classmethod
        def from_uuid(cls, value: UUID):
            raw = value.bytes_le
            return cls(
                int.from_bytes(raw[0:4], "little"),
                int.from_bytes(raw[4:6], "little"),
                int.from_bytes(raw[6:8], "little"),
                (ctypes.c_ubyte * 8)(*raw[8:]),
            )

    folder_id = GUID.from_uuid(UUID("374DE290-123F-4565-9164-39C4925E467B"))
    result_path = ctypes.c_wchar_p()
    status = ctypes.windll.shell32.SHGetKnownFolderPath(  # type: ignore[attr-defined]
        ctypes.byref(folder_id), 0, None, ctypes.byref(result_path)
    )
    if status != 0 or not result_path.value:
        raise OSError(f"无法获取 Windows Downloads Known Folder：{status}")
    try:
        return Path(result_path.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(result_path)  # type: ignore[attr-defined]
