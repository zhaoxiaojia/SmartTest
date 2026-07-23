import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from support.jira_integration.core import IssueStore, UnifiedIssue
from tool.SmartHome.redmine import context_store


def _store(issue_id: str, *, title: str = "", detail: bool = False) -> IssueStore:
    store = IssueStore(
        [
            UnifiedIssue(
                id=issue_id,
                key=issue_id,
                source_system="redmine",
                source_url=f"https://redmine/issues/{issue_id}",
                title=title,
                web_url=f"https://redmine/issues/{issue_id}",
                description="body" if detail else "",
                detail_state="loaded" if detail else "unloaded",
                comments=[{"id": "1", "body": "Original"}] if detail else [],
            )
        ]
    )
    store.select(issue_id)
    return store


def test_v2_view_round_trip_uses_unified_records_and_selected_id(monkeypatch, tmp_path):
    monkeypatch.setattr(context_store, "cache_path", lambda _account: tmp_path / "redmine.json")

    context_store.save_view(
        "alice",
        _store("61043", title="panel issue", detail=True),
        filters={"project": "BDS", "status": "Closed", "type": "Bug"},
    )
    loaded = context_store.load_view("alice")

    assert [issue.id for issue in loaded["issue_list"]] == ["61043"]
    assert loaded["issue_list"][0].description == "body"
    assert loaded["selected_issue_id"] == "61043"
    assert loaded["filters"]["status"] == "Closed"
    assert context_store.load_filters("alice")["type"] == "Bug"


def test_v2_snapshot_has_one_issue_list_and_no_legacy_or_sensitive_sections(
    tmp_path, monkeypatch
):
    path = tmp_path / "alice.json"
    monkeypatch.setattr(context_store, "cache_path", lambda _account: path)

    context_store.save_view("alice", _store("search"), filters={"text": "panel"})
    context_store.save_quick_view("alice", "my_assigned", _store("mine"), filters={})
    context_store.save_project_options("alice", [{"id": "p1"}])
    context_store.save_watched_issue_ids("alice", ["3", "2", "3"])

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {
        "version",
        "account",
        "updated_at",
        "issue_list",
        "selected_issue_id",
        "filters",
        "quick_views",
        "project_options",
        "watched_issue_ids",
    }
    assert payload["version"] == 2 and payload["account"] == "alice"
    assert json.dumps(payload).count('"issue_list"') == 1
    assert payload["quick_views"]["my_assigned"]["issue_ids"] == ["mine"]
    assert "issue_list" not in payload["quick_views"]["my_assigned"]
    assert payload["filters"]["text"] == "panel"
    assert payload["project_options"] == [{"id": "p1"}]
    assert payload["watched_issue_ids"] == ["3", "2"]
    serialized = json.dumps(payload)
    assert "password" not in serialized
    assert "draft" not in serialized
    assert "temporary_path" not in serialized


def test_quick_views_are_account_specific_and_not_overwritten_by_search(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        context_store,
        "cache_path",
        lambda account: tmp_path / f"{account}.json",
    )

    context_store.save_quick_view("alice", "my_assigned", _store("mine"), filters={})
    context_store.save_view("alice", _store("search"), filters={"text": "search"})
    context_store.save_quick_view("bob", "my_assigned", _store("bob"), filters={})

    alice = context_store.load_quick_view("alice", "my_assigned")
    bob = context_store.load_quick_view("bob", "my_assigned")
    assert [issue.id for issue in alice["issue_list"]] == ["mine"]
    assert [issue.id for issue in bob["issue_list"]] == ["bob"]
    assert [issue.id for issue in context_store.load_view("alice")["issue_list"]] == ["search"]


def test_non_v2_wrong_account_and_damaged_snapshots_return_no_usable_data(
    tmp_path, monkeypatch
):
    path = tmp_path / "alice.json"
    monkeypatch.setattr(context_store, "cache_path", lambda _account: path)

    path.write_text(json.dumps({"version": 1, "issueRows": [{"id": "old"}]}), encoding="utf-8")
    assert context_store.load_view_payload("alice") is None
    assert context_store.load_view("alice") is None
    assert context_store.load_quick_view("alice", "my_assigned") is None
    assert context_store.load_filters("alice") == {}
    assert context_store.load_project_options("alice") == []
    assert context_store.load_watched_issue_ids("alice") == []

    context_store.save_view("alice", _store("fresh"), filters={})
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["account"] = "bob"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert context_store.load_view("alice") is None

    path.write_text("{damaged", encoding="utf-8")
    assert context_store.load_view_payload("alice") is None
    context_store.save_project_options("alice", [{"id": "recovered"}])
    assert context_store.load_project_options("alice") == [{"id": "recovered"}]


def test_loaded_snapshots_are_defensive_and_malformed_issue_lists_are_rejected(
    tmp_path, monkeypatch
):
    path = tmp_path / "alice.json"
    monkeypatch.setattr(context_store, "cache_path", lambda _account: path)
    context_store.save_view("alice", _store("1", detail=True), filters={})

    loaded = context_store.load_view("alice")
    loaded["issue_list"][0].comments[0]["body"] = "Changed"
    reloaded = context_store.load_view("alice")
    assert reloaded["issue_list"][0].comments[0]["body"] == "Original"

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["password"] = "must-not-load"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert context_store.load_view("alice") is None

    payload.pop("password")
    payload["issue_list"].append("not-an-issue")
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert context_store.load_view("alice") is None

    payload["issue_list"] = [payload["issue_list"][0], payload["issue_list"][0]]
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert context_store.load_view("alice") is None


@pytest.mark.parametrize("blank_id", ["", " ", "\t"])
def test_v2_snapshot_rejects_blank_issue_identity(tmp_path, monkeypatch, blank_id):
    path = tmp_path / "alice.json"
    monkeypatch.setattr(context_store, "cache_path", lambda _account: path)
    context_store.save_view("alice", _store("1"), filters={})
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["issue_list"][0]["id"] = blank_id
    payload["selected_issue_id"] = blank_id
    payload["quick_views"]["__default__"]["issue_ids"] = [blank_id]
    payload["quick_views"]["__default__"]["selected_issue_id"] = blank_id
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert context_store.load_view_payload("alice") is None


def test_concurrent_updates_remain_atomic_and_keep_all_v2_sections(
    tmp_path, monkeypatch
):
    path = tmp_path / "alice.json"
    monkeypatch.setattr(context_store, "cache_path", lambda _account: path)
    operations = [
        lambda: context_store.save_view("alice", _store("view"), filters={"subject": "panel"}),
        lambda: context_store.save_quick_view("alice", "my_assigned", _store("quick"), filters={}),
        lambda: context_store.save_project_options("alice", [{"id": "project"}]),
        lambda: context_store.save_watched_issue_ids("alice", ["9"]),
    ]

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda operation: operation(), operations))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert payload["project_options"] == [{"id": "project"}]
    assert payload["watched_issue_ids"] == ["9"]
    assert [issue.id for issue in context_store.load_view("alice")["issue_list"]] == ["view"]
    assert [
        issue.id
        for issue in context_store.load_quick_view("alice", "my_assigned")["issue_list"]
    ] == ["quick"]


@pytest.mark.parametrize(
    ("path", "bad_value"),
    [
        (("issue_list", 0, "project"), []),
        (("issue_list", 0, "comments"), ["not-a-map"]),
        (("filters", "status"), 7),
        (("project_options",), ["not-a-map"]),
        (("watched_issue_ids",), [9]),
        (("quick_views", "my_assigned", "issue_ids"), [1]),
        (("quick_views", "my_assigned", "filters", "type"), ["Bug"]),
    ],
)
def test_v2_snapshot_rejects_wrong_nested_contract_types(
    tmp_path, monkeypatch, path, bad_value
):
    cache_file = tmp_path / "alice.json"
    monkeypatch.setattr(context_store, "cache_path", lambda _account: cache_file)
    context_store.save_view("alice", _store("1"), filters={})
    context_store.save_quick_view("alice", "my_assigned", _store("1"), filters={})
    context_store.save_project_options("alice", [{"id": "p", "label": "Project"}])
    context_store.save_watched_issue_ids("alice", ["1"])
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad_value
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    assert context_store.load_view_payload("alice") is None


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("analysis", {"elapsed_hours": {"hours": 8}}),
        ("analysis", {"threshold_hours": []}),
        ("analysis", {"stale_elapsed_hours": "8"}),
        ("analysis", {"risk": {"level": "red"}}),
        ("analysis", {"responsibility_type": []}),
        ("project", {"identifier": {"value": "sh"}}),
        ("status", {"name": ["New"]}),
        ("assignee", {"name": {"display": "Alice"}}),
        ("clone", {"state": "cloned", "issue_key": "SH-1", "issue_url": "", "checked": "yes"}),
        ("detail_fields", [{"label": {"text": "Status"}, "value": "New"}]),
        ("extra_sections", [{"title": "Agile", "fields": {"label": "Board"}}]),
        ("comments", [{"author": ["Alice"], "body": "Investigating"}]),
        ("attachments", [{"filename": "trace.log", "size": {"bytes": 10}}]),
    ],
)
def test_v2_snapshot_rejects_projection_unsafe_nested_values(
    tmp_path, monkeypatch, field_name, bad_value
):
    cache_file = tmp_path / "alice.json"
    monkeypatch.setattr(context_store, "cache_path", lambda _account: cache_file)
    context_store.save_view("alice", _store("1", detail=True), filters={})
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["issue_list"][0][field_name] = bad_value
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    assert context_store.load_view_payload("alice") is None


def test_saving_unloaded_shell_does_not_downgrade_loaded_canonical_record(
    tmp_path, monkeypatch
):
    cache_file = tmp_path / "alice.json"
    monkeypatch.setattr(context_store, "cache_path", lambda _account: cache_file)
    loaded = _store("1", title="Loaded", detail=True)
    loaded.patch(
        "1",
        attachments=[{"id": "a", "filename": "trace.log"}],
        clone={
            "state": "cloned",
            "issue_key": "SH-1",
            "issue_url": "https://jira/browse/SH-1",
        },
    )
    shell = _store("1", title="Fresh list title", detail=False)

    context_store.save_view("alice", loaded, filters={})
    context_store.save_quick_view("alice", "my_assigned", shell, filters={})
    restored = context_store.load_quick_view("alice", "my_assigned")["issue_list"][0]

    assert restored.title == "Fresh list title"
    assert restored.detail_state == "loaded"
    assert restored.description == "body"
    assert restored.comments == [{"id": "1", "body": "Original"}]
    assert restored.attachments == [{"id": "a", "filename": "trace.log"}]
    assert restored.clone["state"] == "cloned"
    assert restored.clone["issue_key"] == "SH-1"


def test_cache_path_disambiguates_accounts_with_same_sanitized_prefix():
    first = context_store.cache_path("alice/support")
    second = context_store.cache_path("alice?support")

    assert first != second
    assert first.parent == second.parent
    assert first.name.startswith("alice_support")
    assert second.name.startswith("alice_support")


def test_v2_writers_reject_malformed_nested_values_instead_of_normalizing(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        context_store,
        "cache_path",
        lambda _account: tmp_path / "alice.json",
    )

    with pytest.raises(TypeError):
        context_store.save_view("alice", _store("1"), filters={"status": 7})
    with pytest.raises(TypeError):
        context_store.save_project_options("alice", ["not-a-map"])
    with pytest.raises(TypeError):
        context_store.save_watched_issue_ids("alice", [9])
