from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

from .models import AuditRule, AuditViolation, IssueAuditResult


ALLOWED_MODULES = tuple(
    ("System|Online|Video|Ethernet|Wifi|BT|APK|HDMI|Audio|DLNA|Miracast|PQ|KPI|USB|"
     "Stability|Multivideo|Tr069|CTS / VTS / GTS / TVTS / STS / GGI / CTS-verify|"
     "MS12|DV|NTS|Primevideo").split("|")
)
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

_RULE_DATA = (
    ("SUMMARY.FORMAT", "Summary", "summary", "Summary 必须包含 4–6 个方括号分组，最后四组依次为客户、CHIP、系统版本和模块，随后填写英文问题描述与复现概率。", "使用“[客户][CHIP][版本][模块]: 英文问题描述,复现概率”；前面可选增加公共 Jira ID 和客户 Bug ID。"),
    ("SUMMARY.CUSTOMER", "Summary", "summary.customer", "Summary 必须填写客户英文名。", "填写客户英文名或英文项目代号。"),
    ("SUMMARY.CHIP", "Summary", "summary.chip", "Summary 必须填写 CHIP。", "填写大写 CHIP 名称。"),
    ("SUMMARY.VERSION", "Summary", "summary.version", "Summary 必须填写系统版本。", "填写明确的系统版本。"),
    ("SUMMARY.CUSTOMER_ENGLISH", "Summary", "summary.customer", "客户名称必须使用英文名或英文项目代号。", "将客户名称改为英文名或英文项目代号。"),
    ("SUMMARY.CHIP_UPPERCASE", "Summary", "summary.chip", "CHIP 必须包含字母并使用大写。", "将 CHIP 名称中的字母改为大写。"),
    ("SUMMARY.MODULE", "Summary", "summary.module", "Summary 的模块必须来自规范允许的模块列表。", "选择规则明细中列出的模块名称。"),
    ("SUMMARY.DESCRIPTION_ENGLISH", "Summary", "summary.description", "Summary 的问题描述必须使用英文。", "使用英文描述问题现象。"),
    ("SUMMARY.PROBABILITY", "Summary", "summary.probability", "Summary 的复现概率必须是百分比或分数。", "使用 50% 或 1/2 等格式。"),
    ("COMPONENT.REQUIRED", "Component", "components", "至少填写一个 Component。", "选择一个或多个与问题相关的 Component。"),
    ("COMPONENT.ALLOWED", "Component", "components", "每个 Component 都必须来自规范允许的模块列表。", "移除不支持的 Component，改用规则明细中的模块名称。"),
    ("DESCRIPTION.STEPS_TO_REPRODUCE", "Description", "description.steps_to_reproduce", "Description 必须包含非空的 Steps to reproduce。", "补充可执行的复现步骤。"),
    ("DESCRIPTION.ACTUAL_RESULTS", "Description", "description.actual_results", "Description 必须包含非空的 Actual results。", "补充实际发生的结果。"),
    ("DESCRIPTION.EXPECTED_RESULTS", "Description", "description.expected_results", "Description 必须包含非空的 Expected results。", "补充预期结果。"),
    ("DESCRIPTION.REPRODUCIBILITY_RATE", "Description", "description.reproducibility_rate", "Description 必须包含非空的 Reproducibility rate。", "补充百分比或分数形式的复现概率。"),
    ("DESCRIPTION.COMPARISION", "Description", "description.comparision", "Description 必须包含非空的 Comparision。", "补充版本或平台对比信息。"),
    ("DESCRIPTION.NOTES", "Description", "description.notes", "Description 必须包含非空的 Notes。", "补充包含软硬件信息的备注。"),
    ("DESCRIPTION.STEPS_ORDERED", "Description", "description.steps_to_reproduce", "复现步骤必须从 1 开始连续编号，且每一步包含可执行动作。", "按顺序重写为完整的编号步骤。"),
    ("DESCRIPTION.RATE_FORMAT", "Description", "description.reproducibility_rate", "Description 中的复现概率必须是百分比或分数。", "使用 50% 或 1/2 等格式。"),
    ("DESCRIPTION.NOTES_HW", "Description", "description.notes", "Notes 必须包含已填写的“HW info: ...”。", "在 Notes 中补充 HW info。"),
    ("DESCRIPTION.NOTES_SW", "Description", "description.notes", "Notes 必须包含已填写的“SW info: ...”。", "在 Notes 中补充 SW info。"),
    ("REGRESSION.EVIDENCE", "Regression", "description.comparision", "Regression 问题必须同时说明旧版本正常和当前版本异常。", "在 Comparision 中补充旧版本正常与当前版本异常的对照证据。"),
    ("ATTACHMENT.MAX_SIZE", "Attachment", "attachment", "单个附件不得超过 10 MiB。", "压缩、拆分附件或改用链接。"),
)
_RULES = tuple(AuditRule(*row) for row in _RULE_DATA)

_SUMMARY_PATTERN = re.compile(r"((?:\[[^\]\r\n]+\]){4,6}):\s*(.+),\s*([^,]+)\.?")
_DESCRIPTION_RULES = (
    ("steps to reproduce", "DESCRIPTION.STEPS_TO_REPRODUCE"),
    ("actual results", "DESCRIPTION.ACTUAL_RESULTS"),
    ("expected results", "DESCRIPTION.EXPECTED_RESULTS"),
    ("reproducibility rate", "DESCRIPTION.REPRODUCIBILITY_RATE"),
    ("comparision", "DESCRIPTION.COMPARISION"),
    ("notes", "DESCRIPTION.NOTES"),
)
_DESCRIPTION_HEADINGS = {name for name, _rule_id in _DESCRIPTION_RULES}
_Failure = Callable[[str, Any, str], None]


class _Issue(NamedTuple):
    key: str
    url: str
    summary: str
    description: str
    reporter: str
    components: tuple[str, ...]
    labels: tuple[str, ...]
    attachments: tuple[tuple[str, int], ...]


def active_rules() -> tuple[AuditRule, ...]:
    return _RULES


def audit_issue(
    issue: dict[str, Any],
    *,
    base_url: str,
    rules: Sequence[AuditRule] | None = None,
) -> IssueAuditResult:
    normalized = _normalize_issue(issue, base_url)
    selected = {rule.rule_id: rule for rule in (rules or _RULES)}
    violations: list[AuditViolation] = []

    def fail(rule_id: str, observed: Any, reason: str) -> None:
        rule = selected.get(rule_id)
        if rule:
            violations.append(
                AuditViolation(
                    rule.rule_id, rule.section, rule.field,
                    str(observed or ""), reason, rule.guidance,
                )
            )

    _audit_summary(normalized.summary, fail)
    _audit_components(normalized.components, fail)
    sections = _audit_description(normalized.description, fail)
    _audit_regression(normalized.labels, sections.get("comparision", ""), fail)
    for filename, size in normalized.attachments:
        if size > MAX_ATTACHMENT_BYTES:
            fail(
                "ATTACHMENT.MAX_SIZE",
                f"{filename} ({size} bytes)",
                f"附件“{filename}”超过 10 MiB。",
            )

    return IssueAuditResult(
        normalized.key, normalized.url, normalized.summary,
        normalized.reporter, not violations, tuple(violations),
    )


def _normalize_issue(issue: dict[str, Any], base_url: str) -> _Issue:
    fields = issue.get("fields") if isinstance(issue, dict) else {}
    fields = fields if isinstance(fields, dict) else {}
    key = str(issue.get("key", "") or "").strip()
    reporter = fields.get("reporter")
    reporter = reporter if isinstance(reporter, dict) else {}
    components = tuple(
        value
        for item in fields.get("components") or ()
        if (value := _item_text(item, "name"))
    )
    labels = tuple(
        value
        for item in fields.get("labels") or ()
        if (value := _item_text(item))
    )
    attachments = tuple(
        (str(item.get("filename", "") or ""), _safe_int(item.get("size")))
        for item in (fields.get("attachment") or fields.get("attachments") or ())
        if isinstance(item, dict)
    )
    reporter_name = (
        reporter.get("displayName")
        or reporter.get("name")
        or reporter.get("emailAddress")
        or ""
    )
    return _Issue(
        key,
        f"{str(base_url or '').rstrip('/')}/browse/{key}",
        str(fields.get("summary", "") or ""),
        _plain_text(fields.get("description")),
        str(reporter_name),
        components,
        labels,
        attachments,
    )


def _audit_summary(summary: str, fail: _Failure) -> None:
    match = _SUMMARY_PATTERN.fullmatch(summary)
    if not match:
        fail(
            "SUMMARY.FORMAT",
            summary,
            "Summary 不符合 4–6 个分组、冒号、英文描述和最终复现概率的格式。",
        )
        return

    groups = [item.strip() for item in re.findall(r"\[([^\]]+)\]", match.group(1))]
    customer, chip, version, module = groups[-4:]
    description, probability = match.group(2).strip(), match.group(3).strip()
    for rule_id, value, reason in (
        ("SUMMARY.CUSTOMER", customer, "客户名称为空。"),
        ("SUMMARY.CHIP", chip, "CHIP 为空。"),
        ("SUMMARY.VERSION", version, "系统版本为空。"),
    ):
        if not value:
            fail(rule_id, value, reason)
    if customer and not _is_english(customer):
        fail("SUMMARY.CUSTOMER_ENGLISH", customer, "客户名称不是有效的英文内容。")
    if chip and (chip != chip.upper() or not re.search(r"[A-Z]", chip)):
        fail("SUMMARY.CHIP_UPPERCASE", chip, f"CHIP“{chip}”未按要求使用大写。")
    if module not in ALLOWED_MODULES:
        fail("SUMMARY.MODULE", module, f"模块“{module}”不在允许列表中。")
    if not _is_english(description):
        fail("SUMMARY.DESCRIPTION_ENGLISH", description, "问题描述不是有效的英文内容。")
    if not _valid_rate(probability):
        fail("SUMMARY.PROBABILITY", probability, f"复现概率“{probability}”格式无效。")


def _audit_components(components: tuple[str, ...], fail: _Failure) -> None:
    if not components:
        fail("COMPONENT.REQUIRED", "", "Component 为空。")
        return
    unsupported = [value for value in components if value not in ALLOWED_MODULES]
    if unsupported:
        fail(
            "COMPONENT.ALLOWED",
            ", ".join(components),
            f"Component 包含不支持的模块：{', '.join(unsupported)}。",
        )


def _audit_description(description: str, fail: _Failure) -> dict[str, str]:
    sections = _description_sections(description)
    for heading, rule_id in _DESCRIPTION_RULES:
        if not sections.get(heading, "").strip():
            fail(rule_id, description, f"{heading.title()} 章节缺失或为空。")

    steps = sections.get("steps to reproduce", "")
    numbered = [
        (int(number), text.strip())
        for number, text in re.findall(r"(?m)^\s*(\d+)[.)]\s*(\S.*)$", steps)
    ]
    if steps and (
        not numbered
        or [number for number, _text in numbered] != list(range(1, len(numbered) + 1))
        or any(not text.strip(" ;.") for _number, text in numbered)
    ):
        fail(
            "DESCRIPTION.STEPS_ORDERED",
            steps,
            "复现步骤没有从 1 开始连续编号，或步骤内容不可执行。",
        )

    rate = sections.get("reproducibility rate", "").splitlines()
    if rate and not _valid_rate(rate[0]):
        fail(
            "DESCRIPTION.RATE_FORMAT",
            rate[0].strip(),
            f"Description 中的复现概率“{rate[0].strip()}”格式无效。",
        )
    notes = sections.get("notes", "")
    for marker, rule_id, label in (
        ("HW info", "DESCRIPTION.NOTES_HW", "硬件"),
        ("SW info", "DESCRIPTION.NOTES_SW", "软件"),
    ):
        pattern = rf"(?im)^[^\S\r\n]*{re.escape(marker)}[^\S\r\n]*:[^\S\r\n]*\S"
        if not re.search(pattern, notes):
            fail(rule_id, notes, f"Notes 缺少已填写的{label}信息“{marker}: ...”。")
    return sections


def _audit_regression(
    labels: tuple[str, ...], comparison: str, fail: _Failure
) -> None:
    if not any(label.casefold() == "regression" for label in labels):
        return
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
    if not previous or not current:
        fail(
            "REGRESSION.EVIDENCE",
            comparison,
            "Regression 对比未同时说明旧版本正常和当前版本异常。",
        )


def _description_sections(description: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in description.splitlines():
        cleaned = re.sub(r"^\s*#+\s*", "", line).strip()
        bracket = re.fullmatch(r"\[([^]]+)\]\s*:\s*", cleaned)
        heading = (bracket.group(1) if bracket else cleaned.rstrip(":")).strip().casefold()
        if heading in _DESCRIPTION_HEADINGS:
            current = heading
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
        and int(fraction.group(1)) <= int(fraction.group(2))
    )


def _is_english(value: str) -> bool:
    return value.isascii() and re.search(r"[A-Za-z]", value) is not None


def _item_text(item: Any, key: str | None = None) -> str:
    value = item.get(key, "") if key and isinstance(item, dict) else item
    return str(value or "").strip()


def _plain_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _adf_text(value)
    return str(value or "")


def _adf_text(value: Any) -> str:
    if isinstance(value, dict):
        parts = [str(value.get("text", "") or "")]
        parts.extend(_adf_text(item) for item in value.get("content") or ())
        return "\n".join(part for part in parts if part)
    if isinstance(value, list):
        return "\n".join(_adf_text(item) for item in value)
    return ""


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
