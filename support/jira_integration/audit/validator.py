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
from .rules import (
    ALLOWED_MODULES,
    DESCRIPTION_SECTIONS,
    MAX_ATTACHMENT_BYTES,
    active_rules,
)


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

    summary_match = _SUMMARY_PATTERN.fullmatch(normalized.summary)
    if summary_match is None:
        _add(
            violations,
            rules_by_id,
            "SUMMARY.FORMAT",
            normalized.summary,
            "Summary 不符合 4–6 个分组、冒号、英文描述和最终复现概率的格式。",
        )
    else:
        groups = [item.strip() for item in re.findall(r"\[([^\]]+)\]", summary_match.group(1))]
        customer, chip, version, module = groups[-4:]
        description = summary_match.group(2).strip()
        probability = summary_match.group(3).strip()

        for rule_id, value, reason in (
            ("SUMMARY.CUSTOMER", customer, "客户名称为空。"),
            ("SUMMARY.CHIP", chip, "CHIP 为空。"),
            ("SUMMARY.VERSION", version, "系统版本为空。"),
        ):
            if not value:
                _add(violations, rules_by_id, rule_id, value, reason)
        if customer and not _is_english_text(customer):
            _add(
                violations,
                rules_by_id,
                "SUMMARY.CUSTOMER_ENGLISH",
                customer,
                "客户名称不是有效的英文内容。",
            )
        if chip and (chip != chip.upper() or re.search(r"[A-Z]", chip) is None):
            _add(
                violations,
                rules_by_id,
                "SUMMARY.CHIP_UPPERCASE",
                chip,
                f"CHIP“{chip}”未按要求使用大写。",
            )
        if module not in ALLOWED_MODULES:
            _add(
                violations,
                rules_by_id,
                "SUMMARY.MODULE",
                module,
                f"模块“{module}”不在允许列表中。",
            )
        if not _is_english_text(description):
            _add(
                violations,
                rules_by_id,
                "SUMMARY.DESCRIPTION_ENGLISH",
                description,
                "问题描述不是有效的英文内容。",
            )
        if not _valid_rate(probability):
            _add(
                violations,
                rules_by_id,
                "SUMMARY.PROBABILITY",
                probability,
                f"复现概率“{probability}”格式无效。",
            )

    if not normalized.components:
        _add(
            violations,
            rules_by_id,
            "COMPONENT.REQUIRED",
            "",
            "Component 为空。",
        )
    else:
        unsupported = [
            component for component in normalized.components if component not in ALLOWED_MODULES
        ]
        if unsupported:
            _add(
                violations,
                rules_by_id,
                "COMPONENT.ALLOWED",
                ", ".join(normalized.components),
                f"Component 包含不支持的模块：{', '.join(unsupported)}。",
            )

    sections = _description_sections(normalized.description)
    for required in DESCRIPTION_SECTIONS:
        key = required.casefold()
        if not sections.get(key, "").strip():
            _add(
                violations,
                rules_by_id,
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
        or [number for number, _text in numbered] != list(range(1, len(numbered) + 1))
        or any(not text.strip(" ;.") for _number, text in numbered)
    ):
        _add(
            violations,
            rules_by_id,
            "DESCRIPTION.STEPS_ORDERED",
            steps,
            "复现步骤没有从 1 开始连续编号，或步骤内容不可执行。",
        )

    rate = next(
        iter(sections.get("reproducibility rate", "").splitlines()),
        "",
    ).strip()
    if rate and not _valid_rate(rate):
        _add(
            violations,
            rules_by_id,
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
            _add(
                violations,
                rules_by_id,
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
            _add(
                violations,
                rules_by_id,
                "REGRESSION.EVIDENCE",
                comparison,
                "Regression 对比未同时说明旧版本正常和当前版本异常。",
            )

    for attachment in normalized.attachments:
        if attachment.size > MAX_ATTACHMENT_BYTES:
            _add(
                violations,
                rules_by_id,
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


def _add(
    violations: list[AuditViolation],
    rules: dict[str, AuditRule],
    rule_id: str,
    observed: str,
    reason: str,
) -> None:
    rule = rules.get(rule_id)
    if rule is None:
        return
    violations.append(
        AuditViolation(
            rule_id=rule.rule_id,
            section=rule.section,
            field=rule.field,
            observed=str(observed or ""),
            reason=reason,
            guidance=rule.guidance,
        )
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
