from datetime import datetime
from zoneinfo import ZoneInfo

from tool.common.project_weekly_audit.models import (
    AuditExecutionContext, AuditStatus, ConfluenceProject,
    ProjectCollection, ProjectCollectionFilter,
)
from tool.common.project_weekly_audit.period import current_reporting_window
from tool.common.project_weekly_audit.service import ConfluenceAuditService
from support.confluence_integration.models import (
    ConfluenceAttachment, ConfluencePage,
)


TZ = ZoneInfo("Asia/Shanghai")


class ContentClient:
    def __init__(self, *, unreadable_kind=""):
        self.unreadable_kind = unreadable_kind
        self.pages = {
            "status": ConfluencePage(
                "status", "Muffin314-Project Status Report", "https://c/status",
                "<table><tr><th>Highlights</th><td>N/A</td></tr>"
                "<tr><th>Impact issues</th><td>N/A</td></tr></table>",
                updated_at=datetime(2026, 7, 28, tzinfo=TZ),
            ),
            "test_information": ConfluencePage(
                "test_information", "Muffin314-Test Information", "https://c/info",
                "Pass: 10 Fail: 0 Pending: 0 Total: 10 Pass Rate: 100%",
                updated_at=datetime(2026, 7, 28, tzinfo=TZ),
            ),
            "test_plan": ConfluencePage(
                "test_plan", "Muffin314-Test Plan", "https://c/plan",
                "Week 31 test playback and deliver validation report.",
                updated_at=datetime(2026, 7, 28, tzinfo=TZ),
            ),
            "environment": ConfluencePage(
                "environment", "Test Environment Setup and Precautions",
                "https://c/environment",
                "Setup step install software on device, configure settings, collect adb log.",
                updated_at=datetime(2026, 7, 28, tzinfo=TZ),
            ),
            "experience": ConfluencePage(
                "experience", "Summary of Experience and Typical Cases",
                "https://c/experience", "Completed project notes.",
            ),
            "report_store": ConfluencePage(
                "report_store", "Muffin314-Test Report Store", "https://c/report",
                "<a href='https://c/report/latest'>Latest report</a>",
                updated_at=datetime(2026, 7, 28, tzinfo=TZ),
            ),
        }
        self.root = ConfluencePage("root", "Muffin314", "https://c/root")
        self.basic = ConfluencePage(
            "basic", "Muffin314-Basic Information", "https://c/basic",
        )

    def get_page_by_url(self, _url):
        return self.root

    def get_page_children(self, page_id):
        if page_id == self.root.id:
            return [self.pages["status"], self.basic]
        if page_id == self.basic.id:
            return [page for kind, page in self.pages.items() if kind != "status"]
        return []

    def get_page(self, page_id):
        for kind, page in self.pages.items():
            if page.id == page_id:
                if kind == self.unreadable_kind:
                    raise PermissionError("denied")
                return page
        raise KeyError(page_id)

    def get_attachments(self, page_id):
        assert page_id == "report_store"
        return [ConfluenceAttachment(
            "a", "weekly.xlsx", "https://c/a",
            created_at=datetime(2026, 7, 28, tzinfo=TZ),
        )]


def collection():
    criteria = ProjectCollectionFilter("source", (2026,))
    project = ConfluenceProject(
        2026, "M314", "Muffin314", "status", "https://c/status",
        "https://c/root", support_mode="A", project_status="NORMAL",
    )
    return ProjectCollection(
        "catalog", "Projects", criteria, datetime(2026, 7, 31, tzinfo=TZ),
        (project,),
    )


def run(monkeypatch, client):
    source = collection()
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.service.discover_project_collection",
        lambda *_args, **_kwargs: source,
    )
    return ConfluenceAuditService(client).run(
        source.filter,
        current_reporting_window(datetime(2026, 7, 29, tzinfo=TZ)),
        AuditExecutionContext("manual"),
    )


def test_service_returns_content_findings_without_update_or_ai_transport(monkeypatch):
    batch = run(monkeypatch, ContentClient())

    assert batch.projects[0].findings
    assert {finding.rule_id for finding in batch.projects[0].findings} >= {
        "required.status", "status.highlights", "test.metrics", "plan.weekly",
        "environment.complete", "report.weekly",
    }


def test_unreadable_page_is_reported_unknown_without_stopping_other_rules(monkeypatch):
    batch = run(monkeypatch, ContentClient(unreadable_kind="test_plan"))
    findings = batch.projects[0].findings
    plan = next(row for row in findings if row.rule_id == "required.test_plan")

    assert plan.status is AuditStatus.UNKNOWN
    assert any(row.rule_id == "status.highlights" for row in findings)
