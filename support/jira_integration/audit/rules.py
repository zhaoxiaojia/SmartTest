from __future__ import annotations

from .models import AuditRule


ALLOWED_MODULES = (
    "System",
    "Online",
    "Video",
    "Ethernet",
    "Wifi",
    "BT",
    "APK",
    "HDMI",
    "Audio",
    "DLNA",
    "Miracast",
    "PQ",
    "KPI",
    "USB",
    "Stability",
    "Multivideo",
    "Tr069",
    "CTS / VTS / GTS / TVTS / STS / GGI / CTS-verify",
    "MS12",
    "DV",
    "NTS",
    "Primevideo",
)

DESCRIPTION_SECTIONS = (
    "Steps to reproduce",
    "Actual results",
    "Expected results",
    "Reproducibility rate",
    "Comparision",
    "Notes",
)

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


_RULES = (
    AuditRule(
        "SUMMARY.FORMAT",
        "Summary",
        "summary",
        "Summary 必须包含 4–6 个方括号分组，最后四组依次为客户、CHIP、系统版本和模块，随后填写英文问题描述与复现概率。",
        "使用“[客户][CHIP][版本][模块]: 英文问题描述,复现概率”；前面可选增加公共 Jira ID 和客户 Bug ID。",
    ),
    AuditRule(
        "SUMMARY.CUSTOMER",
        "Summary",
        "summary.customer",
        "Summary 必须填写客户英文名。",
        "填写客户英文名或英文项目代号。",
    ),
    AuditRule(
        "SUMMARY.CHIP",
        "Summary",
        "summary.chip",
        "Summary 必须填写 CHIP。",
        "填写大写 CHIP 名称。",
    ),
    AuditRule(
        "SUMMARY.VERSION",
        "Summary",
        "summary.version",
        "Summary 必须填写系统版本。",
        "填写明确的系统版本。",
    ),
    AuditRule(
        "SUMMARY.CUSTOMER_ENGLISH",
        "Summary",
        "summary.customer",
        "客户名称必须使用英文名或英文项目代号。",
        "将客户名称改为英文名或英文项目代号。",
    ),
    AuditRule(
        "SUMMARY.CHIP_UPPERCASE",
        "Summary",
        "summary.chip",
        "CHIP 必须包含字母并使用大写。",
        "将 CHIP 名称中的字母改为大写。",
    ),
    AuditRule(
        "SUMMARY.MODULE",
        "Summary",
        "summary.module",
        "Summary 的模块必须来自规范允许的模块列表。",
        "选择规则明细中列出的模块名称。",
    ),
    AuditRule(
        "SUMMARY.DESCRIPTION_ENGLISH",
        "Summary",
        "summary.description",
        "Summary 的问题描述必须使用英文。",
        "使用英文描述问题现象。",
    ),
    AuditRule(
        "SUMMARY.PROBABILITY",
        "Summary",
        "summary.probability",
        "Summary 的复现概率必须是百分比或分数。",
        "使用 50% 或 1/2 等格式。",
    ),
    AuditRule(
        "COMPONENT.REQUIRED",
        "Component",
        "components",
        "至少填写一个 Component。",
        "选择一个或多个与问题相关的 Component。",
    ),
    AuditRule(
        "COMPONENT.ALLOWED",
        "Component",
        "components",
        "每个 Component 都必须来自规范允许的模块列表。",
        "移除不支持的 Component，改用规则明细中的模块名称。",
    ),
    AuditRule(
        "DESCRIPTION.STEPS_TO_REPRODUCE",
        "Description",
        "description.steps_to_reproduce",
        "Description 必须包含非空的 Steps to reproduce。",
        "补充可执行的复现步骤。",
    ),
    AuditRule(
        "DESCRIPTION.ACTUAL_RESULTS",
        "Description",
        "description.actual_results",
        "Description 必须包含非空的 Actual results。",
        "补充实际发生的结果。",
    ),
    AuditRule(
        "DESCRIPTION.EXPECTED_RESULTS",
        "Description",
        "description.expected_results",
        "Description 必须包含非空的 Expected results。",
        "补充预期结果。",
    ),
    AuditRule(
        "DESCRIPTION.REPRODUCIBILITY_RATE",
        "Description",
        "description.reproducibility_rate",
        "Description 必须包含非空的 Reproducibility rate。",
        "补充百分比或分数形式的复现概率。",
    ),
    AuditRule(
        "DESCRIPTION.COMPARISION",
        "Description",
        "description.comparision",
        "Description 必须包含非空的 Comparision。",
        "补充版本或平台对比信息。",
    ),
    AuditRule(
        "DESCRIPTION.NOTES",
        "Description",
        "description.notes",
        "Description 必须包含非空的 Notes。",
        "补充包含软硬件信息的备注。",
    ),
    AuditRule(
        "DESCRIPTION.STEPS_ORDERED",
        "Description",
        "description.steps_to_reproduce",
        "复现步骤必须从 1 开始连续编号，且每一步包含可执行动作。",
        "按顺序重写为完整的编号步骤。",
    ),
    AuditRule(
        "DESCRIPTION.RATE_FORMAT",
        "Description",
        "description.reproducibility_rate",
        "Description 中的复现概率必须是百分比或分数。",
        "使用 50% 或 1/2 等格式。",
    ),
    AuditRule(
        "DESCRIPTION.NOTES_HW",
        "Description",
        "description.notes",
        "Notes 必须包含已填写的“HW info: ...”。",
        "在 Notes 中补充 HW info。",
    ),
    AuditRule(
        "DESCRIPTION.NOTES_SW",
        "Description",
        "description.notes",
        "Notes 必须包含已填写的“SW info: ...”。",
        "在 Notes 中补充 SW info。",
    ),
    AuditRule(
        "REGRESSION.EVIDENCE",
        "Regression",
        "description.comparision",
        "Regression 问题必须同时说明旧版本正常和当前版本异常。",
        "在 Comparision 中补充旧版本正常与当前版本异常的对照证据。",
    ),
    AuditRule(
        "ATTACHMENT.MAX_SIZE",
        "Attachment",
        "attachment",
        "单个附件不得超过 10 MiB。",
        "压缩、拆分附件或改用链接。",
    ),
)


def active_rules() -> tuple[AuditRule, ...]:
    return _RULES
