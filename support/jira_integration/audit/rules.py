from __future__ import annotations

from .models import AuditRule


_RULES = (
    AuditRule(
        "SUMMARY-001",
        "Summary",
        "summary",
        "Summary 使用 [Customer][CHIP][Module] English issue description 结构。",
        "补齐三个方括号字段，并在其后使用英文描述问题。",
    ),
    AuditRule(
        "SUMMARY-002",
        "Summary",
        "summary",
        "客户名称和问题描述使用英文字符。",
        "将 Summary 中的客户名称和问题描述改为英文。",
    ),
    AuditRule(
        "SUMMARY-003",
        "Summary",
        "summary",
        "CHIP 名称必须使用大写。",
        "将 Summary 第二个方括号中的 CHIP 名称改为大写。",
    ),
    AuditRule(
        "COMPONENT-001",
        "Classification",
        "components",
        "至少选择一个 Component，且包含 Summary 中声明的 Module。",
        "选择与 Summary 第三个方括号一致的 Jira Component。",
    ),
    AuditRule(
        "PROBABILITY-001",
        "Description",
        "description",
        "Reproducibility rate 使用百分比或“出现次数/执行次数”格式。",
        "例如填写 80% 或 4/5。",
    ),
    AuditRule(
        "DESCRIPTION-001",
        "Description",
        "description",
        "Description 必须包含规范要求的全部章节。",
        "补齐 Steps、Actual、Expected、Reproducibility、Comparision、Notes、HW info 和 SW info。",
    ),
    AuditRule(
        "REGRESSION-001",
        "Regression",
        "description",
        "Regression 问题必须提供好坏版本证据。",
        "在 SW info 或 Notes 中明确填写 good/bad 两个版本。",
    ),
    AuditRule(
        "ATTACHMENT-001",
        "Attachments",
        "attachment",
        "单个附件不得超过 10 MiB。",
        "压缩或拆分超过 10 MiB 的附件。",
    ),
    AuditRule(
        "LABEL-001",
        "Labels",
        "labels",
        "regression Label 要求填写有效的 Comparision 对比结果。",
        "在 Comparision 章节填写对比版本和结果。",
    ),
)


def active_rules() -> tuple[AuditRule, ...]:
    return _RULES
