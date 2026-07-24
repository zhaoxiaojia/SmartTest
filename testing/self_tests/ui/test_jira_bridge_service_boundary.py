import ast
import importlib
import json
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


class DeferredThread:
    pending = []

    def __init__(self, *, target, kwargs, daemon):
        del daemon
        self._target = target
        self._kwargs = kwargs

    def start(self):
        self.pending.append(self)


def test_jira_bridge_only_imports_jira_application_boundary():
    path = Path("ui/example/bridge/JiraBridge.py")
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("jira")
    }

    assert imported <= {"jira"}


def test_jira_bridge_does_not_own_conversation_storage_or_identity():
    path = Path("ui/example/bridge/JiraBridge.py")
    source = path.read_text(encoding="utf-8-sig")

    assert "self._conversation =" not in source
    assert "self._conversation_history" not in source
    assert "self._current_conversation_id" not in source
    assert "def _load_conversation_history" not in source
    assert "def _save_conversation_history" not in source
    assert "def _persist_current_conversation" not in source
    assert "jsonTool" not in source


def test_workspace_facade_keeps_explicit_bridge_entry_points():
    path = Path("jira/workspace.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    workspace = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "JiraWorkspaceService"
    )

    methods = {node.name for node in workspace.body if isinstance(node, ast.FunctionDef)}

    assert {"fetch_saved_filters", "browse", "fetch_issue_detail", "analyze"} <= methods


def test_jira_filters_region_uses_bridge_quick_views():
    source = Path("ui/example/imports/example/qml/page/T_Jira.qml").read_text(encoding="utf-8")
    assert 'title: qsTr("Filters")' in source
    assert 'text: qsTr("Quick views")' in source
    assert "quickViews = JiraBridge.quickViews" in source
    assert "model: quickViews" in source
    assert "filterRow.query || filterRow.jql" in source


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


def test_conversation_slots_preserve_clear_restore_and_retry_semantics(monkeypatch, tmp_path):
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(jira_bridge_module, "Thread", ImmediateThread)
    workspace = FakeWorkspace()
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=workspace)
    scope = ("", "TV", "Open Work", "Last 30 Days", "", "", "bug", "", "", "", "")

    bridge.submitPrompt("raw Jira question", *scope, False, False, False)
    initial_rows = bridge.conversationRows()
    history_id = bridge.conversationHistoryRows()[0]["id"]
    bridge.retryPrompt("raw Jira question")

    assert bridge.conversationRows() == initial_rows
    assert [name for name, _kwargs in workspace.calls] == ["analyze", "analyze"]
    assert workspace.calls[-1][1]["include_user_message"] is False

    bridge.clearConversation()
    assert bridge.conversationRows()[0]["message"] == (
        "Session cleared. Ask a new Jira question when ready."
    )

    bridge.restoreConversation(history_id)
    assert [row["message"] for row in bridge.conversationRows()] == ["raw Jira question"]


def test_clear_rejects_in_flight_result_error_and_progress(monkeypatch, tmp_path):
    DeferredThread.pending = []
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(jira_bridge_module, "Thread", DeferredThread)
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=FakeWorkspace())
    scope = ("", "TV", "Open Work", "Last 30 Days", "", "", "bug", "", "", "", "")

    bridge.submitPrompt("current question", *scope, False, False, False)
    old_worker_id = DeferredThread.pending[-1]._kwargs["worker_id"]
    assert bridge._get_loading() is True

    bridge.clearConversation()
    bridge._on_progress_update({"worker_id": old_worker_id, "message": "stale progress"})
    bridge._on_worker_error({"worker_id": old_worker_id, "message": "stale error"})
    bridge._on_worker_result(
        {
            "worker_id": old_worker_id,
            "issues": [{"keyId": "STALE-1"}],
            "assistant_message": "stale answer",
            "assistant_timestamp": "later",
            "connected": True,
        }
    )

    assert bridge._get_loading() is False
    assert bridge.statusText == "Ready"
    assert bridge.issueRows() == []
    assert [row["message"] for row in bridge.conversationRows()] == [
        "Session cleared. Ask a new Jira question when ready."
    ]
    history_id = bridge.conversationHistoryRows()[0]["id"]
    bridge.restoreConversation(history_id)
    assert [row["message"] for row in bridge.conversationRows()] == ["current question"]
    assert all(row.get("is_progress") is not True for row in bridge.conversationRows())


def test_restore_rejects_in_flight_result_for_selected_conversation(monkeypatch, tmp_path):
    history_path = tmp_path / "Jira" / "ai_conversation_history.json"
    history_path.parent.mkdir(parents=True)
    history_path.write_text(
        """
        {
          "conversations": [
            {
              "id": "saved",
              "title": "Saved question",
              "preview": "Saved answer",
              "updated_at": 10,
              "messages": [
                {"role": "user", "author": "coco", "message": "Saved question", "timestamp": "then"},
                {"role": "assistant", "author": "SmartTest AI", "message": "Saved answer", "timestamp": "then"}
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    DeferredThread.pending = []
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(jira_bridge_module, "Thread", DeferredThread)
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=FakeWorkspace())
    scope = ("", "TV", "Open Work", "Last 30 Days", "", "", "bug", "", "", "", "")

    bridge.submitPrompt("superseded question", *scope, False, False, False)
    old_worker_id = DeferredThread.pending[-1]._kwargs["worker_id"]
    bridge.restoreConversation("saved")
    bridge._on_worker_result(
        {
            "worker_id": old_worker_id,
            "assistant_message": "stale answer",
            "assistant_timestamp": "later",
            "connected": True,
        }
    )

    assert bridge._get_loading() is False
    assert bridge.statusText == "Ready"
    assert [row["message"] for row in bridge.conversationRows()] == ["Saved question", "Saved answer"]
    history_rows = bridge.conversationHistoryRows()
    assert len(history_rows) == 1
    assert history_rows[0]["id"] == "saved"
    assert history_rows[0]["messageCount"] == 2


def test_restore_filters_unrenderable_persisted_templates(monkeypatch, tmp_path):
    history_path = tmp_path / "Jira" / "ai_conversation_history.json"
    history_path.parent.mkdir(parents=True)
    history_path.write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "id": "templates",
                        "title": "Templates",
                        "preview": "",
                        "updated_at": 10,
                        "messages": [
                            {"role": "assistant", "message": "raw Jira text"},
                            {
                                "role": "assistant",
                                "message_template": "Matched {count}",
                                "message_values": {"count": 2},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Plain fixed text",
                                "message_values": {},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Missing {missing}",
                                "message_values": {},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Broken {",
                                "message_values": {},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Unsafe {user.name}",
                                "message_values": {"user": "coco"},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Positional {0}",
                                "message_values": {"0": "value"},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Conversion {name!r}",
                                "message_values": {"name": "value"},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Specification {count:02d}",
                                "message_values": {"count": 2},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Index {items[0]}",
                                "message_values": {"items": "value"},
                            },
                            {
                                "role": "assistant",
                                "message": "bad timestamp",
                                "timestamp_template": "Broken {",
                                "timestamp_values": {},
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=FakeWorkspace())

    bridge.restoreConversation("templates")
    rows = bridge.conversationRows()

    assert [row["message"] for row in rows] == [
        "raw Jira text",
        "Matched 2",
        "Plain fixed text",
    ]
