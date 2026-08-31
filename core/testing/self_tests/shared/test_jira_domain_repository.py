from __future__ import annotations

from core.domain.detail import DetailState
from core.domain.values import NamedValue, PersonRef
from core.jira.domain import IssueDetails
from core.jira.mapper import JiraIssueMapper
from core.jira.repository import IssueRepository


ISSUE_PAYLOAD = {
    "id": "1001",
    "key": "SH-1",
    "self": "https://jira.example/rest/api/2/issue/1001",
    "fields": {
        "summary": "Lightweight issue",
        "project": {"id": "10", "key": "SH", "name": "Smart Home"},
        "status": {"id": "3", "name": "Open"},
        "issuetype": {"id": "1", "name": "Bug"},
        "priority": {"id": "2", "name": "P2"},
        "assignee": {"accountId": "a1", "name": "alice", "displayName": "Alice"},
        "reporter": {"accountId": "b1", "name": "bob", "displayName": "Bob"},
        "created": "2026-08-01T10:00:00.000+0000",
        "updated": "2026-08-02T11:00:00.000+0000",
        "labels": ["one"],
        "description": "must stay unloaded in list mapping",
        "comment": {"comments": [{"id": "c0", "body": "not requested"}]},
        "attachment": [{"id": "a0", "filename": "not-requested.txt"}],
    },
}


class RecordingJiraGateway:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def search_issues(self, query, page):
        self.calls.append(("search", query, page))
        return {"issues": [ISSUE_PAYLOAD], "startAt": 0, "maxResults": 25, "total": 1}

    def get_issue(self, issue_key):
        self.calls.append(("get", issue_key))
        return ISSUE_PAYLOAD

    def load_issue_sections(self, issue_key, sections):
        self.calls.append(("details", issue_key, sections))
        return {
            "comments": [{"id": "c1", "body": "Loaded comment", "author": {"name": "alice"}}],
        }


def test_jira_mapper_creates_lightweight_issue_with_unloaded_details() -> None:
    issue = JiraIssueMapper("https://jira.example").from_search(ISSUE_PAYLOAD)

    assert issue.identity.key == "SH-1"
    assert issue.project.key == "SH"
    assert issue.summary == "Lightweight issue"
    assert issue.comments.state is DetailState.UNLOADED
    assert issue.attachments.state is DetailState.UNLOADED
    assert issue.description.state is DetailState.UNLOADED


def test_jira_mapper_maps_creator_and_components_as_core_issue_fields() -> None:
    payload = {
        **ISSUE_PAYLOAD,
        "fields": {
            **ISSUE_PAYLOAD["fields"],
            "creator": {"name": "carol", "displayName": "Carol"},
            "components": [
                {"id": "10", "name": "Video"},
                {"id": "11", "name": "Audio"},
            ],
        },
    }

    issue = JiraIssueMapper("https://jira.example").from_search(payload)

    assert issue.creator == PersonRef("carol", "carol", "Carol")
    assert issue.components == (
        NamedValue("10", "Video"), NamedValue("11", "Audio"),
    )


def test_issue_repository_search_does_not_fetch_any_detail_section() -> None:
    gateway = RecordingJiraGateway()
    repository = IssueRepository(gateway, JiraIssueMapper("https://jira.example"))

    page = repository.search("project = SH", page=0)

    assert [issue.identity.key for issue in page.issues] == ["SH-1"]
    assert gateway.calls == [("search", "project = SH", 0)]


def test_issue_repository_loads_only_declared_section() -> None:
    gateway = RecordingJiraGateway()
    mapper = JiraIssueMapper("https://jira.example")
    repository = IssueRepository(gateway, mapper)
    issue = mapper.from_search(ISSUE_PAYLOAD)

    loaded = repository.load_details(issue, IssueDetails(comments=True))

    assert gateway.calls == [("details", "SH-1", ("comments",))]
    assert loaded.comments.state is DetailState.LOADED
    assert loaded.comments.value[0].body == "Loaded comment"
    assert loaded.attachments.state is DetailState.UNLOADED
    assert loaded.description.state is DetailState.UNLOADED
