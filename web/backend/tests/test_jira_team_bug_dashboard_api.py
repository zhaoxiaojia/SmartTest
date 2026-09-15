from fastapi.testclient import TestClient

from smarttest_web.app import create_app
from smarttest_web.session import PersistentSessionStore
from test_web_session import FakeAuthenticator


class Gateway:
    def __init__(self): self.calls = []
    def search_all_payloads(self, jql, *, fields=None, progress=None):
        self.calls.append((jql, fields))
        if progress: progress(1, 1)
        return [{"fields": {"issuetype": {"name": "Bug"},
                            "project": {"key": "TV"},
                            "assignee": {"name": "junjie.li", "displayName": "Junjie Li"},
                            "priority": {"name": "P0"}, "resolution": None}}]


def test_dashboard_team_bugs_requires_auth_and_uses_current_credentials(tmp_path):
    seen, gateway = [], Gateway()
    def factory(username, password):
        seen.append((username, password))
        return gateway
    app = create_app(authenticator=FakeAuthenticator,
        session_store=lambda: PersistentSessionStore(tmp_path / "web.db"),
        jira_team_bug_gateway=factory)
    api = TestClient(app, base_url="https://testserver")
    assert api.get("/api/dashboard/jira-team-bugs").status_code == 401
    api.post("/api/auth/login", json={"username": "coco", "password": "secret"})

    first = api.get("/api/dashboard/jira-team-bugs")
    assert first.status_code == 200
    task_id = first.json()["task"]["id"]
    app.state.jira_team_bug_tasks.manager.join(task_id)
    ready = api.get("/api/dashboard/jira-team-bugs").json()

    assert seen == [("coco", "secret")]
    assert ready["state"] == "ready"
    assert ready["productLines"][2]["people"][0]["displayName"] == "Junjie Li"
    assert not any("Ratio" in key for key in ready["productLines"][2]["people"][0])
    assert "issues" not in ready


def test_logout_all_deletes_account_dashboard_snapshot(tmp_path):
    gateway = Gateway()
    app = create_app(authenticator=FakeAuthenticator,
        session_store=lambda: PersistentSessionStore(tmp_path / "web.db"),
        jira_team_bug_gateway=lambda *_: gateway)
    api = TestClient(app, base_url="https://testserver")
    api.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    task_id = api.get("/api/dashboard/jira-team-bugs").json()["task"]["id"]
    app.state.jira_team_bug_tasks.manager.join(task_id)
    assert api.get("/api/dashboard/jira-team-bugs").json()["state"] == "ready"
    api.post("/api/auth/logout-all")

    api.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    assert api.get("/api/dashboard/jira-team-bugs").json()["state"] == "loading"
