from __future__ import annotations

from dataclasses import dataclass

import pytest

from support.jira_integration.core.models import SearchPage


@dataclass
class FakeClient:
    pages: list[SearchPage] | None = None
    filter_payload: dict | None = None
    error: Exception | None = None

    def __post_init__(self):
        self.search_calls = []
        self.filter_calls = []

    def search_page(self, jql, **kwargs):
        self.search_calls.append((jql, kwargs))
        if self.error is not None:
            raise self.error
        if self.pages:
            return self.pages.pop(0)
        return SearchPage([], 0, kwargs.get("max_results", 1), 0, True)

    def fetch_filter(self, filter_id):
        self.filter_calls.append(filter_id)
        return dict(self.filter_payload or {})


def _issue(key: str) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": "[ACME][T7][Playback] Video freezes after seeking",
            "description": "\n".join(
                (
                    "[Steps to reproduce]:",
                    "Seek video",
                    "[Actual results]:",
                    "Freeze",
                    "[Expected results]:",
                    "Continue",
                    "[Reproducibility rate]:",
                    "1/1",
                    "[Comparision]:",
                    "Not reproduced on build 2026.07.20",
                    "[Notes]:",
                    "",
                    "HW info:",
                    "T7",
                    "SW info:",
                    "2026.07.20",
                )
            ),
            "reporter": {"displayName": "Coco"},
            "components": [{"name": "Playback"}],
            "labels": [],
            "attachment": [],
        },
    }


@pytest.mark.parametrize(
    ("text", "kind", "jql"),
    [
        ("project = SH ORDER BY key", "jql", "project = SH ORDER BY key"),
        ("https://jira.example.com/browse/SH-123", "issue_url", 'key = "SH-123"'),
        ("http://jira.example.com/browse/SH-123", "issue_url", 'key = "SH-123"'),
        (
            "https://jira.example.com/issues/?jql=project%20%3D%20SH",
            "jql_url",
            "project = SH",
        ),
    ],
)
def test_resolve_audit_input_accepts_supported_sources(text, kind, jql):
    from support.jira_integration.audit.input_resolver import resolve_audit_input

    client = FakeClient()
    result = resolve_audit_input(text, base_url="https://jira.example.com", client=client)

    assert (result.source_kind, result.original, result.jql) == (kind, text, jql)
    assert client.search_calls[0][0] == jql
    assert client.search_calls[0][1]["max_results"] == 1


def test_resolve_filter_url_fetches_jql_and_validates_it():
    from support.jira_integration.audit.input_resolver import resolve_audit_input

    client = FakeClient(filter_payload={"id": "42", "jql": "labels = regression"})
    result = resolve_audit_input(
        "https://jira.example.com/issues/?filter=42",
        base_url="https://jira.example.com/",
        client=client,
    )

    assert result.source_kind == "filter_url"
    assert result.jql == "labels = regression"
    assert client.filter_calls == ["42"]
    assert client.search_calls[0][0] == "labels = regression"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("  ", "JQL"),
        ("https://other.example.com/browse/SH-1", "host"),
        ("ftp://jira.example.com/browse/SH-1", "HTTP"),
        ("https://jira.example.com/browse/not-a-key", "URL"),
        ("https://jira.example.com/unsupported", "URL"),
    ],
)
def test_resolve_audit_input_rejects_invalid_input(text, message):
    from support.jira_integration.audit.input_resolver import resolve_audit_input

    with pytest.raises(ValueError, match=message):
        resolve_audit_input(text, base_url="https://jira.example.com", client=FakeClient())


def test_filter_without_jql_and_jira_validation_failure_are_actionable():
    from support.jira_integration.audit.input_resolver import resolve_audit_input

    with pytest.raises(ValueError, match="JQL"):
        resolve_audit_input(
            "https://jira.example.com/issues/?filter=42",
            base_url="https://jira.example.com",
            client=FakeClient(filter_payload={"id": "42"}),
        )
    with pytest.raises(ValueError, match="JQL"):
        resolve_audit_input(
            "project =",
            base_url="https://jira.example.com",
            client=FakeClient(error=RuntimeError("syntax error")),
        )


def test_jira_client_fetch_filter_uses_existing_transport_boundary(monkeypatch):
    from types import SimpleNamespace

    from support.jira_integration.auth.basic import JiraBasicAuth
    from support.jira_integration.transport.client import JiraClient, JiraClientConfig

    client = JiraClient(
        JiraClientConfig(base_url="https://jira.example.com"),
        JiraBasicAuth("user", "secret"),
    )
    calls = []
    monkeypatch.setattr(
        client,
        "_request",
        lambda method, url: calls.append((method, url))
        or SimpleNamespace(data={"id": "42", "jql": "project = SH"}),
    )

    assert client.fetch_filter(" 42 ") == {"id": "42", "jql": "project = SH"}
    assert calls == [("GET", "https://jira.example.com/rest/api/2/filter/42")]


def test_service_reports_fetch_and_audit_progress_per_page_and_issue():
    from support.jira_integration.audit import ResolvedAuditInput
    from support.jira_integration.audit.service import JiraAuditService

    client = FakeClient(
        pages=[
            SearchPage([_issue("SH-1"), _issue("SH-2")], 0, 2, 3, False),
            SearchPage([_issue("SH-3")], 2, 2, 3, True),
        ]
    )
    progress = []
    report = JiraAuditService(client, base_url="https://jira.example.com").run(
        ResolvedAuditInput("jql", "project = SH", "project = SH"),
        lambda stage, processed, total: progress.append((stage, processed, total)),
    )

    assert [item.key for item in report.issues] == ["SH-1", "SH-2", "SH-3"]
    assert report.total_count == 3
    assert report.passed_count == 3
    assert progress == [
        ("fetching", 2, 3),
        ("fetching", 3, 3),
        ("auditing", 1, 3),
        ("auditing", 2, 3),
        ("auditing", 3, 3),
    ]
    assert [call[1]["start_at"] for call in client.search_calls] == [0, 2]


def test_service_returns_empty_report_with_fetch_progress():
    from support.jira_integration.audit import ResolvedAuditInput
    from support.jira_integration.audit.service import JiraAuditService

    client = FakeClient(pages=[SearchPage([], 0, 100, 0, True)])
    progress = []
    report = JiraAuditService(client, base_url="https://jira.example.com").run(
        ResolvedAuditInput("jql", "key = SH-999", "key = SH-999"),
        lambda *args: progress.append(args),
    )

    assert report.total_count == 0
    assert report.issues == ()
    assert progress == [("fetching", 0, 0)]
