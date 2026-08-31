from __future__ import annotations

import importlib
import sys
from pathlib import Path

from PySide6.QtCore import QFile, QObject, Signal


sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "client" / "app" / "ui"))
jira_module = importlib.import_module("example.bridge.JiraBridge")
tool_module = importlib.import_module("example.bridge.ToolBridge")
importlib.import_module("example.imports.resource_rc")


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


def test_common_tool_catalog_excludes_retired_client_tools_and_preserves_others():
    groups = {group["id"]: group for group in tool_module.build_tool_groups()}

    assert groups["common"]["tools"] == []
    assert groups["SmartHome"]["tools"] == [{"id": "redmine"}]
    assert set(groups) == {"common", "STB", "TV", "SmartHome", "IPTV", "Wi-Fi"}


def test_jira_page_runtime_resources_and_bridge_remain_available():
    assert QFile(":/example/qml/page/T_Jira.qml").exists()
    assert jira_module.JiraBridge.__name__ == "JiraBridge"
