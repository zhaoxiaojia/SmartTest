from jira.cache.issue_store import JiraIssueStore
from jira.core.models import IssueRecord
from jira.services.sync_service import JiraSyncService, build_incremental_jql


class FakeIssueService:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def search_records(self, jql, **kwargs):
        self.calls.append({"jql": jql, **kwargs})
        return list(self.records)


def test_build_incremental_jql_uses_overlap_window() -> None:
    query = build_incremental_jql(
        "project = ST",
        "2026-04-17T12:00:00.000+0000",
        overlap_minutes=10,
    )

    assert query == "(project = ST) AND updated >= '2026-04-17 11:50'"


def test_sync_scope_uses_cursor_and_updates_store(tmp_path) -> None:
    store = JiraIssueStore(tmp_path / "jira_issue_store.db")
    store.set_sync_state(
        "wifi_scope",
        cursor_updated="2026-04-17T12:00:00.000+0000",
        base_jql="project = ST",
    )
    issue_service = FakeIssueService(
        [
            IssueRecord(
                key="ST-1",
                id="10001",
                raw={"key": "ST-1"},
                fields={"summary": "Hello", "updated": "2026-04-17T12:03:00.000+0000"},
            )
        ]
    )
    sync_service = JiraSyncService(issue_service, store)

    result = sync_service.sync_scope(
        scope_key="wifi_scope",
        jql="project = ST",
        specs=["summary"],
    )

    assert result.full_sync is False
    assert result.previous_cursor == "2026-04-17T12:00:00.000+0000"
    assert result.next_cursor == "2026-04-17T12:03:00.000+0000"
    assert "updated >=" in issue_service.calls[0]["jql"]
    assert issue_service.calls[0]["specs"] == ["summary", "updated"]
    stored = store.get_record("ST-1")
    assert stored is not None
    assert stored.fields["summary"] == "Hello"
