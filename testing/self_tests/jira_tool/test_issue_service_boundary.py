from jira_tool.core.models import SearchPage
from jira_tool.fields.registry import build_default_registry
from jira_tool.services.issue_service import JiraIssueService
from jira_tool.services.specs import browse_specs


class FakeClient:
    def __init__(self):
        self.search_calls = []

    def search_page(self, jql, **kwargs):
        self.search_calls.append((jql, kwargs))
        return SearchPage(
            issues=[{"id": "1", "key": "TV-1", "fields": {"summary": "Black screen"}}],
            start_at=0,
            max_results=25,
            total=1,
        )

    def fetch_favourite_filters(self):
        return [{"id": "7", "name": "My Bugs", "jql": "assignee = currentUser()"}]


def test_issue_service_owns_page_projection_and_saved_filter_transport():
    client = FakeClient()
    service = JiraIssueService(client, registry=build_default_registry())

    page, records = service.search_page_records(
        "project = TV",
        specs=browse_specs(),
        start_at=0,
        max_results=25,
    )

    assert page.total == 1
    assert records[0].key == "TV-1"
    assert client.search_calls[0][0] == "project = TV"
    assert "summary" in client.search_calls[0][1]["fields"]
    assert service.fetch_favourite_filters()[0]["id"] == "7"


def test_build_fetch_plan_defers_heavy_fields_by_default():
    service = JiraIssueService(FakeClient(), registry=build_default_registry())

    plan = service.build_fetch_plan(["summary", "changelog_statuses"])

    assert [spec.name for spec in plan.active_specs] == ["summary"]
    assert [spec.name for spec in plan.deferred_specs] == ["changelog_statuses"]
