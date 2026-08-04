from __future__ import annotations
from datetime import timedelta
import re

from .discovery import canonical_page_kind
from .html import html_tables, links, table_field_html, text
from .models import AuditFinding, AuditStatus

REQUIRED = ("status", "test_information", "test_plan", "environment", "report_store")
DISPLAY = {
    "status": "Project Status Report",
    "test_information": "Test Information",
    "test_plan": "Test Plan",
    "environment": "Test Environment Setup and Precautions",
    "experience": "Summary of Experience and Typical Cases",
    "report_store": "Test Report Store",
}
PLACEHOLDER = re.compile(r"\bX{3,}\b|XXXX[.\-/]XX[.\-/]XX|\b(?:TBD|TODO)\b", re.I)
NA = re.compile(r"^\s*(?:none|n/?a|无|暂无|没有)\s*[。.]*\s*$", re.I)
DATE = re.compile(r"\b(20\d\d[-./]\d{1,2}[-./]\d{1,2})\b")
RULE_GUIDANCE = {
    "content.placeholder": "Replace template placeholders with current project information.",
    "status.highlights": "Add a traceable Highlights link or explicitly enter N/A.",
    "status.impact": "Add a traceable Impact issues link or explicitly enter N/A.",
    "test.failures": "Add a failure summary and a traceable Jira issue or filter link.",
    "test.blocking_tasks": "Complete the overdue blocking task or update its due date and status.",
    "test.important_tasks": "Complete the overdue important task or update its due date and status.",
    "plan.weekly": "Add the current week's test work, expected result, and deliverable.",
    "environment.complete": "Document setup steps, equipment/software, configuration, and log collection.",
    "report.weekly": "Archive a report attachment during the audit window.",
}


class StaticAuditService:
    def audit(self, project, pages, period, attachments=None, unreadable=None):
        pages = _canonical_pages(pages)
        attachments = attachments or {}
        unreadable = set(unreadable or ())
        findings = []

        def add(kind, rule, status, reason, guidance="", explanation=""):
            page = pages.get(kind)
            if not guidance:
                guidance = (
                    f"Add or restore the required {DISPLAY[kind]} page."
                    if rule.startswith("required.")
                    else RULE_GUIDANCE.get(rule, "")
                )
            findings.append(AuditFinding(
                project.project_id, page.title if page else DISPLAY[kind], rule, status,
                reason, guidance, page_url=page.url if page else project.home_url,
                explanation=explanation or reason,
            ))

        for kind in REQUIRED:
            if kind in pages:
                status, reason = AuditStatus.PASSED, "Page is available."
            elif kind in unreadable:
                status, reason = AuditStatus.UNKNOWN, "Required page exists but could not be read."
            else:
                status, reason = AuditStatus.FAILED, "Required page is missing."
            add(kind, f"required.{kind}", status, reason)

        for kind, page in pages.items():
            if kind != "status" and PLACEHOLDER.search(text(page.body)):
                add(kind, "content.placeholder", AuditStatus.FAILED, "Template placeholder remains.")

        status_page = pages.get("status")
        if status_page:
            for heading, rule in (("Highlights", "status.highlights"), ("Impact issues", "status.impact")):
                rendered = status_page.view_body or status_page.body
                section = (
                    _section(rendered, (heading,), ("Highlights", "Impact issues", "Milestone"))
                    or table_field_html(rendered, heading)
                    or table_field_html(status_page.body, heading)
                )
                plain = text(section)
                valid = bool(links(section)) or bool(NA.match(plain))
                add("status", rule, AuditStatus.PASSED if valid else AuditStatus.FAILED,
                    f"{heading} has a traceable link or explicit N/A." if valid else f"{heading} requires a link or explicit N/A.")

        info = pages.get("test_information")
        if info:
            plain = text(info.body)
            colon_values = {key.casefold(): float(value) for key, value in re.findall(
                r"(Pass Rate|Pass|Fail|Pending|Total)\s*:\s*(\d+(?:\.\d+)?)%?", plain, re.I)}
            metric_rows = _metric_rows(info.body, info.view_body or info.body)
            values = colon_values
            invalid_rows = [row for row in metric_rows if not row["valid"]]
            valid = _colon_metrics_valid(values) if values else bool(metric_rows) and not invalid_rows
            metric_reason = (
                "Test metrics are consistent."
                if valid else
                _metric_issue(invalid_rows[0])
                if invalid_rows else
                "Test metric rows are missing."
            )
            add("test_information", "test.metrics", AuditStatus.PASSED if valid else AuditStatus.FAILED,
                metric_reason, "Correct the named row totals or pass rate to match the executed-test denominator.",
                metric_reason)
            fail_count = values.get("fail", 0) if values else sum(row["fail"] for row in metric_rows)
            if fail_count > 0:
                failure = _section(info.view_body or info.body, ("Fail", "Failure", "Failed"), ("Blocking", "Task Arrangement"))
                table_failures = [row for row in metric_rows if row["fail"] > 0]
                traceable = (
                    bool(links(failure)) and len(text(failure)) > 10
                ) or bool(table_failures) and all(
                    len(text(row["comments_html"])) > 10 and bool(links(row["link_html"]))
                    for row in table_failures
                )
                add("test_information", "test.failures", AuditStatus.PASSED if traceable else AuditStatus.FAILED,
                    "Failures include a summary and traceable link." if traceable else "Failures require a summary and traceable issue link.")
            for heading, rule in (
                ("Blocking QA Testing Items", "test.blocking_tasks"),
                ("Task Arrangement of Important Test", "test.important_tasks"),
            ):
                section = _section(info.body, (heading,), ())
                stale = any(
                    _task_overdue(task, period.end.date().isoformat())
                    for task in re.findall(r"<ac:task\b.*?</ac:task>", section, re.I | re.S)
                )
                if stale:
                    add("test_information", rule, AuditStatus.FAILED, f"{heading} contains an overdue incomplete task.")

        plan = pages.get("test_plan")
        if plan:
            plain = text(plan.body)
            weekly = bool(re.search(r"\b(?:week\s*\d+|w\d+|20\d\d[-./]\d{1,2}[-./]\d{1,2}\s*(?:to|[-~至])\s*20\d\d[-./]\d{1,2}[-./]\d{1,2})\b", plain, re.I))
            actionable = weekly and len(plain) >= 30 and bool(re.search(r"\b(?:test|verify|validation|测试|验证|交付)\b", plain, re.I))
            add("test_plan", "plan.weekly", AuditStatus.PASSED if actionable else AuditStatus.FAILED,
                "Test plan is weekly and actionable." if actionable else "Test plan must include weekly test work and deliverables.")

        environment = pages.get("environment")
        if environment:
            plain = text(environment.body)
            groups = (
                r"\b(?:step|setup|install|步骤|搭建|安装)\b",
                r"\b(?:device|equipment|software|设备|软件)\b",
                r"\b(?:config(?:ure|uration)?|setting|配置)\b",
                r"\b(?:log|日志|adb|dmesg)\b",
            )
            complete = all(re.search(pattern, plain, re.I) for pattern in groups)
            add("environment", "environment.complete", AuditStatus.PASSED if complete else AuditStatus.FAILED,
                "Environment setup and log guidance are complete." if complete else "Environment page must cover steps, equipment/software, configuration, and logs.")

        report = pages.get("report_store")
        if report:
            items = attachments.get("report_store", attachments.get(report.title, []))
            recent_attachment = any(period.contains(item.created_at) for item in items)
            add("report_store", "report.weekly", AuditStatus.PASSED if recent_attachment else AuditStatus.FAILED,
                "A report attachment was archived in the audit week." if recent_attachment
                else "No report attachment was archived in the audit week.",
                explanation=(
                    f"The audit window is {period.start:%Y-%m-%d} through "
                    f"{(period.end - timedelta(days=1)):%Y-%m-%d}; "
                    "no new report attachment was archived in that window."
                    if not recent_attachment else
                    "A report attachment was archived in the audit week."
                ))

        add("experience", "experience.development", AuditStatus.NOT_APPLICABLE,
            "Checked when the project is completed.")
        return findings


def _canonical_pages(pages):
    result = {}
    for key, page in pages.items():
        kind = key if key in DISPLAY else canonical_page_kind(page.title) or canonical_page_kind(key)
        if kind:
            result[kind] = page
    return result

def _section(body, starts, stops):
    start_pattern = "|".join(re.escape(item) for item in starts)
    stop_pattern = "|".join(re.escape(item) for item in stops if item not in starts)
    match = re.search(rf"<h[1-6]\b[^>]*>.*?(?:{start_pattern}).*?</h[1-6]>(.*)", body or "", re.I | re.S)
    if not match:
        return ""
    value = match.group(1)
    if stop_pattern:
        value = re.split(rf"<h[1-6]\b[^>]*>.*?(?:{stop_pattern}).*?</h[1-6]>", value, maxsplit=1, flags=re.I | re.S)[0]
    return value

def _iso(value):
    return value.replace(".", "-").replace("/", "-")

def _task_overdue(task, deadline):
    due = DATE.search(text(task))
    incomplete = bool(re.search(r"<ac:task-status>\s*incomplete\s*</ac:task-status>", task, re.I))
    return bool(incomplete and due and _iso(due.group(1)) <= deadline)

def _colon_metrics_valid(values):
    return bool(values) and (
        values.get("pass", 0) + values.get("fail", 0) + values.get("pending", 0)
        == values.get("total", -1)
        and (
            not values.get("total")
            or round(values.get("pass", 0) / values["total"] * 100, 2)
            == values.get("pass rate")
        )
    )

def _metric_rows(storage, rendered):
    storage_tables = html_tables(storage)
    rendered_tables = html_tables(rendered)
    results = []
    required = {"test item", "pass", "fail", "total", "pass rate"}
    for table_index, table in enumerate(storage_tables):
        if len(table) < 2:
            continue
        header_index = next((
            index for index, cells in enumerate(table)
            if required.issubset({_metric_header(cell) for cell in cells})
        ), None)
        if header_index is None:
            continue
        headers = [_metric_header(cell) for cell in table[header_index]]
        if not required.issubset(headers):
            continue
        rendered_table = rendered_tables[table_index] if table_index < len(rendered_tables) else table
        for row_index, cells in enumerate(table[header_index + 1:], header_index + 1):
            if len(cells) < len(headers):
                continue
            rendered_cells = rendered_table[row_index] if row_index < len(rendered_table) else cells
            by_name = dict(zip(headers, cells))
            rendered_by_name = dict(zip(headers, rendered_cells))
            raw_metrics = [
                text(by_name.get(name, "")).strip()
                for name in ("pass", "fail", "n/a", "not test", "pending", "total", "pass rate")
            ]
            if not any(re.fullmatch(r"\d+(?:\.\d+)?%?", value) for value in raw_metrics):
                continue
            try:
                passed = float(text(by_name["pass"]))
                failed = float(text(by_name["fail"]))
                na = float(text(by_name.get("n/a", "0")) or 0)
                not_test = float(text(by_name.get("not test", "0")) or 0)
                pending = float(text(by_name.get("pending", "0")) or 0)
                total = float(text(by_name["total"]))
                rate = float(text(by_name["pass rate"]).rstrip("%"))
            except ValueError:
                results.append({"valid": False, "name": text(by_name.get("test item", "")),
                                "fail": 0, "comments_html": "", "link_html": ""})
                continue
            # Policy: Total includes every disposition. Pass Rate uses executed
            # tests only (Pass + Fail); N/A, Not Test and Pending are excluded.
            executed = passed + failed
            expected_rate = round(passed / executed * 100, 2) if executed else 0
            results.append({
                "valid": passed + failed + na + not_test + pending == total
                         and abs(expected_rate - rate) <= 0.01,
                "name": text(by_name["test item"]).strip(),
                "pass": passed,
                "fail": failed,
                "n/a": na,
                "not test": not_test,
                "pending": pending,
                "total": total,
                "rate": rate,
                "expected_rate": expected_rate,
                "comments_html": rendered_by_name.get("comments", ""),
                "link_html": (
                    rendered_by_name.get("comments", "")
                    + rendered_by_name.get("results", "")
                ),
            })
    return results


def _metric_header(cell):
    value = text(cell).strip().casefold()
    for name in (
        "test item", "pass rate", "not test", "pending", "total",
        "pass", "fail", "n/a", "results", "comments",
    ):
        if value.startswith(name):
            return name
    return value


def _metric_issue(row):
    if "expected_rate" not in row:
        return f"Test metric row {row.get('name') or '<unnamed>'} contains non-numeric values."
    return (
        f"Test metric row {row['name']}: pass={row['pass']:g}, fail={row['fail']:g}, "
        f"N/A={row['n/a']:g}, not test={row['not test']:g}, pending={row['pending']:g}, "
        f"total={row['total']:g}, actual pass rate={row['rate']:.2f}%, "
        f"expected pass rate={row['expected_rate']:.2f}% using Pass / (Pass + Fail)."
    )
