from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from support.report.excel import write_xlsx_sections


PROJECT_AUDIT_HEADERS = (
    "年份", "项目名", "页面", "规则", "状态", "原因", "调整建议", "页面链接",
)


def export_project_audit_xlsx(batch, output_path: Path) -> Path:
    period = (
        f"{batch.period.start.date().isoformat()} - "
        f"{(batch.period.end - timedelta(microseconds=1)).date().isoformat()}"
    )
    grouped = {}
    for audit in batch.projects:
        project = audit.project
        grouped.setdefault(
            (project.support_mode, project.project_status), [],
        ).append(audit)
    sections = []
    for (support_mode, project_status), audits in sorted(
        grouped.items(), key=lambda item: (
            item[0][0].casefold(), item[0][1].casefold(),
        ),
    ):
        rows, hyperlinks = [], {}
        for audit in sorted(audits, key=lambda row: (
            row.project.matching_years or (row.project.year,),
            row.project.name.casefold(),
            row.project.project_id.casefold(),
        )):
            project = audit.project
            for finding in audit.findings:
                rows.append((
                    ", ".join(map(str, project.matching_years or (project.year,))),
                    project.name,
                    finding.page_title,
                    finding.rule_id,
                    finding.status.value,
                    finding.reason,
                    finding.guidance,
                    finding.page_url,
                ))
                if finding.page_url:
                    hyperlinks[len(rows) - 1] = {8: finding.page_url}
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
    )
