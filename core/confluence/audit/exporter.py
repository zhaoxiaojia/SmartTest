from __future__ import annotations

from pathlib import Path
import re

from core.reporting.excel import write_xlsx_sections
from core.confluence.project_discovery import _commercial_year

from .models import AuditStatus
from .rules import UPDATE_MATRIX_POINTS


_STATUS = {
    AuditStatus.UPDATED: "已更新",
    AuditStatus.NOT_UPDATED: "未更新",
    AuditStatus.INVALID_FORMAT: "格式有误",
    AuditStatus.FAILED: "失败",
    AuditStatus.UNKNOWN: "未知",
}

_HEADERS = (
    "Owner", "年份", "项目名", "项目链接",
    *(point.label for point in UPDATE_MATRIX_POINTS), "PS",
)


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
        grouped = {}
        for audit in audits:
            grouped.setdefault((
                audit.project.support_mode.name if audit.project.support_mode else "",
                audit.project.status.name if audit.project.status else "",
            ), []).append(audit)
        sections = []
        for (support_mode, project_status), group_audits in sorted(
            grouped.items(), key=lambda item: (
                item[0][0].casefold(), item[0][1].casefold(),
            ),
        ):
            rows, hyperlinks = [], {}
            for audit in sorted(group_audits, key=lambda row: (
                _project_year(row.project), row.project.name.casefold(),
                row.project.identity.project_id.casefold(),
            )):
                by_rule = {finding.rule_id: finding for finding in audit.findings}
                rows.append((
                    ", ".join(audit.owners),
                    str(_project_year(audit.project) or ""),
                    audit.project.name,
                    audit.project.catalog_page.url,
                    *(
                        _finding_text(by_rule[point.rule_id])
                        if point.rule_id in by_rule else "未知"
                        for point in UPDATE_MATRIX_POINTS
                    ),
                    "",
                ))
                if audit.project.catalog_page.url:
                    hyperlinks[len(rows) - 1] = {4: audit.project.catalog_page.url}
            sections.append({
                "group": (
                    "Support Mode", support_mode, "Project Status", project_status,
                    "审查周期", f"{batch.period.start.date()} - {batch.period.end.date()}",
                ),
                "headers": _HEADERS,
                "rows": rows,
                "hyperlinks": hyperlinks,
            })
        paths.append(write_xlsx_sections(
            directory / f"{safe}_{batch.id}.xlsx",
            sheet_name="Project Weekly Audit",
            sections=sections,
            wrap_data=False,
        ))
    return paths


def _finding_text(finding):
    if finding.status is AuditStatus.INVALID_FORMAT:
        return finding.reason if finding.reason.startswith("格式有误：") else f"格式有误：{finding.reason}"
    return _STATUS[finding.status]


def _project_year(project):
    fields = dict(project.facts.value.values) if project.facts.value else {}
    return _commercial_year(fields.get("date of commercial approval", "")) or 0
