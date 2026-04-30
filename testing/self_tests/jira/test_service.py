from jira_tool.cache.issue_store import JiraIssueStore
from jira_tool.core.models import IssueRecord, IssueStoreQuery
from jira_tool.fields.specs import FieldSpec
from jira_tool.services.issue_service import JiraIssueService


class FakeClient:
    def __init__(self):
        self.search_calls = []
        self.fetch_calls = []

    def search_all(self, *args, **kwargs):
        self.search_calls.append(kwargs)
        return [
            {
                "id": "10001",
                "key": "ST-1",
                "fields": {
                    "summary": "First",
                    "status": {"name": "Open"},
                },
            },
            {
                "id": "10002",
                "key": "ST-2",
                "fields": {
                    "summary": "Second",
                    "status": {"name": "Done"},
                },
            },
        ]

    def fetch_issue(self, issue_key, *, fields=None, expand=None):
        self.fetch_calls.append({"issue_key": issue_key, "fields": fields, "expand": expand})
        return {
            "id": "10001",
            "key": issue_key,
            "fields": {
                "summary": "First",
                "status": {"name": "Open"},
            },
            "changelog": {
                "histories": [
                    {"items": [{"toString": "Open"}]},
                    {"items": [{"toString": "Verified"}]},
                ]
            },
        }


def test_search_records_projects_issue_fields() -> None:
    client = FakeClient()
    service = JiraIssueService(client)
    specs = [
        FieldSpec(name="summary", path="fields.summary"),
        FieldSpec(name="status", path="fields.status.name"),
    ]

    records = service.search_records("project = ST", specs=specs)

    assert [record.key for record in records] == ["ST-1", "ST-2"]
    assert records[0].fields == {"summary": "First", "status": "Open"}
    assert records[1].fields == {"summary": "Second", "status": "Done"}
    assert client.search_calls[0]["fields"] == ["key", "status", "summary"]


def test_search_records_forwards_max_total_results() -> None:
    client = FakeClient()
    service = JiraIssueService(client)

    service.search_records("project = ST", specs=["summary"], max_total_results=1000)

    assert client.search_calls[0]["max_total_results"] == 1000


def test_hydrate_issue_fetches_heavy_fields_when_requested() -> None:
    client = FakeClient()
    service = JiraIssueService(client)

    record = service.hydrate_issue("ST-1", specs=["summary", "changelog_statuses"])

    assert record.key == "ST-1"
    assert record.fields["summary"] == "First"
    assert record.fields["changelog_statuses"] == ["Open", "Verified"]
    assert client.fetch_calls[0]["fields"] == ["key", "summary"]
    assert client.fetch_calls[0]["expand"] == ["changelog"]


def test_search_local_records_reprojects_from_store(tmp_path) -> None:
    store = JiraIssueStore(tmp_path / "jira_issue_store.db")
    store.upsert_records(
        [
            IssueRecord(
                key="ST-9",
                id="10009",
                raw={
                    "id": "10009",
                    "key": "ST-9",
                    "fields": {
                        "summary": "WiFi issue",
                        "status": {"name": "Open"},
                        "assignee": {"displayName": "Alex"},
                    },
                },
                fields={
                    "summary": "WiFi issue",
                    "status": "Open",
                    "assignee": "Alex",
                    "updated": "2026-04-17T10:00:00.000+0000",
                },
            )
        ]
    )
    client = FakeClient()
    service = JiraIssueService(client, issue_store=store)

    records = service.search_local_records(
        store_query=IssueStoreQuery(text="wifi"),
        specs=["summary", "status", "assignee"],
    )

    assert len(records) == 1
    assert records[0].fields == {"summary": "WiFi issue", "status": "Open", "assignee": "Alex"}
