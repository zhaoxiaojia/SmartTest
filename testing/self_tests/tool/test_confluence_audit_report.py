from datetime import datetime
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

from tool.common.project_weekly_audit.models import (
    AuditBatch,
    AuditExecutionContext,
    AuditFinding,
    AuditPeriod,
    AuditStatus,
    ProjectAudit,
    ProjectCandidate,
    ProjectCollectionFilter,
    UPDATE_MATRIX_POINTS,
)
from tool.common.project_weekly_audit.report import export_project_audit_xlsx


TZ = ZoneInfo("Asia/Shanghai")


def test_xlsx_writes_invalid_reason_in_its_cell_without_repeating_ps(tmp_path):
    project = ProjectCandidate(
        "1", "M314", "Muffin314", "https://c/status", "https://c/root",
        2025, "A", "NORMAL", (2025, 2026),
    )
    findings = []
    for index, point in enumerate(UPDATE_MATRIX_POINTS):
        invalid = index in {2, 3, 4}
        missing_region = index == 4
        findings.append(AuditFinding(
            project.project_id,
            point.label.split(".", 1)[0],
            point.rule_id,
            AuditStatus.INVALID_FORMAT if invalid else (
                AuditStatus.UPDATED if index % 2 else AuditStatus.NOT_UPDATED
            ),
            "格式有误" if missing_region else (
                "PermissionError" if invalid else "timestamp"
            ),
            page_url="https://c/page",
            explanation=(
                "格式有误：查询不到Task Arrangement of Important Test（Must give ETA）"
                if missing_region else (
                    "pageId=42; HTTP 403" if invalid else ""
                )
            ),
        ))
    batch = AuditBatch(
        "matrix1",
        AuditPeriod(
            datetime(2026, 7, 27, tzinfo=TZ),
            datetime(2026, 7, 31, tzinfo=TZ),
        ),
        datetime(2026, 7, 31, tzinfo=TZ),
        [ProjectAudit(project, findings)],
        ProjectCollectionFilter("DOPL + SDPL", (2025, 2026)),
        AuditExecutionContext("manual"),
    )

    sheet = load_workbook(
        export_project_audit_xlsx(batch, tmp_path / "audit.xlsx"),
    ).active

    assert sheet.title == "Project Weekly Audit"
    assert [cell.value for cell in sheet[1]][:6] == [
        "Support Mode", "A", "Project Status", "NORMAL",
        "审查周期", "2026-07-27 - 2026-07-31",
    ]
    assert [cell.value for cell in sheet[2]] == [
        "年份", "项目名", "项目链接",
        *(point.label for point in UPDATE_MATRIX_POINTS), "PS",
    ]
    assert [point.label for point in UPDATE_MATRIX_POINTS] == [
        "Project Status Report.Highlights",
        "Project Status Report.Impact issues",
        "Basic Information.Test Information.Phase Status（当前阶段测试状态）",
        "Basic Information.Test Information.项目整体状态Summary",
        "Basic Information.Test Information.Task Arrangement of Important Test（Must give ETA）",
        "Basic Information.Test Information.Blocking QA Testing Items",
        "Basic Information.Test Information.Test Plan.Category",
        "Basic Information.Test Information.Test Environment Setup and Precautions.测试环境搭建以及注意事项",
        "Basic Information.Test Information.Summary of Experience and Typical Cases",
        "Basic Information.Test Information.Test Report Store",
    ]
    assert sheet.max_row == 3
    assert sheet["A3"].value == "2025, 2026"
    assert sheet["B3"].value == "Muffin314"
    assert sheet["C3"].value == "https://c/root"
    assert sheet["C3"].hyperlink.target == "https://c/root"
    assert sheet["F3"].value == "格式有误：pageId=42; HTTP 403"
    assert sheet["G3"].value == "格式有误：pageId=42; HTTP 403"
    assert sheet["H3"].value == "格式有误：查询不到Task Arrangement of Important Test（Must give ETA）"
    assert sheet["N3"].value is None
    assert sheet.freeze_panes == "A3"
    assert sheet["A1"].fill.fgColor.rgb == "FFD9EAF7"
    assert sheet["A2"].fill.fgColor.rgb == "FF1F4E78"
    assert sheet["A2"].font.bold is True
    assert sheet["A2"].font.color.rgb == "FFFFFFFF"
    assert sheet["D3"].fill.fgColor.rgb == "FFFFEB9C"
    assert sheet["E3"].fill.fgColor.rgb == "FFC6EFCE"
    assert sheet["F3"].fill.fgColor.rgb == "FFFFC7CE"
    assert sheet["G3"].fill.fgColor.rgb == "FFFFC7CE"
    assert sheet["H3"].fill.fgColor.rgb == "FFFFC7CE"
    assert sheet["A2"].alignment.wrap_text is True
    assert sheet["D3"].alignment.wrap_text is not True
    assert sheet["F3"].alignment.wrap_text is not True
