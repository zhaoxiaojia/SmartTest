from __future__ import annotations

import json

import pytest

from support.jira_integration.core.issue_store import IssueStore, UnifiedIssue


def _issue(issue_id: str, *, title: str = "") -> UnifiedIssue:
    return UnifiedIssue(id=issue_id, key=issue_id, title=title)


def test_unified_issue_defaults_and_json_round_trip() -> None:
    issue = UnifiedIssue(
        id="42",
        key="RM-42",
        source_system="redmine",
        source_url="https://redmine.example/issues/42",
        title="Playback fails",
        web_url="https://redmine.example/issues/42",
        project={"id": "7", "name": "SmartTV"},
        status={"id": "1", "name": "New"},
        issue_type={"id": "2", "name": "Bug"},
        priority={"id": "3", "name": "High"},
        assignee={"id": "4", "name": "Coco"},
        reporter={"id": "5", "name": "Mason"},
        created_at="2026-07-20T10:00:00Z",
        updated_at="2026-07-22T10:00:00Z",
        description="Steps",
        detail_fields=[{"label": "Resolution", "value": ""}],
        people_fields=[{"label": "Manager", "value": "Atlas"}],
        date_fields=[{"label": "Due", "value": "2026-07-30"}],
        extra_sections=[{"title": "Agile", "fields": []}],
        comments=[{"id": "6", "body": "Investigating"}],
        attachments=[{"id": "7", "filename": "log.txt"}],
        detail_state="loaded",
        detail_error="",
        clone={"state": "not_cloned"},
        analysis={"risk": "yellow"},
    )

    serialized = issue.to_dict()
    round_tripped = UnifiedIssue.from_dict(json.loads(json.dumps(serialized)))

    assert round_tripped == issue
    assert UnifiedIssue().to_dict() == {
        "id": "",
        "key": "",
        "source_system": "",
        "source_url": "",
        "title": "",
        "web_url": "",
        "project": {},
        "status": {},
        "issue_type": {},
        "priority": {},
        "assignee": {},
        "reporter": {},
        "created_at": "",
        "updated_at": "",
        "description": "",
        "detail_fields": [],
        "people_fields": [],
        "date_fields": [],
        "extra_sections": [],
        "comments": [],
        "attachments": [],
        "detail_state": "unloaded",
        "detail_error": "",
        "clone": {},
        "analysis": {},
    }


def test_unified_issue_rejects_invalid_detail_state() -> None:
    with pytest.raises(ValueError, match="detail_state"):
        UnifiedIssue(detail_state="ready")


def test_replace_all_preserves_order_and_rejects_duplicate_ids_atomically() -> None:
    store = IssueStore()
    store.replace_all([_issue("2"), _issue("1")])

    assert [issue.id for issue in store.issue_list] == ["2", "1"]

    with pytest.raises(ValueError, match="Duplicate issue id: 3"):
        store.replace_all([_issue("3"), _issue("3")])

    assert [issue.id for issue in store.issue_list] == ["2", "1"]


@pytest.mark.parametrize("blank_id", ["", " ", "\t\r\n"])
def test_store_rejects_blank_issue_ids_atomically(blank_id: str) -> None:
    store = IssueStore([_issue("kept")])

    with pytest.raises(ValueError, match="Issue id cannot be empty"):
        store.replace_all([_issue(blank_id)])
    assert [issue.id for issue in store.issue_list] == ["kept"]

    with pytest.raises(ValueError, match="Issue id cannot be empty"):
        store.upsert(_issue(blank_id))
    assert [issue.id for issue in store.issue_list] == ["kept"]


def test_upsert_and_patch_preserve_existing_positions() -> None:
    store = IssueStore([_issue("1"), _issue("2")])

    store.upsert(_issue("1", title="updated"))
    store.upsert(_issue("3"))
    patched = store.patch("2", title="patched", analysis={"risk": "red"})

    assert [issue.id for issue in store.issue_list] == ["1", "2", "3"]
    assert store.get("1") == _issue("1", title="updated")
    assert patched.title == "patched"
    assert patched.analysis == {"risk": "red"}


def test_unknown_ids_are_handled_deterministically() -> None:
    store = IssueStore([_issue("1")])

    assert store.get("missing") is None
    with pytest.raises(KeyError, match="missing"):
        store.patch("missing", title="ignored")
    with pytest.raises(KeyError, match="missing"):
        store.select("missing")


def test_snapshot_and_reads_cannot_mutate_store_records() -> None:
    store = IssueStore(
        [
            UnifiedIssue(
                id="1",
                key="RM-1",
                project={"name": "SmartTV"},
                comments=[{"id": "2", "body": "Original"}],
            )
        ]
    )
    store.select("1")

    snapshot = store.snapshot()
    snapshot["issue_list"][0]["project"]["name"] = "Changed"
    snapshot["issue_list"][0]["comments"][0]["body"] = "Changed"
    fetched = store.get("1")
    assert fetched is not None
    fetched.project["name"] = "Also changed"

    current = store.snapshot()
    assert current["selected_id"] == "1"
    assert current["issue_list"][0]["project"]["name"] == "SmartTV"
    assert current["issue_list"][0]["comments"][0]["body"] == "Original"


def test_selection_uses_identity_without_owning_a_duplicate_record() -> None:
    store = IssueStore([_issue("1"), _issue("2")])

    selected = store.select("2")
    store.patch("2", title="patched")

    assert selected.id == "2"
    assert store.selected_id == "2"
    assert store.selected_issue == _issue("2", title="patched")

    store.replace_all([_issue("1")])
    assert store.selected_id is None
    assert store.selected_issue is None

    assert store.select(None) is None
