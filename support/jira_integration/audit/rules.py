from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from .models import (
    AuditAttachment,
    AuditIssue,
    AuditRule,
    AuditViolation,
    IssueAuditResult,
)


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


_SUMMARY_PATTERN = re.compile(
    r"((?:\[[^\]\r\n]+\]){4,6}):\s*(.+),\s*([^,]+)\.?"
)

_DESCRIPTION_RULE_IDS = {
    "steps to reproduce": "DESCRIPTION.STEPS_TO_REPRODUCE",
    "actual results": "DESCRIPTION.ACTUAL_RESULTS",
    "expected results": "DESCRIPTION.EXPECTED_RESULTS",
    "reproducibility rate": "DESCRIPTION.REPRODUCIBILITY_RATE",
    "comparision": "DESCRIPTION.COMPARISION",
    "notes": "DESCRIPTION.NOTES",
}


def normalize_issue(issue: dict[str, Any], base_url: str) -> AuditIssue:
    fields = issue.get("fields") if isinstance(issue, dict) else {}
    fields = fields if isinstance(fields, dict) else {}
    key = str(issue.get("key", "") or "").strip()
    reporter = fields.get("reporter") or {}
    if not isinstance(reporter, dict):
        reporter = {}
    components = tuple(
        str(item.get("name", "") or "").strip()
        if isinstance(item, dict)
        else str(item or "").strip()
        for item in fields.get("components") or []
        if (
            str(item.get("name", "") or "").strip()
            if isinstance(item, dict)
            else str(item or "").strip()
        )
    )
    labels = tuple(
        str(item or "").strip()
        for item in fields.get("labels") or []
        if str(item or "").strip()
    )
    attachments = tuple(
        AuditAttachment(
            filename=str(item.get("filename", "") or ""),
            size=_safe_int(item.get("size")),
        )
        for item in (fields.get("attachment") or fields.get("attachments") or [])
        if isinstance(item, dict)
    )
    return AuditIssue(
        key=key,
        url=f"{str(base_url or '').rstrip('/')}/browse/{key}",
        summary=str(fields.get("summary", "") or ""),
        description=_plain_text(fields.get("description")),
        reporter=str(
            reporter.get("displayName")
            or reporter.get("name")
            or reporter.get("emailAddress")
            or ""
        ),
        components=components,
        labels=labels,
        attachments=attachments,
    )


def audit_issue(
    issue: dict[str, Any],
    *,
    base_url: str,
    rules: Sequence[AuditRule] | None = None,
) -> IssueAuditResult:
    normalized = normalize_issue(issue, base_url)
    selected_rules = tuple(rules) if rules is not None else active_rules()
    rules_by_id = {rule.rule_id: rule for rule in selected_rules}
    violations: list[AuditViolation] = []

    def fail(rule_id: str, observed: str, reason: str) -> None:
        rule = rules_by_id.get(rule_id)
        if rule is not None:
            violations.append(
                AuditViolation(
                    rule.rule_id,
                    rule.section,
                    rule.field,
                    str(observed or ""),
                    reason,
                    rule.guidance,
                )
            )

    summary_match = _SUMMARY_PATTERN.fullmatch(normalized.summary)
    if summary_match is None:
        fail(
            "SUMMARY.FORMAT",
            normalized.summary,
            "Summary 不符合 4–6 个分组、冒号、英文描述和最终复现概率的格式。",
        )
    else:
        groups = [
            item.strip()
            for item in re.findall(r"\[([^\]]+)\]", summary_match.group(1))
        ]
        customer, chip, version, module = groups[-4:]
        description = summary_match.group(2).strip()
        probability = summary_match.group(3).strip()

        for rule_id, value, reason in (
            ("SUMMARY.CUSTOMER", customer, "客户名称为空。"),
            ("SUMMARY.CHIP", chip, "CHIP 为空。"),
            ("SUMMARY.VERSION", version, "系统版本为空。"),
        ):
            if not value:
                fail(rule_id, value, reason)
        if customer and not _is_english_text(customer):
            fail(
                "SUMMARY.CUSTOMER_ENGLISH",
                customer,
                "客户名称不是有效的英文内容。",
            )
        if chip and (chip != chip.upper() or re.search(r"[A-Z]", chip) is None):
            fail(
                "SUMMARY.CHIP_UPPERCASE",
                chip,
                f"CHIP“{chip}”未按要求使用大写。",
            )
        if module not in ALLOWED_MODULES:
            fail(
                "SUMMARY.MODULE",
                module,
                f"模块“{module}”不在允许列表中。",
            )
        if not _is_english_text(description):
            fail(
                "SUMMARY.DESCRIPTION_ENGLISH",
                description,
                "问题描述不是有效的英文内容。",
            )
        if not _valid_rate(probability):
            fail(
                "SUMMARY.PROBABILITY",
                probability,
                f"复现概率“{probability}”格式无效。",
            )

    if not normalized.components:
        fail("COMPONENT.REQUIRED", "", "Component 为空。")
    else:
        unsupported = [
            component
            for component in normalized.components
            if component not in ALLOWED_MODULES
        ]
        if unsupported:
            fail(
                "COMPONENT.ALLOWED",
                ", ".join(normalized.components),
                f"Component 包含不支持的模块：{', '.join(unsupported)}。",
            )

    sections = _description_sections(normalized.description)
    for required in DESCRIPTION_SECTIONS:
        key = required.casefold()
        if not sections.get(key, "").strip():
            fail(
                _DESCRIPTION_RULE_IDS[key],
                normalized.description,
                f"{required} 章节缺失或为空。",
            )

    steps = sections.get("steps to reproduce", "")
    numbered = [
        (int(number), text.strip())
        for number, text in re.findall(r"(?m)^\s*(\d+)[.)]\s*(\S.*)$", steps)
    ]
    if steps and (
        not numbered
        or [number for number, _text in numbered]
        != list(range(1, len(numbered) + 1))
        or any(not text.strip(" ;.") for _number, text in numbered)
    ):
        fail(
            "DESCRIPTION.STEPS_ORDERED",
            steps,
            "复现步骤没有从 1 开始连续编号，或步骤内容不可执行。",
        )

    rate = next(
        iter(sections.get("reproducibility rate", "").splitlines()),
        "",
    ).strip()
    if rate and not _valid_rate(rate):
        fail(
            "DESCRIPTION.RATE_FORMAT",
            rate,
            f"Description 中的复现概率“{rate}”格式无效。",
        )

    notes = sections.get("notes", "")
    for marker, rule_id, label in (
        ("HW info", "DESCRIPTION.NOTES_HW", "硬件"),
        ("SW info", "DESCRIPTION.NOTES_SW", "软件"),
    ):
        if (
            re.search(
                rf"(?im)^[^\S\r\n]*{re.escape(marker)}[^\S\r\n]*:"
                rf"[^\S\r\n]*\S",
                notes,
            )
            is None
        ):
            fail(
                rule_id,
                notes,
                f"Notes 缺少已填写的{label}信息“{marker}: ...”。",
            )

    if any(label.casefold() == "regression" for label in normalized.labels):
        comparison = sections.get("comparision", "")
        previous = re.search(
            r"(?i)(?:previous|prior|older|baseline|old|last)\s+"
            r"(?:normal\s+)?(?:build|version)|"
            r"(?:build|version)\s*[\w.-]+.*(?:normal|pass|work)",
            comparison,
        )
        current = re.search(
            r"(?i)(?:current|new|broken|failing)\s+(?:build|version)|"
            r"(?:build|version)\s*[\w.-]+.*(?:broken|fail|issue)",
            comparison,
        )
        if previous is None or current is None:
            fail(
                "REGRESSION.EVIDENCE",
                comparison,
                "Regression 对比未同时说明旧版本正常和当前版本异常。",
            )

    for attachment in normalized.attachments:
        if attachment.size > MAX_ATTACHMENT_BYTES:
            fail(
                "ATTACHMENT.MAX_SIZE",
                f"{attachment.filename} ({attachment.size} bytes)",
                f"附件“{attachment.filename}”超过 10 MiB。",
            )

    return IssueAuditResult(
        key=normalized.key,
        url=normalized.url,
        summary=normalized.summary,
        reporter=normalized.reporter,
        passed=not violations,
        violations=tuple(violations),
    )
def _description_sections(description: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    aliases = {name.casefold() for name in DESCRIPTION_SECTIONS}
    for line in description.splitlines():
        cleaned = re.sub(r"^\s*#+\s*", "", line).strip()
        bracket = re.fullmatch(r"\[([^]]+)\]\s*:\s*", cleaned)
        key = (bracket.group(1) if bracket else cleaned.rstrip(":")).strip().casefold()
        if key in aliases:
            current = key
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _valid_rate(value: str) -> bool:
    text = value.strip().rstrip(".")
    if re.fullmatch(r"(?:100|\d{1,2})(?:\.\d+)?%", text):
        return True
    fraction = re.fullmatch(r"(\d+)\s*/\s*(\d+)", text)
    return bool(
        fraction
        and int(fraction.group(2)) > 0
        and 0 <= int(fraction.group(1)) <= int(fraction.group(2))
    )


def _is_english_text(value: str) -> bool:
    return value.isascii() and re.search(r"[A-Za-z]", value) is not None


def _plain_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _adf_text(value)
    return str(value or "")


def _adf_text(value: Any) -> str:
    if isinstance(value, dict):
        text = str(value.get("text", "") or "")
        children = "\n".join(_adf_text(item) for item in value.get("content") or [])
        return "\n".join(part for part in (text, children) if part)
    if isinstance(value, list):
        return "\n".join(_adf_text(item) for item in value)
    return ""


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
