from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from threading import Event

from PySide6.QtCore import QCoreApplication, QObject, QStandardPaths, Signal

from support.jira_integration.audit import AuditReport, ResolvedAuditInput, active_rules
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
    _wait_until(lambda: bridge.viewState["state"] == "completed")
    assert (created[0][1].username, created[0][1].password) == ("chao.li", "secret")
    assert bridge.viewState["progressValue"] == 1.0
    assert bridge.viewState["canExport"] is True


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

    standard = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
    assert calls == [Path(standard) if standard else Path.home() / "Downloads"]
    assert bridge.viewState["exportPath"] == str(exported.resolve())
