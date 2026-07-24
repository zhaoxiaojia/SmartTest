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
from .rules import active_rules


_SUMMARY_PATTERN = re.compile(
    r"^\[([^\[\]]+)\]\[([^\[\]]+)\]\[([^\[\]]+)\]\s+([A-Za-z0-9].+)$"
)
_REQUIRED_SECTIONS = (
    "[Steps to reproduce]:",
    "[Actual results]:",
    "[Expected results]:",
    "[Reproducibility rate]:",
    "[Comparision]:",
    "[Notes]:",
    "HW info:",
    "SW info:",
)
_VERSION_PATTERN = re.compile(r"\b(?:\d{4}[._-]\d{1,2}[._-]\d{1,2}|[A-Za-z]*\d+(?:[._-]\d+)+)\b")
_PROBABILITY_PATTERN = re.compile(r"^(?:100|[1-9]?\d)%$|^\d+\s*/\s*[1-9]\d*$")
_TEN_MIB = 10 * 1024 * 1024


def normalize_issue(issue: dict[str, Any], base_url: str) -> AuditIssue:
    fields = issue.get("fields") if isinstance(issue, dict) else {}
    fields = fields if isinstance(fields, dict) else {}
    key = str(issue.get("key", "") or "").strip()
    reporter = fields.get("reporter") or {}
    if not isinstance(reporter, dict):
        reporter = {}
    components = tuple(
        str(item.get("name", "") or "").strip()
        for item in fields.get("components") or []
        if isinstance(item, dict) and str(item.get("name", "") or "").strip()
    )
    labels = tuple(str(item or "").strip() for item in fields.get("labels") or [] if str(item or "").strip())
    attachments = tuple(
        AuditAttachment(
            filename=str(item.get("filename", "") or ""),
            size=_safe_int(item.get("size")),
        )
        for item in fields.get("attachment") or []
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
    summary_match = _SUMMARY_PATTERN.match(normalized.summary)

    if summary_match is None:
        _add(violations, rules_by_id, "SUMMARY-001", normalized.summary, "Summary 结构不符合规范。")
    if not normalized.summary.isascii():
        _add(violations, rules_by_id, "SUMMARY-002", normalized.summary, "Summary 包含非英文字符。")
    if summary_match is not None and summary_match.group(2) != summary_match.group(2).upper():
        _add(violations, rules_by_id, "SUMMARY-003", normalized.summary, "CHIP 名称未全部大写。")
    elif summary_match is None:
        bracket_parts = re.findall(r"\[([^\[\]]+)\]", normalized.summary)
        if len(bracket_parts) >= 2 and bracket_parts[1] != bracket_parts[1].upper():
            _add(violations, rules_by_id, "SUMMARY-003", normalized.summary, "CHIP 名称未全部大写。")

    expected_component = summary_match.group(3).strip() if summary_match else ""
    if not normalized.components or (
        expected_component
        and expected_component.casefold() not in {item.casefold() for item in normalized.components}
    ):
        _add(
            violations,
            rules_by_id,
            "COMPONENT-001",
            ", ".join(normalized.components),
            "Component 缺失或与 Summary 的 Module 不一致。",
        )

    probability = _section_body(normalized.description, "[Reproducibility rate]:")
    if not _PROBABILITY_PATTERN.fullmatch(probability.strip()):
        _add(violations, rules_by_id, "PROBABILITY-001", probability, "复现概率格式无效。")

    missing_sections = [section for section in _REQUIRED_SECTIONS if section not in normalized.description]
    if missing_sections:
        _add(
            violations,
            rules_by_id,
            "DESCRIPTION-001",
            ", ".join(missing_sections),
            "Description 缺少必需章节。",
        )

    regression = any(label.casefold() == "regression" for label in normalized.labels)
    if regression and len(set(_VERSION_PATTERN.findall(normalized.description))) < 2:
        _add(
            violations,
            rules_by_id,
            "REGRESSION-001",
            _section_body(normalized.description, "SW info:"),
            "Regression 问题缺少两个可区分的版本证据。",
        )
    if regression and not _section_body(normalized.description, "[Comparision]:").strip():
        _add(
            violations,
            rules_by_id,
            "LABEL-001",
            ", ".join(normalized.labels),
            "regression Label 未提供 Comparision 结果。",
        )

    for attachment in normalized.attachments:
        if attachment.size > _TEN_MIB:
            _add(
                violations,
                rules_by_id,
                "ATTACHMENT-001",
                f"{attachment.filename} ({attachment.size} bytes)",
                "附件大小超过 10 MiB。",
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


def _section_body(description: str, heading: str) -> str:
    start = description.find(heading)
    if start < 0:
        return ""
    body_start = start + len(heading)
    following = [
        description.find(candidate, body_start)
        for candidate in _REQUIRED_SECTIONS
        if candidate != heading and description.find(candidate, body_start) >= 0
    ]
    body_end = min(following) if following else len(description)
    return description[body_start:body_end].strip()


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
