from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any, NamedTuple

from .models import (
    AuditRule,
    AuditViolation,
    IssueAuditResult,
)

AI_REVIEWABLE_RULE_IDS = frozenset(
    {
        "SUMMARY.FORMAT",
        "DESCRIPTION.STEPS_TO_REPRODUCE",
        "DESCRIPTION.ACTUAL_RESULTS",
        "DESCRIPTION.EXPECTED_RESULTS",
        "DESCRIPTION.RATE_FORMAT",
        "DESCRIPTION.COMPARISON",
        "DESCRIPTION.NOTES",
        "DESCRIPTION.NOTES_HW",
        "DESCRIPTION.NOTES_SW",
    }
)
_PERSONNEL_PATH = Path(__file__).resolve().parents[3] / "config" / "personnel.json"


@cache
def creator_names() -> frozenset[str]:
    personnel = json.loads(_PERSONNEL_PATH.read_text(encoding="utf-8"))
    employees = personnel["amlogic"]["departments"]["FAE-QA"]["employees"]
    return frozenset(
        str(employee.get("display_name") or "").strip()
        for employee in employees
        if employee.get("active") is not False
        and str(employee.get("display_name") or "").strip()
    )

_RULE_DATA = (
    ("SUMMARY.FORMAT", "Summary", "Summary", "Summary 必须包含 4–6 个方括号分组，最后四组依次为客户、CHIP、系统版本和模块，冒号后填写非空问题描述。", "使用“[客户][CHIP][版本][模块]: 问题描述”；前面可选增加公共 Jira ID 和客户 Bug ID。"),
    ("COMPONENT.REQUIRED", "Component", "Component", "至少填写一个 Component。", "填写与问题对应的 Component。"),
    ("DESCRIPTION.STEPS_TO_REPRODUCE", "Description", "Description", "Description 必须包含非空的 Steps to reproduce。", "补充可执行的复现步骤。"),
    ("DESCRIPTION.ACTUAL_RESULTS", "Description", "Description", "Description 必须包含非空的 Actual results。", "补充实际发生的结果。"),
    ("DESCRIPTION.EXPECTED_RESULTS", "Description", "Description", "Description 必须包含非空的 Expected results。", "补充预期结果。"),
    ("DESCRIPTION.COMPARISON", "Description", "Description", "Description 必须包含非空的 Comparison。", "补充版本对比信息。"),
    ("DESCRIPTION.NOTES", "Description", "Description", "Description 必须包含非空的 Notes。", "补充包含软硬件信息的备注。"),
    ("DESCRIPTION.RATE_FORMAT", "Description", "Description.Reproducibility rate", "复现概率必须是百分比、分数或明确的文字次数，例如 50%、1/2 或出现一次。", "改为百分比、分数或“出现/复现 + 数字 + 次”；文字次数后可补充一组半角或全角括号说明。"),
    ("DESCRIPTION.NOTES_HW", "Description", "Description.Notes", "Notes 必须包含“HW info: ...”。", "补充 HW info。"),
    ("DESCRIPTION.NOTES_SW", "Description", "Description.Notes", "Notes 必须包含“SW info: ...”。", "补充 SW info。"),
    ("DESCRIPTION.TABLE_REQUIRED_VALUE", "Description", "Description.测试信息", "第二套 Description 表格中每一行的测试信息均不能为空。", "在对应行的测试信息列填写内容；允许填写“无”或“-”。"),
)
_RULES = tuple(AuditRule(*row) for row in _RULE_DATA)

_TEXTUAL_OCCURRENCE_RATE = (
    r"(?:出现|复现)\s*(?:\d+|[零〇一二两三四五六七八九十百千万]+)\s*次"
)
_STANDARD_SUMMARY_RATE_AT_END = re.compile(
    rf"(?P<rate>(?:100|\d{{1,2}})(?:\.\d+)?%|\d+\s*/\s*\d+|"
    rf"{_TEXTUAL_OCCURRENCE_RATE})"
    r"\s*[.。]?\s*$"
)
_DESCRIPTION_RULES = (
    ("steps to reproduce", "DESCRIPTION.STEPS_TO_REPRODUCE"),
    ("actual results", "DESCRIPTION.ACTUAL_RESULTS"),
    ("expected results", "DESCRIPTION.EXPECTED_RESULTS"),
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
        "期望结果",
        "预期现象",
    ),
    "reproducibility rate": (
        "Reproducibility rate",
        "Reproduction rate",
        "Occurrence rate",
        "复现概率",
        "复现率",
        "出现概率",
        "概率",
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
        "对比结果",
        "比较结果",
        "对比情况",
        "比较情况",
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
        "软件版本",
    ),
}
_AI_SEMANTIC_HINTS = {
    "DESCRIPTION.STEPS_TO_REPRODUCE": (
        r"(?:打开|进入|点击|选择|播放|启动|连接|安装|重启|操作)",
    ),
    "DESCRIPTION.ACTUAL_RESULTS": (
        r"(?:异常|失败|冻结|卡顿|黑屏|无响应|报错|崩溃|不能|无法)",
    ),
    "DESCRIPTION.EXPECTED_RESULTS": (
        r"(?:应该|应当|期望|预期|正常(?:显示|播放|工作|运行))",
    ),
    "DESCRIPTION.COMPARISON": (
        r"(?:上一|旧|当前|本次|新)版本",
        r"(?:previous|current|old|new)\s+(?:version|build)",
    ),
    "DESCRIPTION.NOTES": (r"(?:补充说明|备注|附加信息)",),
    "DESCRIPTION.NOTES_HW": (
        r"(?:硬件|机型|型号|平台|尺寸|board|device|model)",
    ),
    "DESCRIPTION.NOTES_SW": (
        r"(?:软件|测试版本|构建版本|固件|build|firmware)",
    ),
}
_Failure = Callable[[str, Any, str], None]


class _Issue(NamedTuple):
    key: str
    url: str
    summary: str
    description: str
    creator: str
    components: tuple[str, ...]


def active_rules() -> tuple[AuditRule, ...]:
    return _RULES


def is_audit_eligible(issue: dict[str, Any]) -> bool:
    fields = issue.get("fields") if isinstance(issue, dict) else {}
    fields = fields if isinstance(fields, dict) else {}
    match_name = " ".join(_creator_name(fields).split()).casefold()
    return any(match_name == name.casefold() for name in creator_names())


def _creator_name(fields: dict[str, Any]) -> str:
    creator = fields.get("creator")
    if isinstance(creator, dict):
        username = _normalize_username(
            creator.get("name")
            or creator.get("key")
            or creator.get("accountId")
        )
        display_name = " ".join(
            str(creator.get("displayName") or "").split()
        )
        creator_name = display_name or _name_from_username(username)
    else:
        creator_name = str(creator or "").strip()
    return creator_name


def _normalize_username(username: Any) -> str:
    value = str(username or "").strip().lower()
    if "\\" in value:
        value = value.rsplit("\\", 1)[-1]
    return value.split("@", 1)[0]


def _name_from_username(username: Any) -> str:
    return " ".join(
        part.capitalize()
        for part in _normalize_username(username).split(".")
        if part
    )


def audit_issue(
    issue: dict[str, Any],
    *,
    base_url: str,
) -> IssueAuditResult:
    normalized = _normalize_issue(issue, base_url)
    selected = {rule.rule_id: rule for rule in _RULES}
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
    if not normalized.components:
        fail("COMPONENT.REQUIRED", "[]", "Component 为空。")
    _audit_description(normalized.description, fail)

    return IssueAuditResult(
        key=normalized.key,
        url=normalized.url,
        summary=normalized.summary,
        creator=normalized.creator,
        passed=not violations,
        violations=tuple(violations),
    )


def ai_reviewable_violations(
    result: IssueAuditResult,
    *,
    description: str | None = None,
) -> tuple[AuditViolation, ...]:
    return tuple(
        violation
        for violation in result.violations
        if _is_ai_reviewable_violation(
            violation,
            description=description,
        )
    )


def _is_ai_reviewable_violation(
    violation: AuditViolation,
    *,
    description: str | None = None,
) -> bool:
    if violation.rule_id not in AI_REVIEWABLE_RULE_IDS:
        return False
    if violation.rule_id == "SUMMARY.FORMAT":
        groups, description, _errors = _parse_summary_format(
            violation.observed
        )
        return (
            4 <= len(groups) <= 6
            and all(groups)
            and bool(re.search(r"[A-Za-z\u4e00-\u9fff]", description))
        )
    if violation.rule_id == "DESCRIPTION.RATE_FORMAT":
        return True
    observed = (
        violation.observed
        if description is None
        else description
    ).casefold()
    explicit_aliases = {
        "DESCRIPTION.COMPARISON": _DESCRIPTION_SECTION_ALIASES["comparison"],
        "DESCRIPTION.NOTES_HW": _NOTES_INFO_ALIASES["hw"],
        "DESCRIPTION.NOTES_SW": _NOTES_INFO_ALIASES["sw"],
    }.get(violation.rule_id, ())
    if any(alias.casefold() in observed for alias in explicit_aliases):
        return True
    return any(
        re.search(pattern, observed, re.IGNORECASE)
        for pattern in _AI_SEMANTIC_HINTS.get(violation.rule_id, ())
    )


def _normalize_issue(issue: dict[str, Any], base_url: str) -> _Issue:
    fields = issue.get("fields") if isinstance(issue, dict) else {}
    fields = fields if isinstance(fields, dict) else {}
    key = str(issue.get("key", "") or "").strip()
    components = tuple(
        value
        for item in fields.get("components") or ()
        if (value := _item_text(item, "name"))
    )
    return _Issue(
        key,
        f"{str(base_url or '').rstrip('/')}/browse/{key}",
        str(fields.get("summary", "") or ""),
        issue_description(issue),
        _creator_name(fields),
        components,
    )


def issue_description(issue: dict[str, Any]) -> str:
    fields = issue.get("fields") if isinstance(issue, dict) else {}
    fields = fields if isinstance(fields, dict) else {}
    return _plain_text(fields.get("description"))


def _audit_summary(summary: str, fail: _Failure) -> None:
    _groups, _description, errors = _parse_summary_format(summary)
    if errors:
        fail(
            "SUMMARY.FORMAT",
            summary,
            "；".join(errors) + "。",
        )
        return


def _parse_summary_format(
    value: str,
) -> tuple[list[str], str, list[str]]:
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
            return groups, "", errors
        groups.append(text[position + 1:closing_position].strip())
        position = closing_position + 1

    if not 4 <= len(groups) <= 6:
        errors.append(f"方括号字段数量为 {len(groups)}，要求 4–6 个")
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
        return groups, text[position:].strip(), errors

    body = text[position + 1:].strip()
    rate_match = _STANDARD_SUMMARY_RATE_AT_END.search(body)
    prefix = body[:rate_match.start()].rstrip() if rate_match else body
    if (
        rate_match
        and re.fullmatch(_TEXTUAL_OCCURRENCE_RATE, rate_match.group("rate"))
        and prefix
        and prefix[-1:] not in ",，;；"
    ):
        rate_match = None
        prefix = body
    description = prefix.rstrip(",，;；").rstrip() if rate_match else body
    if not description:
        errors.append("冒号后的问题描述为空")
    return groups, description, errors


def _audit_description(description: str, fail: _Failure) -> dict[str, str]:
    table_rows = _second_description_table_rows(description)
    if table_rows is not None:
        for row_number, field_name, value in table_rows:
            if value.strip():
                continue
            row_label = field_name.strip() or f"第 {row_number} 行"
            fail(
                "DESCRIPTION.TABLE_REQUIRED_VALUE",
                description,
                f"Description 表格中“{row_label}”行的测试信息为空。",
            )
        return {}

    sections = _description_sections(description)
    has_hw_info = _notes_have_info(description, "hw")
    has_sw_info = _notes_have_info(description, "sw")
    for heading, rule_id in _DESCRIPTION_RULES:
        if heading == "notes" and has_hw_info and has_sw_info:
            continue
        if not sections.get(heading, "").strip():
            fail(rule_id, description, f"{heading.title()} 章节缺失或为空。")

    rate = sections.get("reproducibility rate", "").splitlines()
    rate_value = rate[0].strip() if rate else ""
    rate_note = re.fullmatch(
        r"(?P<rate>.+?)\s*(?:\([^()]+\)|（[^（）]+）)",
        rate_value,
    )
    if (
        rate_note
        and re.fullmatch(
            _TEXTUAL_OCCURRENCE_RATE,
            rate_note.group("rate").strip(),
        )
    ):
        rate_value = rate_note.group("rate").strip()
    if rate and not _valid_rate(rate_value):
        fail(
            "DESCRIPTION.RATE_FORMAT",
            description,
            f"Description 中的复现概率“{rate[0].strip()}”格式无效。",
        )
    for info_kind, rule_id, label in (
        ("hw", "DESCRIPTION.NOTES_HW", "硬件"),
        ("sw", "DESCRIPTION.NOTES_SW", "软件"),
    ):
        if not (has_hw_info if info_kind == "hw" else has_sw_info):
            marker = "HW info" if info_kind == "hw" else "SW info"
            fail(
                rule_id,
                description,
                f"Notes 缺少已填写的{label}信息“{marker}: ...”。",
            )
    return sections


def _second_description_table_rows(
    description: str,
) -> list[tuple[int, str, str]] | None:
    header = ("模块", "需要填写信息", "测试信息")
    normalized_header = tuple(_normalize_label(cell) for cell in header)
    lines = description.splitlines()
    for header_index, line in enumerate(lines):
        cells = tuple(
            _normalize_label(cell)
            for cell in re.split(r"\|+", line.strip().strip("|"))[:3]
        )
        if cells != normalized_header:
            continue
        rows: list[tuple[int, str, str]] = []
        for row_number, row_line in enumerate(lines[header_index + 1:], 1):
            row_text = row_line.strip()
            if not row_text.startswith("|") or not row_text.endswith("|"):
                continue
            cells = row_text[1:-1].split("|")
            if len(cells) < 3:
                continue
            rows.append((row_number, cells[1], cells[2]))
        return rows
    return None


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
    cleaned = cleaned.translate(str.maketrans("【】：；", "[]:;"))
    cleaned = re.sub(r"(?<=\])[*_]{1,3}(?=:)", "", cleaned)
    bracket = re.fullmatch(
        r"\[([^]]+)\]\s*(?:[:;]\s*[*_]{0,3}\s*(.*))?",
        cleaned,
    )
    if bracket:
        return (
            _normalize_label(bracket.group(1)),
            (bracket.group(2) or "").strip("*_ "),
        )
    labeled = re.fullmatch(r"([^:;]+?)\s*[:;]\s*[*_]{0,3}\s*(.*)", cleaned)
    if labeled:
        return _normalize_label(labeled.group(1)), labeled.group(2).strip("*_ ")
    standalone = _normalize_label(cleaned)
    return (standalone, "") if standalone else None


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().strip("*_").split()).casefold()


def _valid_rate(value: str) -> bool:
    text = value.strip().rstrip(".")
    if re.fullmatch(_TEXTUAL_OCCURRENCE_RATE, text):
        return True
    if re.fullmatch(r"(?:100|\d{1,2})(?:\.\d+)?%", text):
        return True
    fraction = re.fullmatch(r"(\d+)\s*/\s*(\d+)", text)
    return bool(
        fraction
        and int(fraction.group(2)) > 0
        and int(fraction.group(1)) <= int(fraction.group(2))
    )


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
