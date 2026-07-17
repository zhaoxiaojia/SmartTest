from support.jira_integration.core.models import CreateIssueRequest
from support.jira_integration.services.create_issue_service import CreateIssueService
from support.jira_integration.transport.client import JiraClient


class FakeClient:
    def __init__(self, search_issues=None, pages=None):
        self.search_issues = search_issues or []
        self.pages = list(pages or [])
        self.created_payloads = []
        self.search_calls = []

    def search_page(self, jql, **kwargs):
        self.search_calls.append((jql, kwargs))
        issues = self.pages.pop(0) if self.pages else self.search_issues

        class Page:
            pass

        Page.issues = issues
        Page.total = len(issues)
        return Page()

    def create_issue(self, payload):
        self.created_payloads.append(payload)
        return {"id": "10001", "key": "TV-9", "self": "https://jira/rest/api/2/issue/10001"}


def test_create_issue_skips_existing_third_party_bug_by_source_label():
    client = FakeClient(search_issues=[{"id": "1", "key": "TV-1", "fields": {"summary": "existing"}}])
    service = CreateIssueService(client)
    request = CreateIssueRequest(
        project_key="TV",
        issue_type="Bug",
        summary="Panel issue",
        description="desc",
        source_system="redmine",
        source_id="61043",
    )

    result = service.create_issue(request)

    assert result.created is False
    assert result.existing_key == "TV-1"
    assert client.created_payloads == []
    assert 'labels = "source_redmine"' in client.search_calls[0][0]
    assert 'labels = "redmine_61043"' in client.search_calls[0][0]


def test_check_issue_by_external_url_returns_existing_issue_link():
    client = FakeClient(search_issues=[{"id": "1", "key": "SH-26384", "fields": {"summary": "cloned"}}])
    service = CreateIssueService(client, browse_base_url="https://jira.amlogic.com")

    existing = service.check_issue_by_external_url(
        project_key="SH",
        external_url="https://support.amlogic.com/issues/62003",
    )

    assert existing.key == "SH-26384"
    assert existing.web_url == "https://jira.amlogic.com/browse/SH-26384"
    assert 'project = "SH"' in client.search_calls[0][0]
    assert '"Attachment links" = "https://support.amlogic.com/issues/62003"' in client.search_calls[0][0]


def test_check_issue_by_external_url_falls_back_to_text_search():
    client = FakeClient(pages=[[], [{"id": "1", "key": "SH-26384", "fields": {"summary": "cloned"}}]])
    service = CreateIssueService(client, browse_base_url="https://jira.amlogic.com")

    existing = service.check_issue_by_external_url(
        project_key="SH",
        external_url="https://support.amlogic.com/issues/54345",
    )

    assert existing.key == "SH-26384"
    assert len(client.search_calls) == 2
    assert '"Attachment links" = "https://support.amlogic.com/issues/54345"' in client.search_calls[0][0]
    assert 'text ~ "https://support.amlogic.com/issues/54345"' in client.search_calls[1][0]


def test_create_issue_posts_required_and_optional_fields_when_no_duplicate_exists():
    client = FakeClient()
    service = CreateIssueService(client)
    request = CreateIssueRequest(
        project_key="TV",
        issue_type="Feature",
        summary="Support request",
        description="desc",
        priority="High",
        assignee="alice",
        labels=("customer",),
        components=("Panel",),
        source_system="redmine",
        source_id="62000",
        source_url="https://support/issues/62000",
    )

    result = service.create_issue(request)

    assert result.created is True
    assert result.issue_key == "TV-9"
    assert client.created_payloads == [
        {
            "fields": {
                "project": {"key": "TV"},
                "issuetype": {"name": "Feature"},
                "summary": "Support request",
                "description": "desc\n\nSource: redmine\nSource ID: 62000\nSource URL: https://support/issues/62000",
                "priority": {"name": "High"},
                "assignee": {"name": "alice"},
                "labels": ["customer", "clone_external", "source_redmine", "redmine_62000"],
                "components": [{"name": "Panel"}],
            }
        }
    ]


def test_jira_client_create_issue_posts_to_issue_resource():
    class RecordingClient(JiraClient):
        def __init__(self):
            self.calls = []

        def _api_path(self, suffix):
            return f"https://jira/rest/api/2/{suffix}"

        def _request(self, method, url, *, params=None, json=None):
            self.calls.append((method, url, params, json))

            class Response:
                data = {"id": "10001", "key": "TV-9"}

            return Response()

    client = RecordingClient()
    result = client.create_issue({"fields": {"summary": "x"}})

    assert result == {"id": "10001", "key": "TV-9"}
    assert client.calls == [("POST", "https://jira/rest/api/2/issue", None, {"fields": {"summary": "x"}})]
