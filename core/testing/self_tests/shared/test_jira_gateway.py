from __future__ import annotations

import pytest

from core.jira.commands import CreateIssueCommand
from core.jira.gateway import JiraGateway, JiraGatewayError


class RecordingApi:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def jql(self, jql, *, fields, start, limit, expand=None, validate_query=None):
        self.calls.append(("jql", jql, fields, start, limit, expand, validate_query))
        return {"issues": [], "startAt": start, "maxResults": limit, "total": 0}

    def issue_get_comments(self, issue_key):
        self.calls.append(("comments", issue_key))
        return {"comments": []}

    def get_issue(self, issue_key, *, fields=None, expand=None):
        self.calls.append(("issue", issue_key, fields, expand))
        return {"key": issue_key, "fields": {"description": "body"}}

    def create_issue(self, fields):
        self.calls.append(("create", fields))
        return {"id": "1", "key": "SH-1"}


def test_jira_gateway_search_requests_only_lightweight_core_fields() -> None:
    api = RecordingApi()
    gateway = JiraGateway("https://jira.example", "u", "p", api=api, page_size=25)

    gateway.search_issues("project = SH", page=2)

    call = api.calls[0]
    assert call[:4] == ("jql", "project = SH", list(JiraGateway.CORE_FIELDS), 50)
    assert "comment" not in call[2]
    assert "attachment" not in call[2]
    assert "description" not in call[2]


def test_jira_gateway_loads_comments_without_fetching_other_sections() -> None:
    api = RecordingApi()
    gateway = JiraGateway("https://jira.example", "u", "p", api=api)

    payload = gateway.load_issue_sections("SH-1", ("comments",))

    assert payload == {"comments": []}
    assert api.calls == [("comments", "SH-1")]


def test_jira_gateway_maps_create_command_to_atlassian_create_issue() -> None:
    api = RecordingApi()
    gateway = JiraGateway("https://jira.example", "u", "p", api=api)

    created = gateway.create_issue(CreateIssueCommand("SH", "Bug", "Broken", labels=("one",)))

    assert created["key"] == "SH-1"
    assert api.calls == [("create", {"project": {"key": "SH"}, "issuetype": {"name": "Bug"}, "summary": "Broken", "description": "", "labels": ["one"]})]


def test_jira_gateway_normalizes_third_party_failure() -> None:
    class BrokenApi(RecordingApi):
        def jql(self, *args, **kwargs):
            raise RuntimeError("secret transport detail")

    gateway = JiraGateway("https://jira.example", "u", "p", api=BrokenApi())

    with pytest.raises(JiraGatewayError) as error:
        gateway.search_issues("project = SH", page=0)

    assert error.value.code == "jira_search_failed"
