import ast
import copy
import importlib
import json
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ui"))
jira_bridge_module = importlib.import_module("example.bridge.JiraBridge")


class FakeAuthBridge(QObject):
    authChanged = Signal()

    def currentUsername(self):
        return "tester"


class StatefulAuthBridge(FakeAuthBridge):
    def __init__(self):
        super().__init__()
        self.authenticated = True
        self.credential = True

    def isAuthenticated(self):
        return self.authenticated

    def hasCredential(self):
        return self.credential


class FakeWorkspace:
    def __init__(self):
        self.calls = []

    def browse(self, **kwargs):
        self.calls.append(("browse", kwargs))
        return {
            "mode": "browse",
            "worker_id": kwargs["worker_id"],
            "connected": True,
            "status_state": {"kind": "raw", "text": "Connected"},
            "issues": [{"keyId": "TV-1", "summary": "Black screen"}],
            "selected_issue_index": 0,
            "displayed_total": 2,
            "analysis_summary": "",
            "analysis_summary_state": {"kind": "raw", "text": ""},
            "analysis_actions": [],
            "assistant_message": "",
            "assistant_timestamp": "",
            "append": kwargs["append"],
            "next_start_at": kwargs["start_at"] + 1,
            "can_load_more": True,
            "scope": {
                key: kwargs[key]
                for key in _browse_scope()
                if key in kwargs
            }
            | {
                "board_id": kwargs["board_id"],
                "timeframe_id": kwargs["timeframe_id"],
            },
        }

    def fetch_issue_detail(self, **kwargs):
        self.calls.append(("fetch_issue_detail", kwargs))
        return {"worker_id": kwargs["worker_id"], "issue": {"keyId": kwargs["issue_key"]}}

    def analyze(self, **kwargs):
        self.calls.append(("analyze", kwargs))
        return {
            "mode": "analyze",
            "worker_id": kwargs["worker_id"],
            "connected": True,
            "status_state": {"kind": "raw", "text": "Connected"},
            "issues": [],
            "selected_issue_index": 0,
            "displayed_total": 0,
            "analysis_summary": "",
            "analysis_summary_state": {"kind": "raw", "text": ""},
            "analysis_actions": [],
            "assistant_message": "",
            "assistant_timestamp": "",
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


class _BrowseHarness:
    def __init__(self, label_for=lambda kind, option_id: f"{kind}:{option_id}"):
        self.bridge = jira_bridge_module.JiraBridge(
            FakeAuthBridge(),
            workspace_service=FakeWorkspace(),
        )
        self.bridge._browse_option_label = label_for

    def apply_result(self, payload):
        self.bridge._apply_browse_result(payload)

    def refresh_request(self, **scope):
        return self.bridge._request(scope)

    def analysis_scope(self, **scope):
        return self.bridge._normalize_scope(scope)

    def load_more_request(self):
        if not self.bridge._can_load_more or not self.bridge._active_scope:
            return None
        return self.bridge._request(
            self.bridge._active_scope,
            start_at=self.bridge._next_start_at,
            append=True,
        )

    def select_issue(self, index):
        if index < 0 or index >= len(self.bridge._issues):
            return None
        self.bridge._selected_issue_index = index
        return self.bridge._issue_key(self.bridge._issues[index])

    def apply_detail(self, issue):
        before = self.selected_issue
        self.bridge._apply_issue_detail(issue)
        return self.selected_issue != before

    def apply_saved_filters(self, filters):
        self.bridge._saved_filters = [dict(item) for item in filters]

    def reset(self):
        self.bridge._reset_browse_state()

    @property
    def issue_rows(self):
        return self.bridge.issueRows()

    @property
    def selected_issue(self):
        return self.bridge.selectedIssue()

    @property
    def saved_filters(self):
        return self.bridge.savedFilters()

    @property
    def active_scope(self):
        return copy.deepcopy(self.bridge._active_scope)

    @property
    def displayed_total(self):
        return self.bridge._displayed_total

    @property
    def next_start_at(self):
        return self.bridge._next_start_at

    @property
    def can_load_more(self):
        return self.bridge._can_load_more

    @property
    def quick_views(self):
        return self.bridge.quickViews

    @property
    def project_options(self):
        return self.bridge.projectFilterOptions()

    @property
    def board_options(self):
        return self.bridge.boardOptions()

    @property
    def timeframe_options(self):
        return self.bridge.timeframeOptions()

    @property
    def status_options(self):
        return self.bridge.statusFilterOptions()

    @property
    def priority_options(self):
        return self.bridge.priorityFilterOptions()

    @property
    def issue_type_options(self):
        return self.bridge.issueTypeFilterOptions()

    @property
    def quick_stats(self):
        return {
            "matched": self.bridge._displayed_total,
            "displayed": len(self.bridge._issues),
            "high_priority": int(self.bridge.quickStats()[1]["value"]),
            "blocked": int(self.bridge.quickStats()[2]["value"]),
            "ready_for_test": int(self.bridge.quickStats()[3]["value"]),
        }

    def active_scope_summary(self, **_kwargs):
        return self.bridge._scope_summary()


def _browse_controller():
    return _BrowseHarness()


def _browse_scope(**overrides):
    scope = {
        "raw_jql_text": "",
        "project_ids_csv": "tv",
        "board_label": "board:open_work",
        "timeframe_label": "timeframe:last_30_days",
        "status_ids_csv": "open,blocked",
        "priority_ids_csv": "high",
        "issue_type_ids_csv": "bug",
        "keyword_text": "",
        "assignee_text": "",
        "reporter_text": "",
        "labels_text": "",
        "include_comments": False,
        "include_links": False,
        "only_mine": False,
    }
    scope.update(overrides)
    return scope


def _browse_result(issues, **overrides):
    result = {
        "issues": issues,
        "selected_issue_index": 0,
        "displayed_total": len(issues),
        "append": False,
        "next_start_at": len(issues),
        "can_load_more": False,
        "scope": _browse_scope(),
    }
    result.update(overrides)
    return result


def _complete_worker_result(**overrides):
    result = _browse_result(
        [{"keyId": "TV-2", "summary": "replacement"}],
        mode="analyze",
        worker_id=1,
        connected=True,
        status_state={"kind": "raw", "text": "Connected"},
        analysis_summary="replacement summary",
        analysis_summary_state={"kind": "raw", "text": "replacement summary"},
        analysis_actions=["Inspect TV-2"],
        assistant_message="replacement answer",
        assistant_timestamp="later",
    )
    result.update(overrides)
    return result


def test_browse_controller_replaces_and_appends_with_stable_deduplicated_order():
    controller = _browse_controller()
    controller.apply_result(
        _browse_result(
            [
                {"keyId": "TV-1", "summary": "one-old"},
                {"keyId": "TV-1", "summary": "one-new"},
                {"keyId": "TV-2", "summary": "two"},
            ],
            displayed_total=5,
            next_start_at=3,
            can_load_more=True,
        )
    )
    controller.apply_result(
        _browse_result(
            [
                {"keyId": "TV-2", "summary": "two-new"},
                {"keyId": "TV-3", "summary": "three-old"},
                {"keyId": "TV-3", "summary": "three-new"},
            ],
            append=True,
            displayed_total=5,
            next_start_at=5,
        )
    )

    assert [issue["keyId"] for issue in controller.issue_rows] == ["TV-1", "TV-2", "TV-3"]
    assert [issue["summary"] for issue in controller.issue_rows] == [
        "one-new",
        "two-new",
        "three-new",
    ]
    assert (controller.displayed_total, controller.next_start_at, controller.can_load_more) == (
        5,
        5,
        False,
    )


def test_browse_controller_owns_selection_detail_and_pagination_requests():
    controller = _browse_controller()
    refresh = controller.refresh_request(**_browse_scope())
    assert (refresh["board_id"], refresh["timeframe_id"], refresh["start_at"], refresh["append"]) == (
        "open_work",
        "last_30_days",
        0,
        False,
    )

    controller.apply_result(
        _browse_result(
            [{"keyId": "TV-1"}, {"keyId": "TV-2", "summary": "old"}],
            next_start_at=25,
            can_load_more=True,
            scope=_browse_scope(include_comments=True, labels_text="regression"),
        )
    )
    assert controller.select_issue(1) == "TV-2"
    assert controller.apply_detail({"keyId": "TV-2", "summary": "hydrated"}) is True
    assert controller.selected_issue["summary"] == "hydrated"
    assert controller.apply_detail({"keyId": "MISSING"}) is False
    request = controller.load_more_request()
    assert request is not None
    assert (request["start_at"], request["append"], request["include_comments"]) == (25, True, True)
    assert request["labels_text"] == "regression"


def test_browse_controller_projects_saved_filters_options_and_stats():
    controller = _browse_controller()
    controller.apply_saved_filters(
        [
            {"id": "10", "name": "Mine", "jql": "assignee = currentUser()"},
            {"id": "20", "name": "Open", "jql": "status = Open"},
        ]
    )
    controller.apply_result(
        _browse_result(
            [
                {"keyId": "TV-1", "status": "Blocked", "priority": "High"},
                {"keyId": "TV-2", "status": "Ready for Test", "priority": "Critical"},
                {"keyId": "TV-3", "status": "Resolved", "priority": "Low"},
            ],
            displayed_total=12,
        )
    )

    assert controller.quick_views[0] == {
        "id": "10",
        "label": "Mine",
        "query": "assignee = currentUser()",
    }
    assert controller.project_options[0]["id"] == "all_supported_projects"
    assert controller.board_options[0] == "board:open_work"
    assert controller.timeframe_options[1] == "timeframe:last_30_days"
    assert controller.status_options[1]["id"] == "in_progress"
    assert controller.priority_options[-1]["id"] == "low"
    assert controller.issue_type_options[-1]["id"] == "improvement"
    assert controller.quick_stats == {
        "matched": 12,
        "displayed": 3,
        "high_priority": 2,
        "blocked": 1,
        "ready_for_test": 2,
    }


def test_browse_controller_projects_scope_summary_and_resets_all_state():
    controller = _browse_controller()
    controller.apply_saved_filters([{"id": "10", "name": "Mine", "jql": "x"}])
    controller.apply_result(
        _browse_result(
            [{"keyId": "TV-1"}],
            scope=_browse_scope(raw_jql_text="project = TV"),
            can_load_more=True,
        )
    )
    assert controller.active_scope_summary(text_for=lambda text: text) == "JQL: project = TV"

    controller.reset()

    assert controller.issue_rows == []
    assert controller.selected_issue == {}
    assert controller.saved_filters == []
    assert controller.active_scope == {}
    assert controller.can_load_more is False


def test_browse_controller_keeps_filter_identity_when_display_language_changes():
    language = {"value": "en"}

    def label_for(kind, option_id):
        return f"{language['value']}:{kind}:{option_id}"

    controller = _BrowseHarness(label_for=label_for)
    controller.apply_result(
        _browse_result(
            [{"keyId": "TV-1"}],
            can_load_more=True,
            next_start_at=25,
            scope=_browse_scope(
                board_id="closed_bugs",
                board_label="en:board:closed_bugs",
                timeframe_id="last_90_days",
                timeframe_label="en:timeframe:last_90_days",
            ),
        )
    )

    language["value"] = "zh"
    load_more = controller.load_more_request()
    analysis = controller.analysis_scope(**controller.active_scope)

    assert load_more is not None
    assert (load_more["board_id"], load_more["timeframe_id"]) == (
        "closed_bugs",
        "last_90_days",
    )
    assert (analysis["board_id"], analysis["timeframe_id"]) == (
        "closed_bugs",
        "last_90_days",
    )
    assert load_more["board_label"] == "zh:board:closed_bugs"
    assert load_more["timeframe_label"] == "zh:timeframe:last_90_days"
    summary = controller.active_scope_summary(text_for=lambda text: text)
    assert "Workflow Preset: zh:board:closed_bugs" in summary
    assert "Time Window: zh:timeframe:last_90_days" in summary


def test_bridge_retry_reuses_canonical_scope_ids_after_language_change(
    monkeypatch, tmp_path
):
    language = {"value": "en"}

    def label_for(kind, option_id):
        return f"{language['value']}:{kind}:{option_id}"

    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(jira_bridge_module, "Thread", ImmediateThread)
    workspace = FakeWorkspace()
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=workspace)
    bridge._browse_option_label = label_for
    bridge._apply_browse_result(
        _browse_result(
            [],
            scope=_browse_scope(
                board_id="closed_bugs",
                board_label="en:board:closed_bugs",
                timeframe_id="last_90_days",
                timeframe_label="en:timeframe:last_90_days",
            ),
        )
    )

    language["value"] = "zh"
    bridge.retryPrompt("retry with stable scope")

    analyze_request = workspace.calls[-1][1]
    assert analyze_request["board_id"] == "closed_bugs"
    assert analyze_request["timeframe_id"] == "last_90_days"
    assert analyze_request["board_label"] == "zh:board:closed_bugs"
    assert analyze_request["timeframe_label"] == "zh:timeframe:last_90_days"


def test_browse_controller_deep_copies_nested_issue_detail_filter_and_option_state():
    controller = _browse_controller()
    issue = {
        "keyId": "TV-1",
        "comments": [{"body": "original"}],
        "links": [{"key": "TV-2"}],
        "labels": ["nightly"],
    }
    saved_filter = {"id": "10", "name": "Mine", "jql": "project = TV"}
    controller.apply_result(_browse_result([issue]))
    controller.apply_saved_filters([saved_filter])

    issue["comments"][0]["body"] = "mutated ingress"
    issue["links"][0]["key"] = "MUTATED"
    issue["labels"].append("mutated")
    saved_filter["name"] = "Mutated"
    rows = controller.issue_rows
    rows[0]["comments"][0]["body"] = "mutated egress"
    rows[0]["links"].append({"key": "TV-3"})
    rows[0]["labels"].clear()
    selected = controller.selected_issue
    selected["comments"].append({"body": "selected mutation"})
    filters = controller.saved_filters
    filters[0]["name"] = "Egress mutation"
    options = controller.project_options
    options[0]["label"] = "Mutated option"

    stable = controller.selected_issue
    assert stable["comments"] == [{"body": "original"}]
    assert stable["links"] == [{"key": "TV-2"}]
    assert stable["labels"] == ["nightly"]
    assert controller.saved_filters[0]["name"] == "Mine"
    assert controller.project_options[0]["label"] == "project:all_supported_projects"

    detail = {"keyId": "TV-1", "comments": [{"body": "hydrated"}], "links": []}
    controller.apply_detail(detail)
    detail["comments"][0]["body"] = "mutated detail"
    assert controller.selected_issue["comments"][0]["body"] == "hydrated"


def test_logout_invalidates_late_browse_analysis_detail_error_and_progress(monkeypatch, tmp_path):
    DeferredThread.pending = []
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(jira_bridge_module, "Thread", DeferredThread)
    auth = StatefulAuthBridge()
    bridge = jira_bridge_module.JiraBridge(auth, workspace_service=FakeWorkspace())
    bridge._apply_browse_result(_browse_result([{"keyId": "TV-1", "summary": "before"}]))
    scope = ("", "TV", "Open Work", "Last 30 Days", "", "", "bug", "", "", "", "")

    bridge.refreshScope(*scope, False, False, False)
    browse_worker_id = DeferredThread.pending[-1]._kwargs["worker_id"]
    bridge.submitPrompt("analyze", *scope, False, False, False)
    analysis_worker_id = DeferredThread.pending[-1]._kwargs["worker_id"]
    bridge.selectIssue(0, True, True)
    detail_thread = DeferredThread.pending[-1]
    detail_worker_id = detail_thread._kwargs["worker_id"]
    bridge._filters_loading = True
    auth.authenticated = False
    auth.credential = False

    bridge._handle_auth_changed()

    assert bridge._get_loading() is False
    assert bridge._get_filters_loading() is False
    assert bridge.statusText == "Signed out"
    assert bridge.issueRows() == []
    assert all(row.get("is_progress") is not True for row in bridge.conversationRows())

    detail_thread._target(**detail_thread._kwargs)
    for worker_id in (browse_worker_id, analysis_worker_id):
        bridge._on_worker_result(
            {
                "worker_id": worker_id,
                "issues": [{"keyId": "STALE-1"}],
                "displayed_total": 1,
                "next_start_at": 1,
                "scope": _browse_scope(),
            }
        )
    bridge._on_worker_error({"worker_id": analysis_worker_id, "message": "stale error"})
    bridge._on_progress_update({"worker_id": analysis_worker_id, "message": "stale progress"})
    bridge._on_filters_result(
        {
            "worker_id": 0,
            "filters": [{"id": "stale", "name": "Stale", "jql": "project = STALE"}],
        }
    )
    bridge._on_detail_result(
        {
            "worker_id": detail_worker_id,
            "issue": {"keyId": "TV-1", "summary": "stale detail"},
        }
    )

    assert bridge._get_loading() is False
    assert bridge.statusText == "Signed out"
    assert bridge.issueRows() == []
    assert bridge.savedFilters() == []
    assert all(row.get("is_progress") is not True for row in bridge.conversationRows())
    assert all(row.get("message") != "stale error" for row in bridge.conversationRows())


def test_detail_error_generation_never_collides_with_main_generation_after_logout(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    auth = StatefulAuthBridge()
    bridge = jira_bridge_module.JiraBridge(auth, workspace_service=FakeWorkspace())
    bridge._worker_seq = 1
    bridge._detail_worker_seq = 2
    bridge._detail_loading = True
    auth.authenticated = False
    auth.credential = False

    bridge._handle_auth_changed()

    assert (bridge._worker_seq, bridge._detail_worker_seq) == (2, 3)
    assert bridge.statusText == "Signed out"
    bridge._applyDetailError.emit({"worker_id": 2, "message": "stale detail error"})
    assert bridge.statusText == "Signed out"

    bridge._detail_loading = True
    bridge._applyDetailError.emit({"worker_id": 3, "message": "current detail error"})
    assert bridge._detail_loading is False
    assert bridge._get_loading() is False
    assert bridge.statusText == "Signed out"
    assert all(
        row.get("message") not in {"stale detail error", "current detail error"}
        for row in bridge.conversationRows()
    )

    current_bridge = jira_bridge_module.JiraBridge(
        StatefulAuthBridge(),
        workspace_service=FakeWorkspace(),
    )
    current_bridge._worker_seq = 1
    current_bridge._detail_worker_seq = 2
    current_bridge._set_loading(True)
    current_bridge._detail_loading = True
    current_bridge._applyDetailError.emit(
        {"worker_id": 2, "message": "current concurrent detail error"}
    )
    assert current_bridge._detail_loading is False
    assert current_bridge._get_loading() is True
    assert current_bridge.statusText == "Ready"


@pytest.mark.parametrize(
    "malformed",
    [
        {"analysis_actions": 1},
        {"analysis_summary": 1},
        {"assistant_message": ["not", "text"]},
        {"status_state": ["not", "state"]},
        {"mode": "invalid"},
    ],
)
def test_malformed_analysis_payload_is_rejected_before_any_result_state_mutates(
    malformed, monkeypatch, tmp_path
):
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=FakeWorkspace())
    bridge._apply_browse_result(
        _browse_result(
            [{"keyId": "TV-1", "summary": "original"}],
            scope=_browse_scope(board_id="open_work", timeframe_id="last_30_days"),
        )
    )
    original_issues = bridge.issueRows()
    original_scope = copy.deepcopy(bridge._active_scope)
    original_conversation = bridge.conversationRows()
    bridge._worker_seq = 1
    bridge._set_loading(True)

    bridge._on_worker_result(_complete_worker_result(**malformed))

    assert bridge.issueRows() == original_issues
    assert bridge._active_scope == original_scope
    assert bridge.conversationRows() == original_conversation
    assert bridge._get_loading() is False
    assert bridge.connected is False
    assert bridge.statusText.startswith("Jira request failed:")


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "not-a-result",
        {},
        {"worker_id": "not-an-integer"},
    ],
)
def test_unattributed_malformed_result_cannot_settle_the_active_generation(
    payload, monkeypatch, tmp_path
):
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=FakeWorkspace())
    bridge._worker_seq = 7
    bridge._set_loading(True)
    original_status = bridge.statusText
    original_rows = bridge.conversationRows()

    bridge._on_worker_result(payload)

    assert bridge._worker_seq == 7
    assert bridge._get_loading() is True
    assert bridge.statusText == original_status
    assert bridge.conversationRows() == original_rows


def test_browse_worker_envelopes_its_known_generation(monkeypatch, tmp_path):
    class MissingGenerationWorkspace(FakeWorkspace):
        def browse(self, **_kwargs):
            result = _complete_worker_result(mode="browse", assistant_message="")
            result.pop("worker_id")
            return result

    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    bridge = jira_bridge_module.JiraBridge(
        FakeAuthBridge(),
        workspace_service=MissingGenerationWorkspace(),
    )
    bridge._worker_seq = 4
    bridge._set_loading(True)

    bridge._browse_scope(request={}, worker_id=4)

    assert bridge._get_loading() is False
    assert [row["keyId"] for row in bridge.issueRows()] == ["TV-2"]


@pytest.mark.parametrize(
    ("template", "values"),
    [
        ("Broken {", {}),
        ("Positional {0}", {"0": "value"}),
        ("Unsafe {user.name}", {"user": "coco"}),
        ("Index {items[0]}", {"items": "value"}),
        ("Conversion {name!r}", {"name": "value"}),
        ("Specification {count:02d}", {"count": 2}),
        ("Missing {missing}", {}),
    ],
)
def test_unrenderable_display_state_is_rejected_before_browse_mutation(
    template, values, monkeypatch, tmp_path
):
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=FakeWorkspace())
    bridge._apply_browse_result(_browse_result([{"keyId": "TV-1"}]))
    bridge._worker_seq = 1
    bridge._set_loading(True)

    bridge._on_worker_result(
        _complete_worker_result(
            mode="browse",
            issues=[{"keyId": "TV-2"}],
            status_state={
                "kind": "translated",
                "template": template,
                "values": values,
            },
        )
    )

    assert [row["keyId"] for row in bridge.issueRows()] == ["TV-1"]
    assert bridge._get_loading() is False
    assert bridge.connected is False
    assert bridge.statusText.startswith("Jira request failed:")


def test_bridge_ignores_malformed_rows_and_settles_invalid_pagination_as_error(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(jira_bridge_module, "app_data_dir", lambda: tmp_path)
    bridge = jira_bridge_module.JiraBridge(FakeAuthBridge(), workspace_service=FakeWorkspace())
    bridge._worker_seq = 1
    bridge._set_loading(True)
    bridge._on_worker_result(
        _complete_worker_result(
            mode="browse",
            issues=[None, "not-a-row", {}, {"summary": "keyless"}, {"keyId": "TV-1"}],
            displayed_total=1,
            next_start_at=1,
            can_load_more=False,
            assistant_message="",
            analysis_summary="",
            analysis_summary_state={"kind": "raw", "text": ""},
        )
    )

    assert [row["keyId"] for row in bridge.issueRows()] == ["TV-1"]
    assert bridge._get_loading() is False

    bridge._worker_seq = 2
    bridge._set_loading(True)
    bridge._on_worker_result(
        _complete_worker_result(
            worker_id=2,
            issues=[{"keyId": "TV-2"}],
            displayed_total="not-a-number",
            next_start_at="also-bad",
        )
    )

    assert bridge._get_loading() is False
    assert bridge.connected is False
    assert bridge.statusText.startswith("Jira request failed:")
    assert [row["keyId"] for row in bridge.issueRows()] == ["TV-1"]


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


def test_jira_bridge_owns_browse_state_without_a_relocation_controller():
    source = Path("ui/example/bridge/JiraBridge.py").read_text(encoding="utf-8-sig")

    assert "JiraBrowseController" not in source
    assert not Path("jira/browse_controller.py").exists()


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
