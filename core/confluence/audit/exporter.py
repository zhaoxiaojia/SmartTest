from __future__ import annotations

from pathlib import Path
import re

from core.reporting.excel import write_xlsx_sections

from .models import AuditStatus
from .rules import UPDATE_MATRIX_POINTS


_STATUS = {
    AuditStatus.UPDATED: "已更新",
    AuditStatus.NOT_UPDATED: "未更新",
    AuditStatus.INVALID_FORMAT: "格式有误",
    AuditStatus.FAILED: "失败",
    AuditStatus.UNKNOWN: "未知",
}


def export_audit_xlsx_by_product_line(batch, output_dir: Path):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    keys = sorted({
        audit.project.product_space.key for audit in batch.projects
        if audit.project.product_space.key
    })
    for key in keys:
        safe = re.sub(r"[^\w.-]+", "_", key).strip("._") or "unknown"
        audits = tuple(
            audit for audit in batch.projects
            if audit.project.product_space.key == key
        )
        rows, hyperlinks = [], {}
        for audit in audits:
            by_rule = {finding.rule_id: finding for finding in audit.findings}
            rows.append((
                ", ".join(audit.owners),
                audit.project.identity.project_id,
                audit.project.name,
                audit.project.catalog_page.url,
                *(
                    _finding_text(by_rule[point.rule_id])
                    if point.rule_id in by_rule else "未知"
                    for point in UPDATE_MATRIX_POINTS
                ),
            ))
            if audit.project.catalog_page.url:
                hyperlinks[len(rows) - 1] = {4: audit.project.catalog_page.url}
        paths.append(write_xlsx_sections(
            directory / f"{safe}_{batch.id}.xlsx",
            sheet_name="Project Weekly Audit",
            sections=({
                "group": (
                    "Product Line", key, "审查周期",
                    f"{batch.period.start.date()} - {batch.period.end.date()}",
                ),
                "headers": (
                    "Owner", "Project ID", "Project", "Project URL",
                    *(point.label for point in UPDATE_MATRIX_POINTS),
                ),
                "rows": rows, "hyperlinks": hyperlinks,
            },),
            wrap_data=False,
        ))
    return paths


def _finding_text(finding):
    if finding.status is AuditStatus.INVALID_FORMAT:
        return finding.reason if finding.reason.startswith("格式有误：") else f"格式有误：{finding.reason}"
    return _STATUS[finding.status]
