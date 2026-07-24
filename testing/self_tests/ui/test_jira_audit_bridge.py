from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Signal

from support.jira_integration.audit import AuditReport, ResolvedAuditInput, active_rules
from support.jira_integration.core.models import SearchPage


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


class FakeService:
    def __init__(self, report, *, gate=None):
        self.report = report
        self.gate = gate

    def run(self, _resolved, progress):
        progress("fetching", 1, 2)
        if self.gate is not None:
            self.gate.wait(2)
        progress("auditing", 2, 2)
        return self.report


def _empty_report():
    return AuditReport(
        resolved=ResolvedAuditInput("jql", "project = SH", "project = SH"),
        generated_at=datetime(2026, 7, 24, 10, 0, 0),
        rules=active_rules(),
        issues=(),
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


def test_empty_input_is_rejected_without_starting_or_clearing_previous_result():
    from ui.example.bridge.JiraAuditBridge import JiraAuditBridge

    calls = []
    bridge = JiraAuditBridge(FakeAuth(), client_factory=lambda *args: calls.append(args))
    bridge._report = _empty_report()

    bridge.startAudit("  ")

    assert bridge.state == "idle"
    assert "JQL" in bridge.inputError
    assert bridge._report is not None
    assert calls == []


def test_audit_runs_in_background_and_reuses_transient_credential():
    from threading import Event

    from ui.example.bridge.JiraAuditBridge import JiraAuditBridge

    gate = Event()
    created = []

    def client_factory(config, auth):
        created.append((config, auth))
        return FakeClient()

    bridge = JiraAuditBridge(
        FakeAuth(),
        client_factory=client_factory,
        service_factory=lambda _client, base_url: FakeService(_empty_report(), gate=gate),
    )

    started = time.monotonic()
    bridge.startAudit("project = SH")
    elapsed = time.monotonic() - started

    assert elapsed < 0.2
    assert bridge.state in {"resolving", "fetching"}
    assert bridge.canStart is False
    gate.set()
    _wait_until(lambda: bridge.state == "completed")

    assert created[0][1].username == "chao.li"
    assert created[0][1].password == "secret"
    assert bridge.processedCount == 2
    assert bridge.totalCount == 2
    assert bridge.progressValue == 1.0
    assert bridge.canExport is True
    assert bridge.resultSummary["totalCount"] == 0


def test_stale_generation_payload_does_not_replace_newer_state():
    from ui.example.bridge.JiraAuditBridge import JiraAuditBridge

    bridge = JiraAuditBridge(FakeAuth())
    bridge._generation = 4
    bridge._state = "resolving"

    bridge._on_worker_finished({"generation": 3, "report": _empty_report()})

    assert bridge.state == "resolving"
    assert bridge._report is None


def test_export_publishes_generated_file_path(tmp_path):
    from ui.example.bridge.JiraAuditBridge import JiraAuditBridge

    exported = tmp_path / "audit.xlsx"

    def exporter(_report):
        exported.write_bytes(b"xlsx")
        return exported

    bridge = JiraAuditBridge(
        FakeAuth(),
        export_function=exporter,
    )
    bridge._report = _empty_report()
    bridge._state = "completed"

    bridge.exportReport()

    assert bridge.exportPath == str(exported.resolve())


def test_file_reveal_reuses_global_flutools_without_bridge_launcher():
    root = Path(__file__).resolve().parents[3]
    bridge = (root / "ui/example/bridge/JiraAuditBridge.py").read_text(encoding="utf-8")
    workspace = (
        root
        / "ui/example/imports/example/qml/component/jiraaudit/JiraAuditWorkspace.qml"
    ).read_text(encoding="utf-8")

    assert "FluTools.showFileInFolder(JiraAuditBridge.exportPath)" in workspace
    assert "JiraAuditBridge.exportPath.length === 0" in workspace
    for obsolete in ("revealExport", "process_launcher", "subprocess"):
        assert obsolete not in bridge
    assert "JiraAuditBridge.revealExport" not in workspace


def test_missing_transient_credential_fails_before_worker_creation():
    from ui.example.bridge.JiraAuditBridge import JiraAuditBridge

    calls = []
    bridge = JiraAuditBridge(FakeAuth(password=""), client_factory=lambda *args: calls.append(args))

    bridge.startAudit("project = SH")

    assert bridge.state == "failed"
    assert "Sign in" in bridge.statusText
    assert calls == []


def test_input_resolution_errors_are_bridge_owned_fixed_text():
    from ui.example.bridge.JiraAuditBridge import JiraAuditBridge

    bridge = JiraAuditBridge(FakeAuth(), client_factory=lambda *_args: FakeClient())

    bridge.startAudit("https://other.example.com/browse/SH-1")
    _wait_until(lambda: bridge.state == "failed")

    assert bridge.statusText == "The Jira URL host must match the configured Jira host."
