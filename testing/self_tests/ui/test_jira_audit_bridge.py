from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from threading import Event

from PySide6.QtCore import QCoreApplication, QObject, QStandardPaths, Signal

from support.jira_integration.audit import (
    AIReviewStatus,
    AuditReport,
    AuditViolation,
    IssueAuditResult,
    ResolvedAuditInput,
    active_rules,
)
from support.jira_integration.core.models import SearchPage
from ui.example.bridge.JiraAuditBridge import JiraAuditBridge


class FakeAuth(QObject):
    authChanged = Signal()

    def __init__(self, username="chao.li", password="secret"):
        super().__init__()
        self.username = username
        self.password = password

    def currentUsername(self):
        return self.username

    def transientCredential(self):
        return self.username, self.password

    def isAuthenticated(self):
        return bool(self.username)

    def hasCredential(self):
        return bool(self.password)


class FakeClient:
    def search_page(self, _jql, **kwargs):
        return SearchPage([], 0, kwargs.get("max_results", 1), 0, True)

    def fetch_filter(self, _filter_id):
        return {}


def _report():
    return AuditReport(
        resolved=ResolvedAuditInput("jql", "project = SH", "project = SH"),
        generated_at=datetime(2026, 7, 24, 10, 0, 0),
        rules=active_rules(),
        issues=(),
    )


def _report_with_ai_fallback():
    violation = AuditViolation(
        rule_id="description-steps",
        section="Description",
        field="Description",
        observed="Sensitive description must not reach the view state.",
        reason="Steps are required.",
        guidance="Add reproduction steps.",
    )
    issue = IssueAuditResult(
        key="SH-123",
        url="https://jira.example.com/browse/SH-123",
        summary="Safe summary",
        reporter="safe-reporter",
        passed=False,
        violations=(violation,),
        has_ai_candidates=True,
        ai_review_status=AIReviewStatus.UNCONFIGURED,
        ai_failure_category="configuration",
    )
    return AuditReport(
        resolved=ResolvedAuditInput("jql", "project = SH", "project = SH"),
        generated_at=datetime(2026, 7, 24, 10, 0, 0),
        rules=active_rules(),
        issues=(issue,),
    )


def _wait_until(predicate, timeout=2):
    app = QCoreApplication.instance() or QCoreApplication([])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached")


def test_empty_input_and_missing_auth_do_not_start_audit():
    calls = []
    bridge = JiraAuditBridge(FakeAuth(), client_factory=lambda *args: calls.append(args))

    bridge.startAudit("  ")

    assert bridge.viewState["state"] == "idle"
    assert "JQL" in bridge.viewState["inputError"]
    assert calls == []

    bridge = JiraAuditBridge(FakeAuth(password=""), client_factory=lambda *args: calls.append(args))
    bridge.startAudit("project = SH")
    assert bridge.viewState["state"] == "failed"
    assert "Sign in" in bridge.viewState["statusText"]
    assert calls == []


def test_async_completion_reuses_auth_and_reports_progress():
    gate = Event()
    created = []

    class Service:
        def run(self, _resolved, progress):
            progress("fetching", 1, 2)
            gate.wait(2)
            progress("auditing", 2, 2)
            return _report()

    def client_factory(config, auth):
        created.append((config, auth))
        return FakeClient()

    bridge = JiraAuditBridge(
        FakeAuth(),
        client_factory=client_factory,
        service_factory=lambda *_args, **_kwargs: Service(),
    )
    started = time.monotonic()
    bridge.startAudit("project = SH")

    assert time.monotonic() - started < 0.2
    assert bridge.viewState["canStart"] is False
    gate.set()
    _wait_until(lambda: bridge.viewState["state"] == "awaiting_confirmation")
    assert (created[0][1].username, created[0][1].password) == ("chao.li", "secret")
    assert bridge.viewState["progressValue"] == 1.0
    assert bridge.viewState["state"] == "awaiting_confirmation"
    assert bridge.viewState["canConfirm"] is True
    assert bridge.viewState["canExport"] is False


def test_stale_generation_cannot_replace_current_state():
    class HeldThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    bridge = JiraAuditBridge(FakeAuth(), thread_factory=HeldThread)
    bridge.startAudit("project = SH")

    bridge._on_worker_finished({"generation": 0, "report": _report()})

    assert bridge.viewState["state"] == "resolving"
    assert bridge._report is None


def test_export_uses_qstandardpaths_download_location(tmp_path):
    exported = tmp_path / "audit.xlsx"
    calls = []

    class ImmediateThread:
        def __init__(self, *, target, args, **_kwargs):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    class Service:
        def run(self, _resolved, _progress):
            return _report()

    def exporter(_report, *, downloads_dir):
        calls.append(Path(downloads_dir))
        exported.write_bytes(b"xlsx")
        return exported

    bridge = JiraAuditBridge(
        FakeAuth(),
        client_factory=lambda *_args: FakeClient(),
        service_factory=lambda *_args, **_kwargs: Service(),
        export_function=exporter,
        thread_factory=ImmediateThread,
    )
    bridge.startAudit("project = SH")

    bridge.exportReport()
    assert calls == []
    assert "Confirm" in bridge.viewState["inputError"]

    bridge.confirmAudit()
    bridge.exportReport()

    standard = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
    assert calls == [Path(standard) if standard else Path.home() / "Downloads"]
    assert bridge.viewState["exportPath"] == str(exported.resolve())


def test_progress_and_ai_fallback_are_safe_for_the_view_state():
    bridge = JiraAuditBridge(FakeAuth())
    bridge._generation = 1
    expected = {
        "fetching": ("fetching", 0.2),
        "rule_auditing": ("rule_auditing", 0.5),
        "ai_reviewing": ("ai_reviewing", 0.75),
        "finalizing": ("finalizing", 0.9),
    }

    for stage, (state, progress) in expected.items():
        bridge._on_worker_progress((1, stage, 1, 2))
        assert bridge.viewState["state"] == state
        assert bridge.viewState["progressValue"] == progress

    bridge._on_worker_finished({"generation": 1, "report": _report_with_ai_fallback()})

    assert bridge.viewState["state"] == "awaiting_confirmation"
    assert bridge.viewState["aiReviewStatus"] == "fallback"
    assert "Character-rule results were retained" in bridge.viewState["aiReviewText"]
    assert bridge.viewState["violationRows"] == [{
        "issueKey": "SH-123",
        "issueUrl": "https://jira.example.com/browse/SH-123",
        "rule_id": "description-steps",
        "section": "Description",
        "field": "Description",
        "reason": "Steps are required.",
        "guidance": "Add reproduction steps.",
    }]


def test_confirmation_requires_current_report_and_auth_change_revokes_it():
    auth = FakeAuth()
    bridge = JiraAuditBridge(auth)

    bridge.confirmAudit()
    assert "Complete" in bridge.viewState["inputError"]

    bridge._generation = 1
    bridge._on_worker_finished({"generation": 1, "report": _report()})
    bridge.confirmAudit()
    assert bridge.viewState["canExport"] is True

    auth.authChanged.emit()

    assert bridge.viewState["canConfirm"] is False
    assert bridge.viewState["canExport"] is False
    assert bridge.viewState["exportPath"] == ""


def test_input_errors_keep_resolver_categories_without_exposing_lower_errors():
    class ImmediateThread:
        def __init__(self, *, target, args, **_kwargs):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    class FilterDeniedClient(FakeClient):
        def fetch_filter(self, _filter_id):
            raise RuntimeError("private transport detail")

    class InvalidJqlClient(FakeClient):
        def search_page(self, _jql, **_kwargs):
            raise RuntimeError("private validation detail")

    cases = [
        ("ftp://jira.example.com/browse/SH-1", FakeClient, "HTTP or HTTPS"),
        ("https://other.example.com/browse/SH-1", FakeClient, "configured Jira host"),
        ("https://jira.example.com/not-an-audit-url", FakeClient, "issue, filter, or search"),
        ("https://jira.example.com/filter?filter=7", FilterDeniedClient, "could not be loaded"),
        ("project = invalid", InvalidJqlClient, "JQL validation failed"),
    ]
    for text, client_type, expected in cases:
        service_calls = []
        bridge = JiraAuditBridge(
            FakeAuth(),
            base_url="https://jira.example.com",
            client_factory=lambda *_args, client_type=client_type: client_type(),
            service_factory=lambda *_args, **_kwargs: service_calls.append(True),
            thread_factory=ImmediateThread,
        )

        bridge.startAudit(text)

        assert expected in bridge.viewState["inputError"]
        assert "private" not in bridge.viewState["inputError"]
        assert service_calls == []


def test_starting_a_new_audit_revokes_a_confirmed_report():
    class HeldThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    bridge = JiraAuditBridge(FakeAuth(), thread_factory=HeldThread)
    bridge.startAudit("project = SH")
    bridge._on_worker_finished({"generation": 1, "report": _report()})
    bridge.confirmAudit()
    assert bridge.viewState["canExport"] is True

    bridge.startAudit("project = NEW")

    assert bridge.viewState["state"] == "resolving"
    assert bridge.viewState["canConfirm"] is False
    assert bridge.viewState["canExport"] is False
    assert bridge.viewState["resultSummary"] == {}
