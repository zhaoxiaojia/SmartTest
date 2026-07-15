"""Portable Jira issue-format auditor and XLSX exporter."""

from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile

JIRA_CONFIG = {
    "base_url": "https://jira.amlogic.com",
    "username": "chao.li",
    "password": "Xiaojia#1994",
    "jql": "project = SH AND issuetype = Bug AND priority in (Highest, High) AND created >= 2026-06-01",
    "jira_url": "",
    "issue_keys": [],
    "output": "jira_format_audit.xlsx",
}

# Shared result for the audit and any future business processing in this run.
ISSUE_LIST: list[dict[str, Any]] = []

QA_REPORTER_NAMES = frozenset(
    {
        "Xiuyue Zhang",
        "Junjie Li",
        "Mao Ma",
        "Changwen Dai",
        "Xiangqun Li",
        "Leping Lei",
        "Jianfan Ai",
        "Jinbo Du",
        "Shaojun Chen",
        "Kai Ni",
        "Shuangxiao Hu",
        "Chunyan Liu",
        "Xinying Yang",
        "Bo Ren",
        "Zhangxian Chen",
        "Zhenhua Xiao",
        "Zanbo Huang",
        "Lingguo Bu",
        "Haolin Li",
        "Chenghua Liu",
        "Yongqi Liang",
        "Menghui Liu",
        "Jianhua Huang",
        "Maoguo Xie",
        "Cong Zhang",
        "Jie Xiong",
        "Jianhui Peng",
        "Ling Chen",
        "Zhewu Tao",
        "Meng Wang",
        "Binbin Gao",
        "Jiajia Mu",
        "Zhendong Zhou",
        "Yanyan Deng",
        "Xiaoli Peng",
        "Xing Fan",
        "Zhaoqun Wang",
        "Zijie Chen",
        "Bo Meng",
        "Yu Zhang",
        "Yonghua Wu",
        "Jian Zhong",
        "Yan Wu",
        "Ping Xiong",
        "Lingling Yu",
        "Pan Xu",
        "Chen Chen",
        "Dan Chen",
        "Chao Lu",
        "Chao Li",
        "Nannan Meng",
        "Kang Jiang",
        "Yanqing Tang",
        "Weiting Feng",
        "Taoqing Miao",
        "Chuanyang Hu",
        "Qianyi Liu",
        "Zhuhui Zhang",
        "Jinhuan Yi",
        "Yifeng Xu",
        "Shouneng Chou",
        "Mennan Hu",
        "Hanpeng Su",
        "Haobo Ren",
        "Meiling Zhu",
        "Xiaofeng Li",
        "Qin Zhang",
        "Xuejiao Li",
        "Mingdong Wang",
        "Zongwu Ma",
        "Yunzhu Zhang",
        "Zhijie Yang",
        "Tianwei Xie",
        "Bing Song",
        "Qiaowei Tian",
    }
)
_QA_REPORTER_NAME_KEYS = frozenset(name.casefold() for name in QA_REPORTER_NAMES)

ALLOWED_MODULES = [
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
]
DESCRIPTION_SECTIONS = [
    "Steps to reproduce",
    "Actual results",
    "Expected results",
    "Reproducibility rate",
    "Comparision",
    "Notes",
]
MANAGERS = frozenset({"chao.li"})
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
SUPPORTED_NORMATIVE_SECTIONS = {
    "summary",
    "component",
    "description",
    "label",
    "labels",
    "regression",
    "attachment",
}
EMBEDDED_RULES = {
    "sections": {
        "Summary": "[public Jira ID optional][customer English name][customer Bug ID optional][CHIP][system version][Bug module]: English problem description,probability.",
        "Component": "At least one Component is required and must use an allowed module.",
        "Description": "All required description sections must be present and populated.",
        "Labels": "Project custom labels are allowed; known labels may impose conditional rules.",
        "Regression": "Regression requires previous-normal and current-broken version evidence.",
        "Attachment": "Each attachment must be no larger than 10 MB.",
    },
    "allowed_modules": ALLOWED_MODULES,
    "label_tables": {"General": ["Regression"]},
    "unsupported_sections": [],
}

REPORT_RULE_TEXT = {
    "SPEC.UNSUPPORTED_SECTION": (
        "规范章节必须有对应的自动校验规则。",
        "该规范章节暂未被校验器支持。",
        "补充该章节的共享校验规则。",
    ),
    "SUMMARY.FORMAT": (
        "[客户英文名][CHIP][系统版本][Bug模块]: 英文问题描述,复现概率；可选增加公共 Jira ID 或客户 Bug ID。",
        "Summary 不符合规定的分组和概率格式。",
        "按标准格式重写 Summary。",
    ),
    "SUMMARY.CUSTOMER": (
        "Summary 必须填写客户英文名。",
        "客户名称为空。",
        "填写客户英文名或英文项目代号。",
    ),
    "SUMMARY.CHIP": ("Summary 必须填写 CHIP。", "CHIP 为空。", "填写大写 CHIP 名称。"),
    "SUMMARY.VERSION": (
        "Summary 必须填写系统版本。",
        "系统版本为空。",
        "填写明确的系统版本。",
    ),
    "SUMMARY.CUSTOMER_ENGLISH": (
        "客户名称必须使用英文名或英文项目代号。",
        "客户名称不是有效英文内容。",
        "改用客户英文名或英文项目代号。",
    ),
    "SUMMARY.CHIP_UPPERCASE": (
        "CHIP 必须使用大写字母。",
        "CHIP 未按要求大写。",
        "将 CHIP 改为大写。",
    ),
    "SUMMARY.MODULE": (
        "Bug 模块必须来自规范允许的模块列表。",
        "Bug 模块不在允许列表中。",
        "选择规范中已有的模块名称。",
    ),
    "SUMMARY.DESCRIPTION_ENGLISH": (
        "问题描述必须使用英文。",
        "问题描述不是有效英文内容。",
        "使用英文描述问题现象。",
    ),
    "SUMMARY.PROBABILITY": (
        "复现概率必须是百分比或分数，例如 50% 或 1/2。",
        "复现概率格式无效。",
        "改为百分比或分数。",
    ),
    "COMPONENT.REQUIRED": (
        "至少填写一个 Component。",
        "Component 为空。",
        "填写与问题对应的 Component。",
    ),
    "COMPONENT.ALLOWED": (
        "Component 必须来自规范允许的模块列表。",
        "Component 包含不支持的模块。",
        "选择规范中已有的模块名称。",
    ),
    "DESCRIPTION.STEPS_TO_REPRODUCE": (
        "Description 必须包含非空的 Steps to reproduce。",
        "复现步骤缺失或为空。",
        "补充可执行的复现步骤。",
    ),
    "DESCRIPTION.ACTUAL_RESULTS": (
        "Description 必须包含非空的 Actual results。",
        "实际结果缺失或为空。",
        "补充实际发生的结果。",
    ),
    "DESCRIPTION.EXPECTED_RESULTS": (
        "Description 必须包含非空的 Expected results。",
        "预期结果缺失或为空。",
        "补充预期结果。",
    ),
    "DESCRIPTION.REPRODUCIBILITY_RATE": (
        "Description 必须包含非空复现概率，格式为百分比或分数。",
        "复现概率缺失或为空。",
        "补充百分比或分数形式的复现概率。",
    ),
    "DESCRIPTION.COMPARISION": (
        "Description 必须包含非空的 Comparision。",
        "版本对比信息缺失或为空。",
        "补充版本对比信息。",
    ),
    "DESCRIPTION.NOTES": (
        "Description 必须包含非空的 Notes。",
        "备注缺失或为空。",
        "补充包含软硬件信息的备注。",
    ),
    "DESCRIPTION.STEPS_ORDERED": (
        "复现步骤必须从 1 开始连续编号，且每一步包含可执行动作。",
        "复现步骤编号不连续或内容为空。",
        "按顺序重写为完整可执行步骤。",
    ),
    "DESCRIPTION.RATE_FORMAT": (
        "复现概率必须是百分比或分数，例如 50% 或 1/2。",
        "Description 中的复现概率格式无效。",
        "改为百分比或分数。",
    ),
    "DESCRIPTION.NOTES_HW": (
        "Notes 必须包含“HW info: ...”。",
        "Notes 缺少硬件信息。",
        "补充 HW info。",
    ),
    "DESCRIPTION.NOTES_SW": (
        "Notes 必须包含“SW info: ...”。",
        "Notes 缺少软件信息。",
        "补充 SW info。",
    ),
    "REGRESSION.EVIDENCE": (
        "Regression 问题必须同时说明旧版本正常和当前版本异常。",
        "回归版本证据不完整。",
        "补充旧版本正常与当前版本异常的对照证据。",
    ),
    "ATTACHMENT.MAX_SIZE": (
        "单个附件不得超过 10 MB。",
        "附件大小超过 10 MB。",
        "压缩、拆分附件或改用链接。",
    ),
}
REPORT_DEFAULT_TEXT = (
    "请参照对应规范章节。",
    "当前内容不符合规范。",
    "按规范修正当前内容。",
)


def normalize_username(username: str | None) -> str:
    value = str(username or "").strip().lower()
    if "\\" in value:
        value = value.rsplit("\\", 1)[-1]
    return value.split("@", 1)[0]


def normalize_reporter_name(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def reporter_name_from_username(username: str | None) -> str:
    return " ".join(
        part.capitalize() for part in normalize_username(username).split(".") if part
    )


def is_manager(username: str | None, managers: Iterable[str] = MANAGERS) -> bool:
    return normalize_username(username) in {
        normalize_username(item) for item in managers
    }


def load_markdown_rules(path: str | os.PathLike[str]) -> dict[str, Any]:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Unable to read Markdown rules '{source}': {exc}") from exc
    rules = deepcopy(EMBEDDED_RULES)
    unsupported: list[str] = []
    for title, body in load_markdown_sections(text).items():
        normalized_title = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", title).strip()
        category = next(
            (
                name
                for name in SUPPORTED_NORMATIVE_SECTIONS
                if name in normalized_title.lower()
            ),
            "",
        )
        prose, tables = load_markdown_tables(body)
        if category and prose:
            rules["sections"][category.title()] = prose
        for table in tables:
            headers = table[0]
            module_column = _column_index(headers, "Summary 模块名", "Summary 模块名称")
            label_column = _column_index(headers, "Label")
            if module_column is not None:
                rules["allowed_modules"] = _table_column(table, module_column)
            if label_column is not None:
                rules["label_tables"][title] = _table_column(table, label_column)
        # Numbered examples, sources, templates, and explanatory subsections are supporting material.
        if (
            not category
            and not re.match(
                r"^(?:\d+\.)?\s*(?:完整.*示例|规范来源|标准格式|字段说明|填写说明|其他注意事项|基本规则)",
                normalized_title,
            )
            and _is_normative(body)
        ):
            unsupported.append(title)
    rules["unsupported_sections"] = unsupported
    return rules


def normalize_issue(
    issue: dict[str, Any], base_url: str | None = None
) -> dict[str, Any]:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else issue
    key = str(issue.get("key") or issue.get("keyId") or fields.get("key") or "")
    components = fields.get("components") or []
    url = str(issue.get("url") or issue.get("self") or "")
    reporter = fields.get("reporter")
    if isinstance(reporter, dict):
        reporter_username = normalize_username(
            reporter.get("name") or reporter.get("key") or reporter.get("accountId")
        )
        display_name = " ".join(str(reporter.get("displayName") or "").split())
        reporter_name = display_name or reporter_name_from_username(reporter_username)
        reporter_match_name = normalize_reporter_name(reporter_name)
    else:
        reporter_username = ""
        reporter_name = str(reporter or "").strip()
        reporter_match_name = ""
    if base_url and key:
        url = f"{base_url.rstrip('/')}/browse/{key}"
    return {
        "key": key,
        "url": url,
        "summary": str(fields.get("summary") or ""),
        "components": [
            str(item.get("name", "")) if isinstance(item, dict) else str(item)
            for item in components
        ],
        "description": _plain_text(fields.get("description")),
        "labels": [str(x) for x in fields.get("labels") or []],
        "attachments": [
            x
            for x in (fields.get("attachment") or fields.get("attachments") or [])
            if isinstance(x, dict)
        ],
        "reporter": reporter_name or "未知报告人",
        "reporter_username": reporter_username,
        "reporter_match_name": reporter_match_name,
    }


def validate_issue(
    issue: dict[str, Any],
    *,
    rules: dict[str, Any] | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    active, data, violations = (
        deepcopy(rules or EMBEDDED_RULES),
        normalize_issue(issue, base_url),
        [],
    )

    def fail(
        rule_id: str, section: str, field: str, value: Any, reason: str, guidance: str
    ) -> None:
        violations.append(
            {
                "rule_id": rule_id,
                "spec_section": section,
                "spec_text": active.get("sections", {}).get(
                    section, EMBEDDED_RULES["sections"].get(section, "")
                ),
                "jira_field": field,
                "jira_value": _report_value(value),
                "failure_reason": reason,
                "correction_guidance": guidance,
            }
        )

    for title in active.get("unsupported_sections", []):
        fail(
            "SPEC.UNSUPPORTED_SECTION",
            title,
            "Specification",
            title,
            "The Markdown contains an unsupported normative category.",
            "Add a validator for this category.",
        )

    summary = re.fullmatch(
        r"((?:\[[^\]\r\n]+\]){4,6}):\s*(.+),\s*([^,]+)\.?", data["summary"]
    )
    if not summary:
        fail(
            "SUMMARY.FORMAT",
            "Summary",
            "Summary",
            data["summary"],
            "Summary does not match the required 4-6 bracket groups and final probability.",
            "Use [customer][CHIP][version][module]: English description,probability; optional public/customer Bug IDs may be added.",
        )
    else:
        groups = re.findall(r"\[([^\]]+)\]", summary.group(1))
        customer, chip, version, module = groups[-4:]
        description, probability = summary.group(2).strip(), summary.group(3).strip()
        for rule_id, value, reason in (
            ("SUMMARY.CUSTOMER", customer, "Customer English name is required."),
            ("SUMMARY.CHIP", chip, "CHIP is required."),
            ("SUMMARY.VERSION", version, "System version is required."),
        ):
            if not value:
                fail(
                    rule_id,
                    "Summary",
                    "Summary",
                    value,
                    reason,
                    "Populate the cited bracket group.",
                )
        if not re.search(r"[A-Za-z]", customer) or re.search(
            r"[\u4e00-\u9fff]", customer
        ):
            fail(
                "SUMMARY.CUSTOMER_ENGLISH",
                "Summary",
                "Summary",
                customer,
                f"Customer name '{customer}' is not an English name.",
                "Use the customer's English name or English project code.",
            )
        if chip != chip.upper() or not re.search(r"[A-Z]", chip):
            fail(
                "SUMMARY.CHIP_UPPERCASE",
                "Summary",
                "Summary",
                chip,
                f"CHIP '{chip}' is not uppercase.",
                "Write CHIP in uppercase.",
            )
        if module not in active["allowed_modules"]:
            fail(
                "SUMMARY.MODULE",
                "Summary",
                "Summary",
                module,
                f"Module '{module}' is not allowed.",
                f"Use one of: {', '.join(active['allowed_modules'])}.",
            )
        if not re.search(r"[A-Za-z]", description) or re.search(
            r"[\u4e00-\u9fff]", description
        ):
            fail(
                "SUMMARY.DESCRIPTION_ENGLISH",
                "Summary",
                "Summary",
                description,
                f"Description '{description}' is not English text.",
                "Use an English problem description.",
            )
        if not _valid_rate(probability):
            fail(
                "SUMMARY.PROBABILITY",
                "Summary",
                "Summary",
                probability,
                f"Probability '{probability}' is invalid.",
                "Use a percentage or fraction such as 50% or 1/2.",
            )

    if not data["components"]:
        fail(
            "COMPONENT.REQUIRED",
            "Component",
            "Component",
            data["components"],
            "Component is required.",
            "Set at least one Component.",
        )
    elif any(x not in active["allowed_modules"] for x in data["components"]):
        fail(
            "COMPONENT.ALLOWED",
            "Component",
            "Component",
            data["components"],
            "Component contains an unsupported module.",
            "Use an allowed module.",
        )

    sections = _description_sections(data["description"])
    for required in DESCRIPTION_SECTIONS:
        if not sections.get(required.lower(), "").strip():
            fail(
                f"DESCRIPTION.{required.upper().replace(' ', '_')}",
                "Description",
                "Description",
                data["description"],
                f"Required section '{required}' is missing or empty.",
                f"Add a populated '{required}' section.",
            )
    steps = sections.get("steps to reproduce", "")
    numbered = [
        (int(n), text.strip())
        for n, text in re.findall(r"(?m)^\s*(\d+)[.)]\s*(\S.*)$", steps)
    ]
    if steps and (
        not numbered
        or [n for n, _ in numbered] != list(range(1, len(numbered) + 1))
        or any(not text.strip(" ;.") for _, text in numbered)
    ):
        fail(
            "DESCRIPTION.STEPS_ORDERED",
            "Description",
            "Description.Steps to reproduce",
            steps,
            "Steps are not ordered, non-empty executable numbered steps.",
            "Use consecutive steps starting at 1, each with an executable action.",
        )
    rate = next(iter(sections.get("reproducibility rate", "").splitlines()), "").strip()
    if rate and not _valid_rate(rate):
        fail(
            "DESCRIPTION.RATE_FORMAT",
            "Description",
            "Description.Reproducibility rate",
            rate,
            f"Rate '{rate}' is invalid.",
            "Use a percentage or fraction.",
        )
    notes = sections.get("notes", "")
    for marker in ("HW info", "SW info"):
        if not re.search(rf"(?im)^\s*{marker}\s*:\s*\S", notes):
            fail(
                f"DESCRIPTION.NOTES_{marker[:2].upper()}",
                "Description",
                "Description.Notes",
                notes,
                f"Notes is missing populated {marker}.",
                f"Add '{marker}: ...'.",
            )
    if any(x.lower() == "regression" for x in data["labels"]):
        comparison = sections.get("comparision", "")
        previous = re.search(
            r"(?i)(?:previous|prior|older|baseline|old|last)\s+(?:normal\s+)?(?:build|version)|(?:build|version)\s*[\w.-]+.*(?:normal|pass|work)",
            comparison,
        )
        current = re.search(
            r"(?i)(?:current|new|broken|failing)\s+(?:build|version)|(?:build|version)\s*[\w.-]+.*(?:broken|fail|issue)",
            comparison,
        )
        if not previous or not current:
            fail(
                "REGRESSION.EVIDENCE",
                "Regression",
                "Description.Comparision",
                comparison,
                f"Regression evidence is incomplete: '{comparison}'.",
                "Cite the previous-normal version and current-broken version.",
            )
    for attachment in data["attachments"]:
        size = attachment.get("size", 0)
        if isinstance(size, (int, float)) and size > MAX_ATTACHMENT_BYTES:
            fail(
                "ATTACHMENT.MAX_SIZE",
                "Attachment",
                "Attachment",
                attachment,
                f"Attachment exceeds 10 MB ({int(size)} bytes).",
                "Compress, split, or link it.",
            )
    return {
        "key": data["key"],
        "url": data["url"],
        "reporter": data["reporter"],
        "reporter_username": data["reporter_username"],
        "reporter_match_name": data["reporter_match_name"],
        "overall_result": "FAIL" if violations else "PASS",
        "violations": violations,
    }


def validate_issues(
    issues: Iterable[dict[str, Any]], **kwargs: Any
) -> list[dict[str, Any]]:
    return [validate_issue(issue, **kwargs) for issue in issues]


def export_xlsx(
    results: Iterable[dict[str, Any]],
    output: str | os.PathLike[str],
    *,
    jql: str = "",
    generated_at: str | None = None,
) -> Path:
    rows = list(results)
    passed = sum(row["overall_result"] == "PASS" for row in rows)
    failed_by_reporter: dict[str, set[str]] = {}
    for row in rows:
        if row["overall_result"] == "FAIL":
            reporter = str(row.get("reporter") or "未知报告人")
            failed_by_reporter.setdefault(reporter, set()).add(str(row["key"]))
    summary = [
        ["指标", "值"],
        ["生成时间", generated_at or datetime.now(timezone.utc).isoformat()],
        ["JQL 查询条件", jql],
        ["问题总数", len(rows)],
        ["通过 Jira 数", passed],
        ["不通过 Jira 数", len(rows) - passed],
        ["通过率", f"{(passed / len(rows) * 100) if rows else 0:.2f}%"],
        [],
        ["报告人", "违规 Jira 数量", "违规 Jira 号"],
    ]
    summary.extend(
        [reporter, len(keys), "、".join(sorted(keys))]
        for reporter, keys in sorted(failed_by_reporter.items())
    )
    headers = [
        "Issue Key",
        "Issue URL",
        "检查结果",
        "规则编号",
        "规范章节",
        "规范要求/标准格式",
        "Jira 字段",
        "当前 Jira 内容",
        "失败原因",
        "修改建议",
    ]
    details = [headers] + [
        [
            result["key"],
            result["url"],
            "符合" if result["overall_result"] == "PASS" else "不符合",
            item["rule_id"],
            item["spec_section"],
            report_text[0],
            item["jira_field"],
            item["jira_value"],
            report_text[1],
            report_text[2],
        ]
        for result in rows
        for item in result["violations"]
        for report_text in [REPORT_RULE_TEXT.get(item["rule_id"], REPORT_DEFAULT_TEXT)]
    ]
    destination = Path(output)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
            )
            archive.writestr(
                "_rels/.rels",
                '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
            )
            archive.writestr(
                "xl/workbook.xml",
                '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="汇总" sheetId="1" r:id="rId1"/><sheet name="违规明细" sheetId="2" r:id="rId2"/></sheets></workbook>',
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
            )
            archive.writestr(
                "xl/styles.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                _worksheet_xml(summary, [28, 18, 85], header_rows={1, 9}),
            )
            archive.writestr(
                "xl/worksheets/sheet2.xml",
                _worksheet_xml(
                    details,
                    [14, 38, 10, 34, 18, 55, 22, 65, 38, 38],
                    auto_filter=True,
                ),
            )
    except OSError as exc:
        raise OSError(f"Unable to write XLSX report '{destination}': {exc}") from exc
    return destination


def fetch_jira_issues(
    base_url: str, jql: str, username: str, password: str, *, page_size: int = 100
) -> list[dict[str, Any]]:
    issues, start_at = [], 0
    while True:
        query = urlencode(
            {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size,
                "fields": "summary,components,description,labels,attachment,reporter",
            }
        )
        request = Request(
            f"{base_url.rstrip('/')}/rest/api/2/search?{query}",
            headers={
                "Accept": "application/json",
                "Authorization": _authorization(username, password),
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Jira request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Jira request failed: {exc.reason}") from exc
        page = payload.get("issues") or []
        issues.extend(page)
        start_at += len(page)
        if not page or start_at >= int(payload.get("total", start_at)):
            return issues


def _authorization(username: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()


def _filter_jql(base_url: str, filter_id: str, username: str, password: str) -> str:
    request = Request(
        f"{base_url.rstrip('/')}/rest/api/2/filter/{filter_id}",
        headers={
            "Accept": "application/json",
            "Authorization": _authorization(username, password),
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Jira filter request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Jira filter request failed: {exc.reason}") from exc
    jql = str(payload.get("jql") or "").strip()
    if not jql:
        raise ValueError(f"Jira filter {filter_id} did not provide JQL")
    return jql


def resolve_jql(config: dict[str, Any]) -> str:
    keys = [
        str(key).strip().upper()
        for key in config.get("issue_keys", [])
        if str(key).strip()
    ]
    if keys:
        invalid = [key for key in keys if not re.fullmatch(r"[A-Z][A-Z0-9_]*-\d+", key)]
        if invalid:
            raise ValueError(f"Invalid Jira issue key: {invalid[0]}")
        return f"key in ({', '.join(keys)})"

    jira_url = str(config.get("jira_url") or "").strip()
    if jira_url:
        parsed = urlparse(jira_url)
        browse = re.fullmatch(r"/browse/([A-Za-z][A-Za-z0-9_]*-\d+)/?", parsed.path)
        if browse:
            return f'key = "{browse.group(1).upper()}"'
        query = parse_qs(parsed.query)
        if query.get("jql", [""])[0].strip():
            return query["jql"][0].strip()
        filter_id = query.get("filter", [""])[0].strip()
        if filter_id:
            if not filter_id.isdigit():
                raise ValueError(f"Invalid Jira filter id: {filter_id}")
            return _filter_jql(
                str(config.get("base_url") or ""),
                filter_id,
                str(config.get("username") or ""),
                str(config.get("password") or ""),
            )
        raise ValueError("Jira URL must contain /browse/ISSUE-KEY, jql, or filter")

    jql = str(config.get("jql") or "").strip()
    if jql:
        return jql
    raise ValueError("Configure issue_keys, jira_url, or jql in JIRA_CONFIG")


def run(config: dict[str, Any]) -> int:
    base_url = str(config.get("base_url") or "").strip()
    username = str(config.get("username") or "").strip()
    password = str(config.get("password") or "")
    output = str(config.get("output") or "").strip()
    if not base_url or not username or not password or not output:
        raise ValueError(
            "JIRA_CONFIG requires base_url, username, password, and output"
        )
    jql = resolve_jql(config)
    fetched = fetch_jira_issues(base_url, jql, username, password)
    ISSUE_LIST[:] = [
        issue
        for issue in fetched
        if normalize_issue(issue)["reporter_match_name"] in _QA_REPORTER_NAME_KEYS
    ]
    results = validate_issues(
        ISSUE_LIST, rules=deepcopy(EMBEDDED_RULES), base_url=base_url
    )
    export_xlsx(results, output, jql=jql)
    return 0


def load_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1).strip()
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return {title: "\n".join(lines).strip() for title, lines in sections.items()}


def load_markdown_tables(body: str) -> tuple[str, list[list[list[str]]]]:
    tables, table_lines, prose = [], [], []
    for line in [*body.splitlines(), ""]:
        if line.strip().startswith("|") and line.strip().endswith("|"):
            table_lines.append(line)
        else:
            if table_lines:
                rows = [
                    [cell.strip() for cell in row.strip().strip("|").split("|")]
                    for row in table_lines
                ]
                if len(rows) >= 2:
                    tables.append(rows)
                table_lines = []
            if line:
                prose.append(line)
    return "\n".join(prose).strip(), tables


def _column_index(headers: list[str], *names: str) -> int | None:
    return next((headers.index(name) for name in names if name in headers), None)


def _table_column(table: list[list[str]], index: int) -> list[str]:
    return [row[index] for row in table[2:] if len(row) > index and row[index]]


def _is_normative(body: str) -> bool:
    return bool(
        re.search(
            r"(?i)\b(must|required|shall|should|need|only|not allowed)\b|必须|需要|不能|不得",
            body,
        )
    )


def _plain_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return (
            str(value.get("text") or "")
            if value.get("type") == "text"
            else "\n".join(_plain_text(x) for x in value.get("content", []) if x)
        )
    if isinstance(value, list):
        return "\n".join(_plain_text(x) for x in value)
    return str(value or "")


def _description_sections(description: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    aliases = {name.lower(): name.lower() for name in DESCRIPTION_SECTIONS}
    for line in description.splitlines():
        cleaned = re.sub(r"^\s*#+\s*", "", line).strip()
        bracket = re.fullmatch(r"\[([^]]+)\]\s*:\s*", cleaned)
        key = (bracket.group(1) if bracket else cleaned.rstrip(":")).strip().lower()
        if key in aliases:
            current = aliases[key]
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


def _report_value(value: Any) -> str:
    return (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, sort_keys=True)
    )


def _worksheet_xml(
    rows: list[list[Any]],
    widths: list[int],
    *,
    auto_filter: bool = False,
    header_rows: set[int] | None = None,
) -> str:
    styled_headers = header_rows or {1}
    xml_rows = []
    for row_number, row in enumerate(rows, 1):
        cells = []
        for column, value in enumerate(row, 1):
            reference = f"{_column_name(column)}{row_number}"
            style = 1 if row_number in styled_headers else 2
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{reference}" s="{style}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{reference}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'
                )
        content_length = max((len(str(value)) for value in row), default=0)
        height = (
            30
            if row_number in styled_headers
            else min(90, max(18, 15 * max(1, content_length // 80 + 1)))
        )
        xml_rows.append(
            f'<row r="{row_number}" ht="{height}" customHeight="1">{"".join(cells)}</row>'
        )
    columns = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, 1)
    )
    filter_xml = (
        f'<autoFilter ref="A1:{_column_name(len(widths))}{len(rows)}"/>'
        if auto_filter
        else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>'
        + columns
        + "</cols><sheetData>"
        + "".join(xml_rows)
        + "</sheetData>"
        + filter_xml
        + "</worksheet>"
    )


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def main() -> int:
    try:
        return run(JIRA_CONFIG)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
