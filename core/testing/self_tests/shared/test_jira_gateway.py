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

    def get_all_fields(self):
        self.calls.append(("fields",))
        return [
            {"id": "customfield_101", "name": "Project ID"},
            {"id": "customfield_102", "name": "Software Release"},
            {"id": "customfield_103", "name": "Severity"},
        ]


def test_jira_gateway_search_requests_only_lightweight_core_fields() -> None:
    api = RecordingApi()
    gateway = JiraGateway("https://jira.example", "u", "p", api=api, page_size=25)

    gateway.search_issues("project = SH", page=2)

    call = api.calls[0]
    assert call[:4] == ("jql", "project = SH", list(JiraGateway.CORE_FIELDS), 50)
    assert "comment" not in call[2]
    assert "attachment" not in call[2]
    assert "description" not in call[2]


def test_release_search_resolves_custom_field_ids_from_metadata_and_includes_fix_versions() -> None:
    api = RecordingApi()
    gateway = JiraGateway("https://jira.example", "u", "p", api=api)

    payload = gateway.search_release_issues('"Project ID" = "P100"')

    assert api.calls[0] == ("fields",)
    assert api.calls[1][0:3] == (
        "jql", '"Project ID" = "P100"',
        [*JiraGateway.CORE_FIELDS, "fixVersions", "resolutiondate", "customfield_101", "customfield_102", "customfield_103"],
    )
    assert payload["fieldMetadata"] == {
        "customfield_101": "Project ID", "customfield_102": "Software Release", "customfield_103": "Severity",
    }


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


def test_jira_gateway_logs_issue_request_operations_without_response_content(monkeypatch) -> None:
    import core.jira.gateway as gateway_module

    records = []
    monkeypatch.setattr(
        gateway_module,
        "smart_log",
        lambda message, **kwargs: records.append((message, kwargs)),
        raising=False,
    )
    gateway = JiraGateway("https://jira.example", "u", "p", api=RecordingApi())

    gateway.get_issue("SH-1")
    gateway.load_issue_sections("SH-1", ("description",))

    requests = [kwargs["extra"] for message, kwargs in records
                if message == "Jira gateway issue request"]
    assert [item["operation"] for item in requests] == ["get_issue", "load_issue_sections"]
    assert all(item["issue_key"] == "SH-1" for item in requests)
    assert all(item["outcome"] == "success" for item in requests)
    assert requests[1]["sections"] == ["description"]
    assert all(item["duration_ms"] >= 0 for item in requests)
    assert all("body" not in item for item in requests)
