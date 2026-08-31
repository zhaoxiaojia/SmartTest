from __future__ import annotations

from datetime import datetime, timezone

import pytest
from openpyxl import load_workbook

from core.tools.common.jira_format_audit import (
    AuditReport,
    ResolvedAuditInput,
    active_rules,
    audit_issue,
    export_audit_xlsx,
)


def _issue(description: str) -> dict:
    return {
        "key": "SH-123",
        "fields": {
            "summary": "[ACME][T7][V1.1][Video]: Video freezes,1/2",
            "description": description,
            "creator": {"displayName": "Chao Li"},
            "reporter": {"displayName": "Different Reporter"},
            "components": [{"name": "Video"}],
        },
    }


def _table(header: str) -> str:
    return "\n".join(
        (
            header,
            "|平台信息|客户/项目代号|T6X高刷|",
            "|测试环境|测试仪器|-|",
            "|测试设置|HDMI输出|无|",
        )
    )


@pytest.mark.parametrize(
    "header",
    (
        "|模块|需要填写信息|测试信息|",
        "||模块||需要填写信息||测试信息||",
        "||||模块|||需要填写信息||||测试信息||||",
    ),
)
def test_table_template_ignores_header_pipe_counts(header):
    result = audit_issue(_issue(_table(header)), base_url="https://jira.example.com")

    assert result.passed


def test_non_target_table_header_uses_standard_description_rules():
    result = audit_issue(
        _issue(_table("||模块||填写说明||测试信息||")),
        base_url="https://jira.example.com",
    )

    assert {item.rule_id for item in result.violations} == {
        "DESCRIPTION.STEPS_TO_REPRODUCE",
        "DESCRIPTION.ACTUAL_RESULTS",
        "DESCRIPTION.EXPECTED_RESULTS",
        "DESCRIPTION.COMPARISON",
        "DESCRIPTION.NOTES",
        "DESCRIPTION.NOTES_HW",
        "DESCRIPTION.NOTES_SW",
    }


def test_export_summary_groups_by_creator_and_never_shows_reporter(tmp_path):
    result = audit_issue(_issue(""), base_url="https://jira.example.com")
    assert result.creator == "Chao Li"
    assert not hasattr(result, "reporter")
    generated_at = datetime(2026, 8, 21, tzinfo=timezone.utc)
    report = AuditReport(
        ResolvedAuditInput("jql", "project = SH", "project = SH"),
        generated_at,
        active_rules(),
        (result,),
    )

    path = export_audit_xlsx(report, downloads_dir=tmp_path, now=generated_at)
    rows = tuple(load_workbook(path)["汇总"].values)

    assert rows[8] == ("创建人", "违规 Jira 数量", "违规 Jira 号")
    assert rows[9] == ("Chao Li", 1, "SH-123")
    assert all("报告人" not in str(cell) for row in rows for cell in row if cell)
