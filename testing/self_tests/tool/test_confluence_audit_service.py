from datetime import datetime
import json
from zoneinfo import ZoneInfo

from support.confluence_integration.models import ConfluencePage
from tool.common.project_weekly_audit.models import (
    AuditPeriod,
    AuditStatus,
    ProjectCandidate,
    UPDATE_MATRIX_POINTS,
)
from tool.common.project_weekly_audit.service import ConfluenceAuditService


TZ = ZoneInfo("Asia/Shanghai")


def project():
    return ProjectCandidate(
        "status", "M314", "Muffin314", "https://c/status",
        "https://c/root", 2026, "A", "NORMAL", (2026,),
    )


def period():
    return AuditPeriod(
        datetime(2026, 7, 27, tzinfo=TZ),
        datetime(2026, 7, 31, tzinfo=TZ),
    )


def test_missing_and_unreadable_pages_are_invalid_with_diagnostics(monkeypatch):
    pages = {}
    errors = {
        "test_plan": "PermissionError|pageId=42; HTTP 403",
    }
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_pages",
        lambda *_args, **_kwargs: (pages, errors),
    )

    findings = ConfluenceAuditService(object())._audit_project(
        project(), period(),
    ).findings

    assert {finding.status for finding in findings} == {
        AuditStatus.INVALID_FORMAT,
    }
    plan = next(row for row in findings if row.rule_id == "plan.test")
    assert plan.reason == "PermissionError"
    assert plan.explanation == "pageId=42; HTTP 403"
    report = next(row for row in findings if row.rule_id == "report.weekly")
    assert report.explanation == "格式有误：查询不到Test Report Store"
    missing = [row for row in findings if row.rule_id != "plan.test"]
    standard_names = {
        point.rule_id: point.standard_name for point in UPDATE_MATRIX_POINTS
    }
    assert all(
        row.explanation == f"格式有误：查询不到{standard_names[row.rule_id]}"
        for row in missing
    )


class VersionedPageClient:
    def __init__(self, current, historical):
        self.current = current
        self.historical = historical

    def get_page(self, page_id):
        assert page_id == self.current.id
        return self.current

    def get_page_version(self, page_id, version):
        assert page_id == self.current.id
        return self.historical[version]


def test_same_page_regions_are_compared_independently(monkeypatch):
    previous = ConfluencePage(
        "s", "Project Status Report", "https://c/s",
        body=(
            "<h2>Highlights</h2><p>Old highlight</p>"
            "<h2>Impact issues</h2><p>Stable impact</p>"
        ),
        version=1,
        updated_at=datetime(2026, 8, 2, 20, tzinfo=TZ),
    )
    current = ConfluencePage(
        "s", "Project Status Report", "https://c/s",
        body=(
            "<h2>Highlights</h2><p>New highlight</p>"
            "<h2>Impact issues</h2><p>Stable impact</p>"
        ),
        version=2,
        updated_at=datetime(2026, 8, 3, 9, tzinfo=TZ),
    )
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_pages",
        lambda *_args, **_kwargs: ({"status": current}, {}),
    )
    window = AuditPeriod(
        datetime(2026, 8, 3, tzinfo=TZ),
        datetime(2026, 8, 5, 12, tzinfo=TZ),
    )

    findings = ConfluenceAuditService(
        VersionedPageClient(current, {1: previous}),
    )._audit_project(project(), window).findings
    by_rule = {finding.rule_id: finding for finding in findings}

    assert by_rule["status.highlights"].status is AuditStatus.UPDATED
    assert by_rule["status.impact"].status is AuditStatus.NOT_UPDATED


def test_whitespace_and_style_only_region_change_is_not_updated(monkeypatch):
    previous = ConfluencePage(
        "s", "Project Status Report", "https://c/s",
        body="<h2>Highlights</h2><p>Same content</p>",
        version=1,
        updated_at=datetime(2026, 8, 2, 20, tzinfo=TZ),
    )
    current = ConfluencePage(
        "s", "Project Status Report", "https://c/s",
        body=(
            '<h2 style="color: blue">Highlights</h2>'
            '<p class="emphasis">  Same\n\tcontent  </p>'
        ),
        version=2,
        updated_at=datetime(2026, 8, 3, 9, tzinfo=TZ),
    )
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_pages",
        lambda *_args, **_kwargs: ({"status": current}, {}),
    )

    findings = ConfluenceAuditService(
        VersionedPageClient(current, {1: previous}),
    )._audit_project(
        project(),
        AuditPeriod(
            datetime(2026, 8, 3, tzinfo=TZ),
            datetime(2026, 8, 5, 12, tzinfo=TZ),
        ),
    ).findings

    highlight = next(
        row for row in findings if row.rule_id == "status.highlights"
    )
    assert highlight.status is AuditStatus.NOT_UPDATED


def test_test_plan_table_data_change_is_updated(monkeypatch):
    previous = ConfluencePage(
        "p", "Test Plan", "https://c/p",
        body=(
            "<table><tr><th>Category</th><th>Sub-Item</th><th>August</th></tr>"
            "<tr><td>Function</td><td>Smoke</td><td>Planned</td></tr></table>"
        ),
        version=1,
        updated_at=datetime(2026, 8, 2, 20, tzinfo=TZ),
    )
    current = ConfluencePage(
        "p", "Test Plan", "https://c/p",
        body=(
            "<table><tr><th>Category</th><th>Sub-Item</th><th>August</th></tr>"
            "<tr><td>Function</td><td>Regression</td><td>Done</td></tr></table>"
        ),
        version=2,
        updated_at=datetime(2026, 8, 3, 9, tzinfo=TZ),
    )
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_pages",
        lambda *_args, **_kwargs: ({"test_plan": current}, {}),
    )

    findings = ConfluenceAuditService(
        VersionedPageClient(current, {1: previous}),
    )._audit_project(project(), AuditPeriod(
        datetime(2026, 8, 3, tzinfo=TZ),
        datetime(2026, 8, 5, 12, tzinfo=TZ),
    )).findings
    plan = next(row for row in findings if row.rule_id == "plan.test")

    assert plan.status is AuditStatus.UPDATED


def test_present_empty_region_is_not_invalid(monkeypatch):
    current = ConfluencePage(
        "s", "Test Information", "https://c/s",
        body="<h2>III. Blocking QA Testing Items：</h2>",
        version=1,
        updated_at=datetime(2026, 8, 3, 9, tzinfo=TZ),
    )
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_pages",
        lambda *_args, **_kwargs: ({"test_information": current}, {}),
    )

    findings = ConfluenceAuditService(
        VersionedPageClient(current, {}),
    )._audit_project(project(), AuditPeriod(
        datetime(2026, 8, 3, tzinfo=TZ),
        datetime(2026, 8, 5, 12, tzinfo=TZ),
    )).findings
    blocking = next(row for row in findings if row.rule_id == "test.blocking")

    assert blocking.status is AuditStatus.UPDATED


def test_historical_missing_to_present_empty_is_updated(monkeypatch):
    previous = ConfluencePage(
        "s", "Test Information", "https://c/s",
        body="<h2>Other field</h2>", version=1,
        updated_at=datetime(2026, 8, 2, 20, tzinfo=TZ),
    )
    current = ConfluencePage(
        "s", "Test Information", "https://c/s",
        body="<h2>III. Blocking QA Testing Items：</h2>", version=2,
        updated_at=datetime(2026, 8, 3, 9, tzinfo=TZ),
    )
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_pages",
        lambda *_args, **_kwargs: ({"test_information": current}, {}),
    )

    findings = ConfluenceAuditService(
        VersionedPageClient(current, {1: previous}),
    )._audit_project(project(), AuditPeriod(
        datetime(2026, 8, 3, tzinfo=TZ),
        datetime(2026, 8, 5, 12, tzinfo=TZ),
    )).findings
    blocking = next(row for row in findings if row.rule_id == "test.blocking")

    assert blocking.status is AuditStatus.UPDATED


def test_rule_trace_is_complete_and_does_not_leak_content(monkeypatch):
    current = ConfluencePage(
        "s", "Project Status Report", "https://c/s",
        body="<h2>Highlights</h2><p>SECRET_BODY_VALUE</p>", version=1,
        updated_at=datetime(2026, 8, 2, 20, tzinfo=TZ),
    )
    records = []
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.smart_log",
        lambda message, *args, **kwargs: records.append((message, kwargs)),
    )
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "status.highlights")

    ConfluenceAuditService(VersionedPageClient(current, {}))._audit_page_regions(
        project(), current, (point,), period(),
    )

    trace = next(
        kwargs["extra"] for message, kwargs in records
        if message.startswith("Confluence audit rule trace")
    )
    assert {
        "project_id", "project_name", "rule_id", "standard_name",
        "page_id", "page_title", "page_url", "configured_locators",
        "versions", "baseline_version", "changed", "final_status",
        "final_reason",
    } <= trace.keys()
    assert {
        "version", "updated_at", "source", "found", "locator_type",
        "element_type", "boundary", "content_length", "content_hash",
    } <= trace["versions"][0].keys()
    assert "SECRET_BODY_VALUE" not in json.dumps(trace, ensure_ascii=False)


def test_region_missing_is_invalid_without_page_timestamp_fallback(monkeypatch):
    current = ConfluencePage(
        "s", "Project Status Report", "https://c/s",
        body="<h2>Highlights</h2><p>Updated</p>",
        version=1,
        updated_at=datetime(2026, 8, 3, 9, tzinfo=TZ),
    )
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_pages",
        lambda *_args, **_kwargs: ({"status": current}, {}),
    )

    findings = ConfluenceAuditService(
        VersionedPageClient(current, {}),
    )._audit_project(
        project(),
        AuditPeriod(
            datetime(2026, 8, 3, tzinfo=TZ),
            datetime(2026, 8, 5, 12, tzinfo=TZ),
        ),
    ).findings
    impact = next(row for row in findings if row.rule_id == "status.impact")

    assert impact.status is AuditStatus.INVALID_FORMAT
    assert impact.reason == "格式有误"
    assert impact.explanation == "格式有误：查询不到Impact issues"


def test_empty_test_report_store_page_is_structurally_valid(monkeypatch):
    current = ConfluencePage(
        "r", "Test Report Store", "https://c/r",
        body="<p>  </p>", version=1,
        updated_at=datetime(2026, 8, 3, 9, tzinfo=TZ),
    )
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_pages",
        lambda *_args, **_kwargs: ({"report_store": current}, {}),
    )

    findings = ConfluenceAuditService(
        VersionedPageClient(current, {}),
    )._audit_project(project(), AuditPeriod(
        datetime(2026, 8, 3, tzinfo=TZ),
        datetime(2026, 8, 5, 12, tzinfo=TZ),
    )).findings
    report = next(row for row in findings if row.rule_id == "report.weekly")

    assert report.status is AuditStatus.UPDATED


def test_monday_reset_excludes_region_change_before_midnight(monkeypatch):
    saturday = ConfluencePage(
        "s", "Project Status Report", "https://c/s",
        body="<h2>Highlights</h2><p>Saturday value</p>",
        version=1,
        updated_at=datetime(2026, 8, 1, 10, tzinfo=TZ),
    )
    sunday = ConfluencePage(
        "s", "Project Status Report", "https://c/s",
        body="<h2>Highlights</h2><p>Sunday value</p>",
        version=2,
        updated_at=datetime(2026, 8, 2, 23, 59, 59, tzinfo=TZ),
    )
    monday = ConfluencePage(
        "s", "Project Status Report", "https://c/s",
        body="<h2>Highlights</h2><p>Sunday value</p>",
        version=3,
        updated_at=datetime(2026, 8, 3, 0, 0, 1, tzinfo=TZ),
    )
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_pages",
        lambda *_args, **_kwargs: ({"status": monday}, {}),
    )

    findings = ConfluenceAuditService(
        VersionedPageClient(monday, {1: saturday, 2: sunday}),
    )._audit_project(
        project(),
        AuditPeriod(
            datetime(2026, 8, 3, tzinfo=TZ),
            datetime(2026, 8, 5, 12, tzinfo=TZ),
        ),
    ).findings

    highlight = next(
        row for row in findings if row.rule_id == "status.highlights"
    )
    assert highlight.status is AuditStatus.NOT_UPDATED
