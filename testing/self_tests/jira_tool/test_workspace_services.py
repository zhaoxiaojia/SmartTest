from dataclasses import fields

from jira_tool.core.models import IssueRecord, SearchPage
from jira_tool.fields.registry import build_default_registry
from jira_tool.services.browse_service import JiraBrowseService
from jira_tool.services.requests import JiraBrowseRequest
from jira_tool.services.workspace import JiraWorkspaceService


class FakeIssueService:
    def __init__(self):
        self.page_calls = []

    def build_fetch_plan(self, specs, *, include_heavy=False):
        return build_default_registry().build_plan(specs, include_heavy=include_heavy)

    def search_page_records(self, jql, *, specs, start_at, max_results, include_heavy=False):
        self.page_calls.append((jql, start_at, max_results))
        page = SearchPage(issues=[{"key": "TV-1"}], start_at=start_at, max_results=max_results, total=1)
        record = IssueRecord(
            key="TV-1",
            id="1",
            raw={"key": "TV-1"},
            fields={"summary": "Black screen", "status": "Open", "priority": "High"},
        )
        return page, [record]

    def fetch_favourite_filters(self):
        return [
            {"id": "7", "name": "My Bugs", "jql": "assignee = currentUser()"},
            {"id": "7", "name": "Duplicate", "jql": "project = TV"},
            {"id": "", "name": "Invalid", "jql": "project = TV"},
        ]

    def hydrate_issue(self, issue_key, *, specs):
        return IssueRecord(key=issue_key, id="1", raw={"key": issue_key}, fields={"summary": "Black screen"})


def make_browse_request():
    return JiraBrowseRequest(
        worker_id=3,
        selected_issue_index=0,
        raw_jql_text="project = TV",
        project_ids_csv="",
        board_id="",
        board_label="",
        timeframe_id="",
        timeframe_label="",
        status_ids_csv="",
        priority_ids_csv="",
        issue_type_ids_csv="",
        keyword_text="",
        assignee_text="",
        reporter_text="",
        labels_text="",
        include_comments=False,
        include_links=False,
        only_mine=False,
        start_at=0,
        append=False,
        translated_state=lambda key, **kwargs: {"key": key, "args": kwargs},
    )


def test_browse_service_uses_public_issue_service_boundary():
    issue_service = FakeIssueService()
    service = JiraBrowseService(base_url="https://jira.example", issue_service=issue_service)

    result = service.browse(make_browse_request())

    assert issue_service.page_calls == [("project = TV", 0, 25)]
    assert result["mode"] == "browse"
    assert result["issues"][0]["keyId"] == "TV-1"


def test_saved_filters_are_normalized_without_private_client_access():
    issue_service = FakeIssueService()
    service = JiraBrowseService(base_url="https://jira.example", issue_service=issue_service)

    assert service.fetch_saved_filters() == [
        {"id": "7", "name": "My Bugs", "jql": "assignee = currentUser()"}
    ]


class RecordingBrowseService:
    pass


class RecordingAnalysisService:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def analyze(self, request):
        self.requests.append(request)
        return self.result


def analysis_arguments(worker_id=9):
    browse_request = make_browse_request()
    values = {field.name: getattr(browse_request, field.name) for field in fields(browse_request)}
    values.pop("selected_issue_index")
    values.pop("start_at")
    values.pop("append")
    values.update(
        worker_id=worker_id,
        project_ids_csv="TV",
        include_user_message=True,
        prompt="summarize blockers",
        raw_state=lambda key: {"key": key},
        assistant_timestamp="2026-07-15 10:00:00",
    )
    return values


def test_workspace_facade_delegates_analysis_without_rebuilding_business_logic():
    analysis = RecordingAnalysisService(result={"mode": "analyze", "worker_id": 9})
    workspace = JiraWorkspaceService(
        browse_service=RecordingBrowseService(),
        analysis_service=analysis,
    )

    result = workspace.analyze(**analysis_arguments(worker_id=9))

    assert result == {"mode": "analyze", "worker_id": 9}
    assert analysis.requests[0].prompt == "summarize blockers"
    assert analysis.requests[0].project_ids_csv == "TV"
