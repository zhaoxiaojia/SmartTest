from pathlib import Path

from jira_tool.cache.issue_store import JiraIssueStore
from jira_tool.core.models import IssueRecord, IssueStoreQuery


def test_issue_store_round_trip(tmp_path: Path) -> None:
    store = JiraIssueStore(tmp_path / "jira_issue_store.db")
    records = [
        IssueRecord(
            key="ST-1",
            id="10001",
            raw={"key": "ST-1"},
            fields={"summary": "Hello", "updated": "2026-04-17T10:00:00.000+0000"},
        ),
        IssueRecord(
            key="ST-2",
            id="10002",
            raw={"key": "ST-2"},
            fields={"summary": "World", "updated": "2026-04-17T11:00:00.000+0000"},
        ),
    ]

    stored = store.upsert_records(records)
    latest = store.list_records(limit=1)
    loaded = store.get_record("ST-1")

    assert stored == 2
    assert latest[0].key == "ST-2"
    assert loaded is not None
    assert loaded.fields["summary"] == "Hello"


def test_issue_store_persists_sync_state(tmp_path: Path) -> None:
    store = JiraIssueStore(tmp_path / "jira_issue_store.db")

    store.set_sync_state(
        "wifi_scope",
        cursor_updated="2026-04-17T12:00:00.000+0000",
        base_jql="project = ST",
        extra={"mode": "incremental"},
    )
    state = store.get_sync_state("wifi_scope")

    assert state is not None
    assert state.cursor_updated == "2026-04-17T12:00:00.000+0000"
    assert state.base_jql == "project = ST"
    assert state.extra["mode"] == "incremental"


def test_issue_store_query_filters_indexed_columns(tmp_path: Path) -> None:
    store = JiraIssueStore(tmp_path / "jira_issue_store.db")
    store.upsert_records(
        [
            IssueRecord(
                key="ST-1",
                id="10001",
                raw={"key": "ST-1", "fields": {"summary": "WiFi roaming issue"}},
                fields={
                    "summary": "WiFi roaming issue",
                    "status": "Open",
                    "assignee": "Alex",
                    "priority": "High",
                    "updated": "2026-04-17T10:00:00.000+0000",
                },
            ),
            IssueRecord(
                key="ST-2",
                id="10002",
                raw={"key": "ST-2", "fields": {"summary": "Audio issue"}},
                fields={
                    "summary": "Audio issue",
                    "status": "Done",
                    "assignee": "Robin",
                    "priority": "Low",
                    "updated": "2026-04-17T11:00:00.000+0000",
                },
            ),
        ]
    )

    results = store.query_records(
        IssueStoreQuery(
            statuses=("Open",),
            assignees=("Alex",),
            text="wifi",
        )
    )

    assert [record.key for record in results] == ["ST-1"]
