from __future__ import annotations

from pathlib import Path

from support.report.excel import write_xlsx_sections

from .models import AuditStatus, UPDATE_MATRIX_POINTS


PROJECT_AUDIT_HEADERS = (
    "年份",
    "项目名",
    "项目链接",
    *(point.label for point in UPDATE_MATRIX_POINTS),
    "PS",
)
STATUS_TEXT = {
    AuditStatus.UPDATED: "已更新",
    AuditStatus.NOT_UPDATED: "未更新",
    AuditStatus.INVALID_FORMAT: "格式有误",
}


def export_project_audit_xlsx(batch, output_path: Path) -> Path:
    period = (
        f"{batch.period.start.date().isoformat()} - "
        f"{batch.period.end.date().isoformat()}"
    )
    grouped = {}
    for audit in batch.projects:
        project = audit.project
        grouped.setdefault(
            (project.support_mode, project.project_status), [],
        ).append(audit)
    sections = []
    for (support_mode, project_status), audits in sorted(
        grouped.items(),
        key=lambda item: (item[0][0].casefold(), item[0][1].casefold()),
    ):
        rows, hyperlinks = [], {}
        for audit in sorted(
            audits,
            key=lambda row: (
                row.project.matching_years or (row.project.year,),
                row.project.name.casefold(),
                row.project.project_id.casefold(),
            ),
        ):
            rows.append(_project_row(audit))
            if audit.project.home_url:
                hyperlinks[len(rows) - 1] = {3: audit.project.home_url}
        sections.append({
            "group": (
                "Support Mode", support_mode,
                "Project Status", project_status,
                "审查周期", period,
            ),
            "headers": PROJECT_AUDIT_HEADERS,
            "rows": rows,
            "hyperlinks": hyperlinks,
        })
    return write_xlsx_sections(
        output_path,
        sheet_name="Project Weekly Audit",
        sections=sections,
        wrap_data=False,
    )


def _project_row(audit):
    by_rule = {finding.rule_id: finding for finding in audit.findings}
    states = []
    for point in UPDATE_MATRIX_POINTS:
        finding = by_rule[point.rule_id]
        if finding.status is AuditStatus.INVALID_FORMAT:
            detail = finding.explanation or finding.reason
            states.append(
                detail if detail.startswith("格式有误：")
                else f"格式有误：{detail}"
            )
        else:
            states.append(STATUS_TEXT[finding.status])
    project = audit.project
    return (
        ", ".join(map(str, project.matching_years or (project.year,))),
        project.name,
        project.home_url,
        *states,
        "",
    )
