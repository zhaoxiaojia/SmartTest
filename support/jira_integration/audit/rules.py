from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

from .models import (
    AuditRule,
    AuditViolation,
    IssueAuditResult,
)


ALLOWED_MODULES = tuple(
    ("System|Online|Video|Ethernet|Wifi|BT|APK|HDMI|Audio|DLNA|Miracast|PQ|KPI|USB|"
     "Stability|Multivideo|Tr069|CTS / VTS / GTS / TVTS / STS / GGI / CTS-verify|"
     "MS12|DV|NTS|Primevideo").split("|")
)
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
DISABLED_RULE_IDS = frozenset(
    {
        "COMPONENT.ALLOWED",
        "DESCRIPTION.REPRODUCIBILITY_RATE",
        "ATTACHMENT.MAX_SIZE",
        "SUMMARY.MODULE",
        "SUMMARY.CHIP_UPPERCASE",
        "DESCRIPTION.STEPS_ORDERED",
    }
)
AI_REVIEWABLE_RULE_IDS = frozenset(
    {
        "SUMMARY.PROBABILITY",
        "DESCRIPTION.RATE_FORMAT",
        "DESCRIPTION.COMPARISON",
        "DESCRIPTION.NOTES_HW",
        "DESCRIPTION.NOTES_SW",
    }
)

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
    ("DESCRIPTION.COMPARISON", "Description", "description.comparison", "Description 必须包含非空的 Comparison。", "补充版本或平台对比信息。"),
    ("DESCRIPTION.NOTES", "Description", "description.notes", "Description 必须包含非空的 Notes。", "补充包含软硬件信息的备注。"),
    ("DESCRIPTION.STEPS_ORDERED", "Description", "description.steps_to_reproduce", "复现步骤必须从 1 开始连续编号，且每一步包含可执行动作。", "按顺序重写为完整的编号步骤。"),
    ("DESCRIPTION.RATE_FORMAT", "Description", "description.reproducibility_rate", "Description 中的复现概率必须是百分比或分数。", "使用 50% 或 1/2 等格式。"),
    ("DESCRIPTION.NOTES_HW", "Description", "description.notes", "Notes 必须包含已填写的“HW info: ...”。", "在 Notes 中补充 HW info。"),
    ("DESCRIPTION.NOTES_SW", "Description", "description.notes", "Notes 必须包含已填写的“SW info: ...”。", "在 Notes 中补充 SW info。"),
    ("REGRESSION.EVIDENCE", "Regression", "description.comparison", "Regression 问题必须同时说明旧版本正常和当前版本异常。", "在 Comparison 中补充旧版本正常与当前版本异常的对照证据。"),
    ("ATTACHMENT.MAX_SIZE", "Attachment", "attachment", "单个附件不得超过 10 MiB。", "压缩、拆分附件或改用链接。"),
)
_ALL_RULES = tuple(AuditRule(*row) for row in _RULE_DATA)
_RULES = tuple(
    rule for rule in _ALL_RULES
    if rule.rule_id not in DISABLED_RULE_IDS
)

_SUMMARY_RATE_AT_END = re.compile(
    r"(?P<rate>(?:100|\d{1,2})(?:\.\d+)?%|\d+\s*/\s*\d+)"
    r"\s*[.。]?\s*$"
)
_DESCRIPTION_RULES = (
    ("steps to reproduce", "DESCRIPTION.STEPS_TO_REPRODUCE"),
    ("actual results", "DESCRIPTION.ACTUAL_RESULTS"),
    ("expected results", "DESCRIPTION.EXPECTED_RESULTS"),
    ("reproducibility rate", "DESCRIPTION.REPRODUCIBILITY_RATE"),
    ("comparison", "DESCRIPTION.COMPARISON"),
    ("notes", "DESCRIPTION.NOTES"),
)
_DESCRIPTION_SECTION_ALIASES = {
    "steps to reproduce": (
        "Steps to reproduce",
        "Reproduction steps",
        "Test steps",
        "操作步骤",
        "复现步骤",
        "测试步骤",
    ),
    "actual results": (
        "Actual result",
        "Actual results",
        "Observed result",
        "Observed results",
        "实际结果",
        "实际现象",
        "问题现象",
    ),
    "expected results": (
        "Expected result",
        "Expected results",
        "Expected behavior",
        "Expected behaviour",
        "预期结果",
        "预期现象",
    ),
    "reproducibility rate": (
        "Reproducibility rate",
        "Reproduction rate",
        "Occurrence rate",
        "复现概率",
        "复现率",
        "出现概率",
    ),
    "comparison": (
        "Compare info",
        "Comparison",
        "Comparison info",
        "Version comparison",
        "Third Comparison",
        "Third-party Comparison",
        "Third party comparison",
        "对比信息",
        "版本对比",
        "第三方对比",
    ),
    "notes": (
        "Note",
        "Notes",
        "Remark",
        "Remarks",
        "Additional information",
        "备注",
        "补充信息",
    ),
}
_NOTES_INFO_ALIASES = {
    "hw": (
        "HW info",
        "HW information",
        "Hardware info",
        "Hardware information",
        "硬件信息",
    ),
    "sw": (
        "SW info",
        "SW information",
        "Software info",
        "Software information",
        "软件信息",
    ),
}
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
        if rule_id in DISABLED_RULE_IDS:
            return
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
    _audit_regression(normalized.labels, sections.get("comparison", ""), fail)
    for filename, size in normalized.attachments:
        if size > MAX_ATTACHMENT_BYTES:
            fail(
                "ATTACHMENT.MAX_SIZE",
                f"{filename} ({size} bytes)",
                f"附件“{filename}”超过 10 MiB。",
            )

    return IssueAuditResult(
        key=normalized.key,
        url=normalized.url,
        summary=normalized.summary,
        reporter=normalized.reporter,
        passed=not violations,
        violations=tuple(violations),
        has_ai_candidates=bool(_ai_reviewable_violations(violations)),
        _ai_description=normalized.description,
    )


def ai_reviewable_violations(
    result: IssueAuditResult,
) -> tuple[AuditViolation, ...]:
    return _ai_reviewable_violations(result.violations)


def _ai_reviewable_violations(
    violations: Sequence[AuditViolation],
) -> tuple[AuditViolation, ...]:
    return tuple(
        violation
        for violation in violations
        if _is_ai_reviewable_violation(violation)
    )


def _is_ai_reviewable_violation(violation: AuditViolation) -> bool:
    if violation.rule_id not in AI_REVIEWABLE_RULE_IDS:
        return False
    if violation.rule_id in {
        "SUMMARY.PROBABILITY",
        "DESCRIPTION.RATE_FORMAT",
    }:
        return True
    aliases = {
        "DESCRIPTION.COMPARISON": _DESCRIPTION_SECTION_ALIASES["comparison"],
        "DESCRIPTION.NOTES_HW": _NOTES_INFO_ALIASES["hw"],
        "DESCRIPTION.NOTES_SW": _NOTES_INFO_ALIASES["sw"],
    }[violation.rule_id]
    observed = violation.observed.casefold()
    return any(alias.casefold() in observed for alias in aliases)


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
    groups, description, probability, errors = _parse_summary_format(summary)
    if errors:
        fail(
            "SUMMARY.FORMAT",
            summary,
            "；".join(errors) + "。",
        )
        return

    customer, chip, version, module = groups[-4:]
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


def _parse_summary_format(
    value: str,
) -> tuple[list[str], str, str, list[str]]:
    text = str(value or "").strip()
    groups: list[str] = []
    errors: list[str] = []
    position = 0
    bracket_pairs = {"[": "]", "【": "】"}
    while position < len(text):
        while position < len(text) and text[position].isspace():
            position += 1
        opening = text[position] if position < len(text) else ""
        if opening not in bracket_pairs:
            break
        closing = bracket_pairs[opening]
        closing_position = text.find(closing, position + 1)
        if closing_position < 0:
            errors.append(
                f"第 {len(groups) + 1} 个字段缺少右方括号“{closing}”"
            )
            return groups, "", "", errors
        groups.append(text[position + 1:closing_position].strip())
        position = closing_position + 1

    group_count_error = ""
    if not 4 <= len(groups) <= 6:
        group_count_error = f"方括号字段数量为 {len(groups)}，要求 4–6 个"
        errors.append(group_count_error)
    empty_groups = [
        str(index) for index, group in enumerate(groups, 1)
        if not group
    ]
    if empty_groups:
        errors.append(f"第 {', '.join(empty_groups)} 个方括号字段为空")

    while position < len(text) and text[position].isspace():
        position += 1
    if position >= len(text) or text[position] not in (":", "："):
        errors.append("方括号字段后缺少必需的冒号（允许“:”或“：”）")
        return groups, "", "", errors

    body = text[position + 1:].strip()
    misplaced_group = re.match(r"^(\[([^\]]+)\]|【([^】]+)】)", body)
    misplaced_module = (
        (misplaced_group.group(2) or misplaced_group.group(3)).strip()
        if misplaced_group
        else ""
    )
    if len(groups) == 3 and misplaced_module.casefold() in {
        module.casefold() for module in ALLOWED_MODULES
    }:
        errors.remove(group_count_error)
        errors.append(
            f"Bug 模块字段“{misplaced_group.group(1)}”位于冒号后，"
            f"导致冒号前只有 3 个字段；应将“{misplaced_group.group(1)}”移到冒号前"
        )
    rate_match = _SUMMARY_RATE_AT_END.search(body)
    probability = rate_match.group("rate").strip() if rate_match else ""
    description = (
        body[:rate_match.start()].rstrip().rstrip(",，").rstrip()
        if rate_match
        else body
    )
    if not description:
        errors.append("冒号后的问题描述为空")
    return groups, description, probability, errors


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
    for info_kind, rule_id, label in (
        ("hw", "DESCRIPTION.NOTES_HW", "硬件"),
        ("sw", "DESCRIPTION.NOTES_SW", "软件"),
    ):
        if not _notes_have_info(notes, info_kind):
            marker = "HW info" if info_kind == "hw" else "SW info"
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
    aliases = {
        _normalize_label(alias): section
        for section, section_aliases in _DESCRIPTION_SECTION_ALIASES.items()
        for alias in section_aliases
    }
    for line in description.splitlines():
        labeled = _split_labeled_line(line)
        section = aliases.get(labeled[0]) if labeled else None
        if section:
            current = section
            sections.setdefault(current, [])
            if labeled and labeled[1]:
                sections[current].append(labeled[1])
        elif current:
            sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _notes_have_info(notes: str, info_kind: str) -> bool:
    aliases = {
        _normalize_label(alias)
        for alias in _NOTES_INFO_ALIASES.get(info_kind, ())
    }
    known_labels = {
        _normalize_label(alias)
        for alias_group in (
            *_DESCRIPTION_SECTION_ALIASES.values(),
            *_NOTES_INFO_ALIASES.values(),
        )
        for alias in alias_group
    }
    lines = notes.splitlines()
    for index, line in enumerate(lines):
        labeled = _split_labeled_line(line)
        if not labeled or labeled[0] not in aliases:
            continue
        if labeled[1]:
            return True
        for following in lines[index + 1:]:
            if not following.strip():
                continue
            following_label = _split_labeled_line(following)
            return not following_label or following_label[0] not in known_labels
    return False


def _split_labeled_line(line: str) -> tuple[str, str] | None:
    cleaned = re.sub(r"^\s*#+\s*", "", line).strip()
    cleaned = re.sub(r"^[*_]{1,3}\s*", "", cleaned)
    cleaned = cleaned.replace("\uFF1A", ":")
    cleaned = re.sub(r"(?<=\])[*_]{1,3}(?=:)", "", cleaned)
    bracket = re.fullmatch(r"\[([^]]+)\]\s*(?::\s*[*_]{0,3}\s*(.*))?", cleaned)
    if bracket:
        return (
            _normalize_label(bracket.group(1)),
            (bracket.group(2) or "").strip("*_ "),
        )
    labeled = re.fullmatch(r"([^:]+?)\s*:\s*[*_]{0,3}\s*(.*)", cleaned)
    if labeled:
        return _normalize_label(labeled.group(1)), labeled.group(2).strip("*_ ")
    standalone = _normalize_label(cleaned)
    return (standalone, "") if standalone else None


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().strip("*_").split()).casefold()


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
