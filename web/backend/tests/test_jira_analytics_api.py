from fastapi.testclient import TestClient

from smarttest_web.app import create_app
from smarttest_web.session import PersistentSessionStore
from test_web_session import FakeAuthenticator


class FilterOwner:
    def fields(self): return [{"id": "customfield_1", "name": "Team", "control": "advanced", "queryable": False, "options": [], "schema": {}}]
    def saved_filters(self): return [{"id": "7", "name": "Mine", "owner": "Coco"}]
    def saved_filter(self, value): return {"id": value, "name": "Mine", "jql": "project = SH"}
    def validate(self, jql): return {"valid": jql != "bad", "errors": [] if jql != "bad" else ["Bad JQL"]}
    def suggestions(self, field_name, query):
        return [{"value": f"{field_name}:1", "displayName": query or "All"}]


class Gateway:
    def search_all_payloads(self, _jql): return []


def client(tmp_path):
    app = create_app(
        authenticator=FakeAuthenticator,
        session_store=lambda: PersistentSessionStore(tmp_path / "web.db"),
        jira_filter_owner=lambda _u, _p: (FilterOwner(), Gateway()),
    )
    result = TestClient(app, base_url="https://testserver")
    result.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    return result


def test_analytics_endpoints_are_independent_and_search_starts_task(tmp_path):
    api = client(tmp_path)

    assert api.get("/api/jira/analytics/fields").json()["more"][0]["id"] == "customfield_1"
    assert api.get("/api/jira/analytics/suggestions", params={"fieldName": "status", "query": "op"}).json() == [
        {"value": "status:1", "displayName": "op"},
    ]
    assert api.get("/api/jira/analytics/saved-filters").json()[0]["id"] == "7"
    assert api.get("/api/jira/analytics/saved-filters/7").json()["jql"] == "project = SH"
    invalid = api.post("/api/jira/analytics/search", json={"mode": "advanced", "jql": "bad"})
    assert invalid.json()["validation"]["valid"] is False
    started = api.post("/api/jira/analytics/search", json={"mode": "advanced", "jql": "project = SH"})
    assert started.status_code == 200
    task_id = started.json()["taskId"]
    assert api.get(f"/api/jira/analytics/tasks/{task_id}").status_code == 200
    assert api.delete(f"/api/jira/analytics/tasks/{task_id}").json() == {"cancelled": True}
    assert api.get("/api/jira/filter-snapshot").json()["snapshot"] is None


def test_analytics_state_is_not_visible_to_another_account(tmp_path):
    first = client(tmp_path)
    first.post("/api/jira/analytics/search", json={"mode": "advanced", "jql": "project = SH"})
    first.post("/api/auth/logout")
    first.post("/api/auth/login", json={"username": "other", "password": "secret"})

    assert first.get("/api/jira/analytics/state").json()["activeJql"] == ""


def test_suggestions_resolve_the_current_sessions_jira_credentials_on_every_request(tmp_path):
    calls = []

    class AccountAuthenticator:
        def authenticate(self, username, _password):
            return {"success": True, "username": username, "display_name": username, "avatar_bytes": b""}

    def owner(username, password):
        calls.append((username, password))
        return FilterOwner(), Gateway()

    app = create_app(
        authenticator=AccountAuthenticator,
        session_store=lambda: PersistentSessionStore(tmp_path / "web.db"),
        jira_filter_owner=owner,
    )
    api = TestClient(app, base_url="https://testserver")
    api.post("/api/auth/login", json={"username": "alice", "password": "first"})
    api.get("/api/jira/analytics/suggestions", params={"fieldName": "status"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "bob", "password": "second"})
    api.get("/api/jira/analytics/suggestions", params={"fieldName": "status"})

    assert calls == [("alice", "first"), ("bob", "second")]
