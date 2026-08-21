from __future__ import annotations

import importlib
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ui"))
jira_module = importlib.import_module("example.bridge.JiraBridge")
jira_audit_module = importlib.import_module("example.bridge.JiraAuditBridge")
confluence_module = importlib.import_module("example.bridge.ConfluenceAuditBridge")


class RuntimeAuth(QObject):
    authChanged = Signal()
    runtimeCredentialSupplyRequired = Signal()
    runtimeCredentialSupplied = Signal()
    runtimeCredentialSupplyCancelled = Signal()

    def __init__(self):
        super().__init__()
        self.password = ""

    def currentUsername(self):
        return "alice"

    def isAuthenticated(self):
        return True

    def hasCredential(self):
        return bool(self.password)

    def transientCredential(self):
        return "alice", self.password

    def acquireRuntimeCredential(self):
        if self.password:
            return {"status": "ready"}
        self.runtimeCredentialSupplyRequired.emit()
        return {"status": "password_required"}


class HeldThread:
    pending = []

    def __init__(self, *, target, args=(), kwargs=None, **_ignored):
        self._call = lambda: target(*args, **(kwargs or {}))

    def start(self):
        self.pending.append(self._call)


class JiraWorkspace:
    def fetch_saved_filters(self):
        return []


def test_jira_workspace_requests_runtime_password_and_bootstraps_once(monkeypatch):
    HeldThread.pending = []
    monkeypatch.setattr(jira_module, "Thread", HeldThread)
    auth = RuntimeAuth()
    requests = []
    auth.runtimeCredentialSupplyRequired.connect(lambda: requests.append(True))
    bridge = jira_module.JiraBridge(auth, workspace_service=JiraWorkspace())

    bridge.bootstrap()
    assert requests == [True]
    assert "LDAP" not in bridge.statusText

    auth.password = "direct-password"
    auth.runtimeCredentialSupplied.emit()
    auth.runtimeCredentialSupplied.emit()

    assert bridge.connected is True
    assert len(HeldThread.pending) == 1


def test_jira_audit_resumes_one_pending_request_after_password(monkeypatch):
    HeldThread.pending = []
    monkeypatch.setattr(jira_audit_module, "Thread", HeldThread)
    auth = RuntimeAuth()
    requests = []
    auth.runtimeCredentialSupplyRequired.connect(lambda: requests.append(True))
    bridge = jira_audit_module.JiraAuditBridge(auth)

    bridge.startAudit("project = SH")
    assert requests == [True]
    assert "LDAP" not in bridge.viewState["statusText"]

    auth.password = "direct-password"
    auth.runtimeCredentialSupplied.emit()
    auth.runtimeCredentialSupplied.emit()

    assert bridge.viewState["state"] == "resolving"
    assert len(HeldThread.pending) == 1


def test_confluence_audit_resumes_one_pending_request_after_password(
    monkeypatch, tmp_path,
):
    HeldThread.pending = []
    monkeypatch.setattr(confluence_module, "Thread", HeldThread)
    auth = RuntimeAuth()
    requests = []
    auth.runtimeCredentialSupplyRequired.connect(lambda: requests.append(True))
    bridge = confluence_module.ConfluenceAuditBridge(auth, history_root=tmp_path)
    bridge.toggleProductLine("DOPL")

    bridge.startAudit()
    assert requests == [True]
    assert "LDAP" not in bridge.viewState["statusText"]

    auth.password = "direct-password"
    auth.runtimeCredentialSupplied.emit()
    auth.runtimeCredentialSupplied.emit()

    assert bridge.viewState["state"] == "discovering"
    assert len(HeldThread.pending) == 1
