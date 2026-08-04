from datetime import datetime
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

from tool.common.project_weekly_audit.models import (
    AuditBatch, AuditExecutionContext, AuditFinding, AuditPeriod, AuditStatus,
    ProjectAudit, ProjectCandidate, ProjectCollectionFilter,
)
from tool.common.project_weekly_audit.report import export_project_audit_xlsx


TZ = ZoneInfo("Asia/Shanghai")


def test_xlsx_reports_content_findings_without_update_matrix_columns(tmp_path):
    project = ProjectCandidate(
        "1", "M314", "Muffin314", "https://c/status", "https://c/root",
        2026, "A", "NORMAL", (2026,),
    )
    findings = [
        AuditFinding(
            "M314", "Test Plan", "plan.weekly", AuditStatus.FAILED,
            "Weekly plan is missing.", "Add weekly deliverables.",
            page_url="https://c/plan", explanation="No weekly section was found.",
        ),
        AuditFinding(
            "M314", "Project Status Report", "required.status",
            AuditStatus.PASSED, "Page is available.",
            page_url="https://c/status",
        ),
    ]
    batch = AuditBatch(
        "content1",
        AuditPeriod(
            datetime(2026, 7, 27, tzinfo=TZ),
            datetime(2026, 7, 31, tzinfo=TZ),
        ),
        datetime(2026, 7, 31, tzinfo=TZ),
        [ProjectAudit(project, findings)],
        ProjectCollectionFilter("DOPL + SDPL", (2026,), ("A",), ("NORMAL",)),
        AuditExecutionContext("manual"),
    )

    path = export_project_audit_xlsx(batch, tmp_path / "audit.xlsx")
    sheet = load_workbook(path).active
    values = [tuple(cell.value for cell in row) for row in sheet.iter_rows()]
    flattened = "\n".join(str(value) for row in values for value in row if value)

    assert "plan.weekly" in flattened
    assert "Weekly plan is missing." in flattened
    assert "updated" not in flattened.casefold()
    assert "invalid_format" not in flattened.casefold()
