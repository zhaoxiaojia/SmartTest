from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from core.domain.detail import DetailSection
from core.domain.values import NamedValue
from core.jira.domain import (
    Issue,
    IssueDetails,
    IssueIdentity,
    IssuePage,
    JiraProjectRef,
)
from smarttest_web.app import create_app
from test_web_session import FakeAuthenticator


def _client(app):
    client = TestClient(app, base_url="https://testserver")
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    return client


def _issue() -> Issue:
    return Issue(
        IssueIdentity("1", "SH-1", "https://jira/SH-1"), "Cached",
        JiraProjectRef("SH"), NamedValue("1", "Open"), NamedValue("2", "Bug"),
    )


class _Facts:
    def query(self, _username, **_kwargs):
        return {"state": "ready", "facets": [], "projects": [], "ownerHierarchy": []}


def test_jira_current_cache_api_preserves_pagination_and_explicit_details() -> None:
    class Service:
        def __init__(self):
            self.list_calls = []
            self.detail_calls = []

        def list_issues(self, query, page, page_size):
            self.list_calls.append((query, page, page_size))
            return IssuePage((_issue(),), page, page_size, 30)

        def get_issue(self, issue_key, details: IssueDetails):
            self.detail_calls.append((issue_key, details.sections()))
            return replace(_issue(), comments=DetailSection.loaded(()))

    service = Service()
    app = create_app(
        authenticator=FakeAuthenticator,
        jira_cache_owner=lambda _username, _password: service,
        project_facts_owner=_Facts,
    )
    client = _client(app)

    listed = client.get("/api/jira/issues", params={"query": "project=SH", "page": 1, "pageSize": 25})
    detailed = client.get("/api/jira/issues/SH-1", params=[("details", "comments")])

    assert listed.status_code == 200
    assert listed.json()["pagination"] == {"page": 1, "pageSize": 25, "total": 30}
    assert listed.json()["issues"][0]["key"] == "SH-1"
    assert service.list_calls == [("project=SH", 1, 25)]
    assert detailed.status_code == 200
    assert detailed.json()["details"]["comments"]["state"] == "loaded"
    assert service.detail_calls == [("SH-1", ("comments",))]


def test_current_cache_invalidation_routes_call_only_the_matching_owner() -> None:
    class JiraService:
        def __init__(self): self.invalidated = []
        def invalidate_issue(self, key): self.invalidated.append(key)

    class ConfluenceOwner:
        def __init__(self): self.invalidated = []
        def query(self, username, **_kwargs):
            return {"state": "ready", "facets": [], "projects": [], "ownerHierarchy": []}
        def invalidate_project(self, project_id, access): self.invalidated.append(project_id)

    jira, confluence = JiraService(), ConfluenceOwner()
    client = _client(create_app(
        authenticator=FakeAuthenticator,
        jira_cache_owner=lambda *_: jira,
        project_facts_owner=lambda: confluence,
    ))

    assert client.delete("/api/jira/issues/SH-1").json() == {"invalidated": "SH-1"}
    assert client.delete("/api/confluence/projects/P100").json() == {"invalidated": "P100"}
    assert jira.invalidated == ["SH-1"]
    assert confluence.invalidated == ["P100"]
