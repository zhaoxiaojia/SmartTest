from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tool.common.project_weekly_audit.discovery import (
    canonical_page_kind,
    discover_project_pages,
)
from tool.common.project_weekly_audit.models import AuditStatus, ProjectCandidate
from tool.common.project_weekly_audit.period import (
    current_reporting_window, previous_business_week, scheduled_reporting_window,
)
from tool.common.project_weekly_audit.rules import StaticAuditService
from support.confluence_integration.models import ConfluenceAttachment, ConfluencePage

TZ = ZoneInfo("Asia/Shanghai")


def test_previous_business_week_excludes_current_monday():
    period = previous_business_week(datetime(2026, 7, 29, 15, tzinfo=TZ))
    assert period.start == datetime(2026, 7, 20, tzinfo=TZ)
    assert period.end == datetime(2026, 7, 27, tzinfo=TZ)
    assert period.contains(datetime(2026, 7, 26, 23, tzinfo=TZ))
    assert not period.contains(datetime(2026, 7, 27, 0, tzinfo=TZ))


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 7, 29, 15, tzinfo=TZ),  # Wednesday
        datetime(2026, 7, 31, 9, tzinfo=TZ),   # Friday
        datetime(2026, 8, 1, 12, tzinfo=TZ),   # Saturday
        datetime(2026, 8, 2, 23, tzinfo=TZ),   # Sunday
    ],
)
def test_current_reporting_window_is_monday_to_manual_trigger(now):
    period = current_reporting_window(now)
    assert period.start == datetime(2026, 7, 27, tzinfo=TZ)
    assert period.end == now
    assert period.contains(datetime(2026, 7, 27, 0, tzinfo=TZ))
    assert not period.contains(now)


def test_scheduled_reporting_window_is_monday_to_friday():
    period = scheduled_reporting_window(datetime(2026, 7, 31, 0, 5, tzinfo=TZ))
    assert period.start == datetime(2026, 7, 27, tzinfo=TZ)
    assert period.end == datetime(2026, 7, 31, tzinfo=TZ)

@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("1.★Muffin314-Project Status Report", "status"),
        ("3. Muffin314-Test Information", "test_information"),
        ("Muffin314-Test Plan", "test_plan"),
        ("Test Environment Setup and Precautions", "environment"),
        ("Summary of Experience and Typical Cases", "experience"),
        ("Muffin314-Test Report Store", "report_store"),
    ],
)
def test_real_prefixed_titles_are_classified_deterministically(title, kind):
    assert canonical_page_kind(title) == kind


class PageGraphClient:
    def __init__(self, duplicate=False):
        rows = [
            ("671973853", "1.★Muffin314-Project Status Report"),
            ("671973854", "3. Muffin314-Test Information"),
            ("671973855", "Muffin314-Test Plan"),
            ("671973856", "Test Environment Setup and Precautions"),
            ("671973857", "Summary of Experience and Typical Cases"),
            ("671973858", "Muffin314-Test Report Store"),
        ]
        if duplicate:
            rows.append(("671973859", "Backup Test Plan"))
        self.home = ConfluencePage(
            "671973851", "Muffin314 Project Home", "https://c/pages/671973851",
        )
        self.pages = {
            page_id: ConfluencePage(
                page_id, title, f"https://c/pages/{page_id}", "",
            )
            for page_id, title in rows
        }
    def get_page_by_url(self, url):
        assert "671973851" in url
        return self.home
    def get_page_children(self, page_id):
        return list(self.pages.values()) if page_id == self.home.id else []


def test_page_graph_loads_targets_from_project_children():
    project = ProjectCandidate("671973853", "M314", "Muffin314", "https://c/pages/671973853",
                               "https://c/pages/viewpage.action?pageId=671973851")
    pages = discover_project_pages(PageGraphClient(), project)
    assert set(pages) == {"status", "test_information", "test_plan", "environment", "experience", "report_store"}
    assert pages["status"].id == "671973853"


def test_page_graph_ignores_descriptive_pages_that_only_end_in_test_plan_words():
    project = ProjectCandidate("671973853", "M314", "Muffin314", "https://c/pages/671973853",
                               "https://c/pages/viewpage.action?pageId=671973851")
    pages, errors = discover_project_pages(
        PageGraphClient(duplicate=True), project, return_errors=True,
    )
    assert pages["test_plan"].id == "671973855"
    assert "test_plan" not in errors


def test_wifi_test_plan_is_not_the_project_main_test_plan():
    assert canonical_page_kind("Turtle121-WiFi Test Plan") is None


def test_static_rules_cover_missing_pages_placeholders_overdue_math_reports_and_na():
    project = ProjectCandidate("1", "M314", "Muffin314", "https://c/1", "https://c/display/M314")
    period = previous_business_week(datetime(2026, 7, 29, tzinfo=TZ))
    pages = {
        "Project Status Report": ConfluencePage("1", "Project Status Report", "https://c/1",
            "<h2>Status Summary</h2><p>XXX</p><h2>QA</h2>"
            '<ac:task><ac:task-status>incomplete</ac:task-status><ac:task-body>QA due 2026-07-20</ac:task-body></ac:task>'),
        "Test Information": ConfluencePage("2", "Test Information", "https://c/2",
            "<p>Pass: 8 Fail: 1 Pending: 0 Total: 8 Pass Rate: 100%</p>"),
        "Summary of Experience and Typical Cases": ConfluencePage("3", "Summary of Experience and Typical Cases", "https://c/3", ""),
        "Test Report Store": ConfluencePage("4", "Test Report Store", "https://c/4", ""),
    }
    attachments = {"Test Report Store": [ConfluenceAttachment("a", "report.xlsx", "https://c/a",
        created_at=datetime(2026, 7, 10, tzinfo=TZ))]}
    findings = StaticAuditService().audit(project, pages, period, attachments)
    by_rule = {f.rule_id: f for f in findings}
    assert by_rule["required.test_plan"].status is AuditStatus.FAILED
    assert by_rule["test.metrics"].status is AuditStatus.FAILED
    assert by_rule["report.weekly"].status is AuditStatus.FAILED
    assert "required Test Plan" in by_rule["required.test_plan"].guidance
    assert "report attachment" in by_rule["report.weekly"].guidance
    assert all(
        finding.guidance != "Update the referenced page to resolve this finding, then rerun the audit."
        for finding in findings
    )
    assert by_rule["experience.development"].status is AuditStatus.NOT_APPLICABLE


def test_confirmed_static_rules_pass_for_complete_real_shaped_pages():
    project = ProjectCandidate("1", "M314", "Muffin314", "https://c/1", "https://c/home")
    period = previous_business_week(datetime(2026, 7, 29, tzinfo=TZ))
    task = ("<ac:task><ac:task-status>complete</ac:task-status>"
            "<ac:task-body>QA regression due 2026-07-25</ac:task-body></ac:task>")
    pages = {
        "status": ConfluencePage("1", "1.★Muffin314-Project Status Report", "https://c/1",
            "<h2>Status Summary</h2><p>Build delivered and validation started.</p>"
            f"<h2>Key Target and Completeness</h2><p>QA</p>{task}"
            '<h2>Highlights</h2><p><a href="https://c/highlight">Demo result</a></p>'
            "<h2>Impact issues</h2><p>N/A</p><h2>Milestone</h2><p>2026-08-01</p>"),
        "test_information": ConfluencePage("2", "3. Muffin314-Test Information", "https://c/2",
            "<p>Pass: 9 Fail: 1 Pending: 0 Total: 10 Pass Rate: 90%</p>"
            '<h2>Failed</h2><p>Decoder crash <a href="https://jira/browse/BUG-1">BUG-1</a></p>'
            f"<h2>Blocking QA Testing Items</h2>{task}"
            f"<h2>Task Arrangement of Important Test</h2>{task}"),
        "test_plan": ConfluencePage("3", "Muffin314-Test Plan", "https://c/3",
            "<p>Week 30: test playback stability and deliver regression report.</p>"),
        "environment": ConfluencePage("4", "Test Environment Setup and Precautions", "https://c/4",
            "<p>Setup steps: install software on device. Configure network setting. Get adb log and dmesg.</p>"),
        "experience": ConfluencePage("5", "Summary of Experience and Typical Cases", "https://c/5", ""),
        "report_store": ConfluencePage("6", "Muffin314-Test Report Store", "https://c/6", ""),
    }
    attachments = {"report_store": [ConfluenceAttachment(
        "a", "weekly-report.xlsx", "https://c/a",
        created_at=datetime(2026, 7, 26, 20, tzinfo=TZ),
    )]}
    findings = StaticAuditService().audit(project, pages, period, attachments)
    required_rules = {
        "status.highlights", "status.impact", "test.metrics", "test.failures",
        "plan.weekly", "environment.complete",
        "report.weekly",
    }
    assert {row.rule_id for row in findings if row.status is AuditStatus.PASSED} >= required_rules
    assert not [row for row in findings if row.status is AuditStatus.FAILED]


def test_stale_test_tasks_fail():
    project = ProjectCandidate("1", "M314", "Muffin314", "https://c/1", "https://c/home")
    period = previous_business_week(datetime(2026, 7, 29, tzinfo=TZ))
    stale = ("<ac:task><ac:task-status>incomplete</ac:task-status>"
             "<ac:task-body>Blocking item 2026-07-20</ac:task-body></ac:task>")
    pages = {
        "status": ConfluencePage("1", "Project Status Report", "https://c/1",
            "<h2>Status Summary</h2><p>Progress</p><h2>QA</h2>" + stale
            + "<h2>Highlights</h2><p>N/A</p><h2>Impact issues</h2><p>None</p>"),
        "test_information": ConfluencePage("2", "Test Information", "https://c/2",
            "<p>Pass: 1 Fail: 0 Pending: 0 Total: 1 Pass Rate: 100%</p>"
            "<h2>Blocking QA Testing Items</h2>" + stale),
    }
    findings = StaticAuditService().audit(project, pages, period)
    failed = {row.rule_id for row in findings if row.status is AuditStatus.FAILED}
    assert "test.blocking_tasks" in failed


def test_real_storage_table_and_rendered_macro_results_drive_static_rules():
    project = ProjectCandidate("1", "M314", "Muffin314", "https://c/1", "https://c/home")
    period = previous_business_week(datetime(2026, 7, 29, tzinfo=TZ))
    task = ("<ac:task><ac:task-status>complete</ac:task-status>"
            "<ac:task-body>QA regression 2026-07-25</ac:task-body></ac:task>")
    status_storage = (
        "<table><tbody>"
        "<tr><th>Status Summary</th><td><ol><li>Build delivered; regression started.</li></ol></td></tr>"
        f"<tr><th>Key Target and Completeness</th><td><p>QA</p>{task}</td></tr>"
        '<tr><th>Highlights</th><td><ac:structured-macro ac:name="content-report"/></td></tr>'
        '<tr><th>Impact issues</th><td><ac:structured-macro ac:name="content-report"/></td></tr>'
        "</tbody></table>"
    )
    status_view = (
        "<table><tbody>"
        "<tr><th>Status Summary</th><td><ol><li>Build delivered; regression started.</li></ol></td></tr>"
        '<tr><th>Highlights</th><td><a href="/display/M314/demo">Demo highlight</a></td></tr>'
        "<tr><th>Impact issues</th><td>N/A</td></tr>"
        "</tbody></table>"
    )
    metric_storage = (
        "<table><thead><tr><th>Test Item</th><th>Pass</th><th>Fail</th><th>N/A</th>"
        "<th>Not Test</th><th>Pending</th><th>Total</th><th>Pass Rate</th>"
        "<th>Results</th><th>Comments</th></tr></thead><tbody><tr>"
        "<td>Playback</td><td>46</td><td>1</td><td>2</td><td>1</td><td>0</td>"
        "<td>50</td><td>97.87%</td><td>Fail</td><td>Decoder crash BUG-1</td>"
        "</tr></tbody></table>"
    )
    metric_view = metric_storage.replace(
        "Decoder crash BUG-1",
        'Decoder crash <a href="https://jira.example/browse/BUG-1">BUG-1</a>',
    )
    pages = {
        "status": ConfluencePage("1", "1.★Muffin314-Project Status Report", "https://c/1",
                                  status_storage, status_view),
        "test_information": ConfluencePage("2", "3. Muffin314-Test Information", "https://c/2",
                                            metric_storage, metric_view),
    }
    findings = StaticAuditService().audit(project, pages, period)
    by_rule = {row.rule_id: row for row in findings}
    assert by_rule["status.highlights"].status is AuditStatus.PASSED
    assert by_rule["status.impact"].status is AuditStatus.PASSED
    assert by_rule["test.metrics"].status is AuditStatus.PASSED
    assert by_rule["test.failures"].status is AuditStatus.PASSED
    assert not ({"status.summary", "qa.tasks", "qa.overdue"} & set(by_rule))


def test_rendered_content_report_not_found_is_not_treated_as_explicit_na():
    project = ProjectCandidate("1", "M314", "Muffin314", "https://c/1", "https://c/home")
    period = previous_business_week(datetime(2026, 7, 29, tzinfo=TZ))
    storage = (
        "<table><tr><th>Status Summary</th><td>Updated</td></tr>"
        "<tr><th>Highlights</th><td><ac:structured-macro/></td></tr>"
        "<tr><th>Impact issues</th><td>N/A</td></tr></table>"
    )
    view = (
        "<table><tr><th>Status Summary</th><td>Updated</td></tr>"
        "<tr><th>Highlights</th><td>未找到内容</td></tr>"
        "<tr><th>Impact issues</th><td>N/A</td></tr></table>"
    )
    page = ConfluencePage("1", "Project Status Report", "https://c/1", storage, view)
    findings = StaticAuditService().audit(project, {"status": page}, period)
    highlight = next(row for row in findings if row.rule_id == "status.highlights")
    assert highlight.status is AuditStatus.FAILED
def test_actual_metric_rows_are_parsed_and_inconsistency_names_row_and_values():
    project = ProjectCandidate("1", "Muffin314", "Muffin314", "https://c/1", "https://c/home")
    period = current_reporting_window(datetime(2026, 7, 29, tzinfo=TZ))
    table = (
        "<table><tr><td>Phase</td><td>EVT</td></tr>"
        "<tr><th>Test Item（需要和 Test Plan 对应）</th><th>Pass</th><th>Fail</th><th>N/A</th>"
        "<th>Pending</th><th>Total</th><th>Pass Rate</th></tr>"
        "<tr><td>Function</td><td>46</td><td>31</td><td>9</td><td>0</td>"
        "<td>86</td><td>59.74%</td></tr>"
        "<tr><td>Compatibility</td><td></td><td></td><td></td><td></td>"
        "<td></td><td></td></tr>"
        "<tr><td>Stability</td><td>3</td><td>2</td><td>0</td><td>16</td>"
        "<td>21</td><td>14.29%</td></tr></table>"
    )
    page = ConfluencePage("i", "Test Information", "https://c/i", table, table)
    findings = StaticAuditService().audit(project, {"test_information": page}, period)
    metric = next(row for row in findings if row.rule_id == "test.metrics")
    assert metric.status is AuditStatus.FAILED
    assert "Stability" in metric.reason
    assert "pass=3" in metric.reason
    assert "fail=2" in metric.reason
    assert "pending=16" in metric.reason
    assert "total=21" in metric.reason
    assert "actual pass rate=14.29%" in metric.reason
    assert "expected pass rate=60.00%" in metric.reason
    assert "Stability" in metric.explanation
    assert "14.29%" in metric.explanation
    assert "60.00%" in metric.explanation
    assert "Pass / (Pass + Fail)" in metric.explanation
    assert "missing" not in metric.reason.casefold()
    assert metric.guidance
    assert metric.page_url == "https://c/i"


def test_report_weekly_failure_explains_window_without_page_update_fallback():
    project = ProjectCandidate("1", "Muffin314", "Muffin314", "https://c/1", "https://c/home")
    period = scheduled_reporting_window(datetime(2026, 7, 29, tzinfo=TZ))
    page = ConfluencePage(
        "r", "Muffin314-Test Report Store", "https://c/r", "",
        updated_at=datetime(2026, 7, 11, 10, tzinfo=TZ),
    )
    finding = next(
        row for row in StaticAuditService().audit(
            project, {"report_store": page}, period, attachments={"report_store": []},
        )
        if row.rule_id == "report.weekly"
    )
    assert finding.status is AuditStatus.FAILED
    assert "2026-07-27" in finding.explanation
    assert "2026-07-30" in finding.explanation
    assert "2026-07-11" not in finding.explanation
    assert "no new report attachment" in finding.explanation.casefold()
