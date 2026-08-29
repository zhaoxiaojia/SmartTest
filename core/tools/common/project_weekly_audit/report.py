from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

from core.reporting.excel import write_xlsx_sections

from .models import AuditStatus
from .rules import UPDATE_MATRIX_POINTS


PROJECT_AUDIT_HEADERS = (
    "Owner",
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
                hyperlinks[len(rows) - 1] = {4: audit.project.home_url}
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
    if not sections and batch.product_lines:
        sections.append({
            "group": ("Product Line", batch.product_lines[0].display_name),
            "headers": PROJECT_AUDIT_HEADERS,
            "rows": [],
            "hyperlinks": {},
        })
    return write_xlsx_sections(
        output_path,
        sheet_name="Project Weekly Audit",
        sections=sections,
        wrap_data=False,
    )


def export_project_audit_xlsx_by_product_line(batch, output_dir: Path):
    output_dir = Path(output_dir)
    paths = []
    for line in batch.product_lines:
        line_batch = replace(
            batch,
            projects=[
                audit for audit in batch.projects
                if audit.project.space_key == line.key
            ],
            product_lines=(line,),
        )
        safe_name = re.sub(
            r"[^\w.-]+", "_", line.display_name, flags=re.UNICODE,
        ).strip("._") or line.key
        paths.append(export_project_audit_xlsx(
            line_batch,
            output_dir / f"{safe_name}_{batch.id}.xlsx",
        ))
    return paths


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
        audit.owner,
        ", ".join(map(str, project.matching_years or (project.year,))),
        project.name,
        project.home_url,
        *states,
        "",
    )
