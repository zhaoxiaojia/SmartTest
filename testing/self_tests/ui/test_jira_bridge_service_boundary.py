import ast
import importlib
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ui"))
jira_bridge_module = importlib.import_module("example.bridge.JiraBridge")


class FakeAuthBridge(QObject):
    authChanged = Signal()

    def currentUsername(self):
        return "tester"


class FakeWorkspace:
    def __init__(self):
        self.calls = []

    def browse(self, **kwargs):
        self.calls.append(("browse", kwargs))
        return {
            "worker_id": kwargs["worker_id"],
            "issues": [{"keyId": "TV-1", "summary": "Black screen"}],
            "displayed_total": 2,
            "append": kwargs["append"],
            "next_start_at": kwargs["start_at"] + 1,
            "can_load_more": True,
            "scope": dict(kwargs),
        }

    def fetch_issue_detail(self, **kwargs):
        self.calls.append(("fetch_issue_detail", kwargs))
        return {"worker_id": kwargs["worker_id"], "issue": {"keyId": kwargs["issue_key"]}}

    def analyze(self, **kwargs):
        self.calls.append(("analyze", kwargs))
        return {
            "worker_id": kwargs["worker_id"],
            "issues": [],
            "displayed_total": 0,
            "append": False,
            "next_start_at": 0,
            "can_load_more": False,
            "scope": {},
        }


class ImmediateThread:
    def __init__(self, *, target, kwargs, daemon):
        del daemon
        self._target = target
        self._kwargs = kwargs

    def start(self):
        self._target(**self._kwargs)


def test_jira_bridge_only_imports_jira_application_boundary():
    path = Path("ui/example/bridge/JiraBridge.py")
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("jira_tool")
    }

    assert imported <= {"jira_tool.services"}


def test_workspace_facade_keeps_explicit_bridge_entry_points():
    path = Path("jira_tool/services/workspace.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    workspace = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "JiraWorkspaceService"
    )

    methods = {node.name for node in workspace.body if isinstance(node, ast.FunctionDef)}

    assert {"fetch_saved_filters", "browse", "fetch_issue_detail", "analyze"} <= methods


def test_jira_bridge_routes_page_actions_only_through_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(jira_bridge_module, "Thread", ImmediateThread)
    workspace = FakeWorkspace()
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=workspace)
    scope = ("project = TV", "TV", "Open Work", "Last 30 Days", "", "", "bug", "", "", "", "")

    bridge.refreshScope(*scope, False, False, False)
    bridge.selectIssue(0, True, False)
    bridge.loadMore()
    bridge.submitPrompt("summarize blockers", *scope, False, False, False)

    assert [name for name, _kwargs in workspace.calls] == [
        "browse",
        "fetch_issue_detail",
        "browse",
        "analyze",
    ]
    assert workspace.calls[0][1]["start_at"] == 0
    assert workspace.calls[2][1]["append"] is True
    assert workspace.calls[3][1]["prompt"] == "summarize blockers"
