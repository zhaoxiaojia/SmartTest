from __future__ import annotations

import importlib
import time
from datetime import datetime
from pathlib import Path
from threading import Event

import pytest
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

bridge_module = importlib.import_module("ui.example.bridge.JiraAuditBridge")
JiraAuditBridge = bridge_module.JiraAuditBridge


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


class HeldThread:
    def __init__(self, **_kwargs):
        pass

    def start(self):
        pass


class ImmediateThread:
    def __init__(self, *, target, args, **_kwargs):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


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
        ai_review_status=AIReviewStatus.UNCONFIGURED,
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


def test_empty_input_and_missing_auth_do_not_start_audit(monkeypatch):
    calls = []
    monkeypatch.setattr(bridge_module, "JiraClient", lambda *args: calls.append(args))
    bridge = JiraAuditBridge(FakeAuth())

    bridge.startAudit("  ")

    assert bridge.viewState["state"] == "idle"
    assert "JQL" in bridge.viewState["inputError"]
    assert calls == []

    bridge = JiraAuditBridge(FakeAuth(password=""))
    bridge.startAudit("project = SH")
    assert bridge.viewState["state"] == "failed"
    assert "Sign in" in bridge.viewState["statusText"]
    assert calls == []


def test_async_completion_reuses_auth_and_reports_progress(monkeypatch):
    gate = Event()
    created = []

    class Service:
        def run(self, _resolved, progress):
            progress("fetching", 1, 2)
            gate.wait(2)
            progress("rule_auditing", 2, 2)
            return _report()

    def client_factory(config, auth):
        created.append((config, auth))
        return FakeClient()

    monkeypatch.setattr(bridge_module, "JiraClient", client_factory)
    monkeypatch.setattr(bridge_module, "JiraAuditService", lambda *_args, **_kwargs: Service())
    bridge = JiraAuditBridge(FakeAuth())
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


def test_stale_generation_cannot_replace_current_state(monkeypatch):
    monkeypatch.setattr(bridge_module, "Thread", HeldThread)
    bridge = JiraAuditBridge(FakeAuth())
    bridge.startAudit("project = SH")

    bridge._on_worker_finished({"generation": 0, "report": _report()})

    assert bridge.viewState["state"] == "resolving"
    assert bridge._report is None


def test_export_uses_qstandardpaths_download_location(monkeypatch, tmp_path):
    exported = tmp_path / "audit.xlsx"
    calls = []

    class Service:
        def run(self, _resolved, _progress):
            return _report()

    def exporter(_report, *, downloads_dir):
        calls.append(Path(downloads_dir))
        exported.write_bytes(b"xlsx")
        return exported

    monkeypatch.setattr(bridge_module, "JiraClient", lambda *_args: FakeClient())
    monkeypatch.setattr(bridge_module, "JiraAuditService", lambda *_args, **_kwargs: Service())
    monkeypatch.setattr(bridge_module, "export_audit_xlsx", exporter)
    monkeypatch.setattr(bridge_module, "Thread", ImmediateThread)
    bridge = JiraAuditBridge(FakeAuth())
    bridge.startAudit("project = SH")

    bridge.exportReport()
    assert calls == []
    assert "Confirm" in bridge.viewState["inputError"]

    bridge.confirmAudit()
    bridge.exportReport()

    standard = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
    assert calls == [Path(standard) if standard else Path.home() / "Downloads"]
    assert bridge.viewState["exportPath"] == str(exported.resolve())


def test_export_failure_logging_never_retains_exception_details(monkeypatch):
    logged = []
    bridge = JiraAuditBridge(FakeAuth())
    bridge._generation = 1
    bridge._on_worker_finished({"generation": 1, "report": _report()})
    bridge.confirmAudit()
    monkeypatch.setattr(
        bridge_module,
        "export_audit_xlsx",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("private-export-detail")
        ),
    )
    monkeypatch.setattr(
        bridge_module,
        "smart_log",
        lambda *args, **kwargs: logged.append((args, kwargs)),
    )

    bridge.exportReport()

    assert "private-export-detail" not in repr(logged)
    assert logged[0][0] == ("Jira audit export failed",)
    assert "Failed to export" in bridge.viewState["inputError"]


def test_progress_and_ai_fallback_are_safe_for_the_view_state():
    bridge = JiraAuditBridge(FakeAuth())
    bridge._generation = 1
    progress_events = (
        ("fetching", 1, 4, 0.05),
        ("fetching", 2, 4, 0.1),
        ("rule_auditing", 1, 2, 0.35),
        ("rule_auditing", 1, 4, 0.35),
        ("ai_reviewing", 1, 2, 0.625),
        ("finalizing", 1, 2, 0.825),
    )

    for stage, processed, total, progress in progress_events:
        bridge._on_worker_progress((1, stage, processed, total))
        assert bridge.viewState["state"] == stage
        assert bridge.viewState["progressValue"] == pytest.approx(progress)

    bridge._on_worker_finished({"generation": 1, "report": _report_with_ai_fallback()})

    assert bridge.viewState["state"] == "awaiting_confirmation"
    assert "Character-rule results were retained" in bridge.viewState["aiReviewText"]
    assert bridge.viewState["violationRows"] == [{
        "issueKey": "SH-123",
        "issueUrl": "https://jira.example.com/browse/SH-123",
        "rule_id": "description-steps",
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


def test_input_errors_keep_resolver_categories_without_exposing_lower_errors(monkeypatch):
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
        monkeypatch.setattr(bridge_module, "JIRA_BASE_URL", "https://jira.example.com")
        monkeypatch.setattr(
            bridge_module,
            "JiraClient",
            lambda *_args, client_type=client_type: client_type(),
        )
        monkeypatch.setattr(
            bridge_module,
            "JiraAuditService",
            lambda *_args, **_kwargs: service_calls.append(True),
        )
        monkeypatch.setattr(bridge_module, "Thread", ImmediateThread)
        bridge = JiraAuditBridge(FakeAuth())

        bridge.startAudit(text)

        assert expected in bridge.viewState["inputError"]
        assert "private" not in bridge.viewState["inputError"]
        assert service_calls == []


def test_starting_a_new_audit_revokes_a_confirmed_report(monkeypatch):
    monkeypatch.setattr(bridge_module, "Thread", HeldThread)
    bridge = JiraAuditBridge(FakeAuth())
    bridge.startAudit("project = SH")
    bridge._on_worker_finished({"generation": 1, "report": _report()})
    bridge.confirmAudit()
    assert bridge.viewState["canExport"] is True

    bridge.startAudit("project = NEW")

    assert bridge.viewState["state"] == "resolving"
    assert bridge.viewState["canConfirm"] is False
    assert bridge.viewState["canExport"] is False
    assert bridge.viewState["resultSummary"] == {}
