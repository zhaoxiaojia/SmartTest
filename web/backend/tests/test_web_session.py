from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

from fastapi.testclient import TestClient

from smarttest_web.app import create_app
from smarttest_web.session import InMemorySessionStore
from smarttest_web.project_facts_api import ProjectFactsWebOwner


class FakeAuthenticator:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {"success": True, "username": "coco", "display_name": "Coco Chen", "avatar_bytes": b"avatar"}

    def authenticate(self, username, password):
        self.calls.append((username, password))
        return dict(self.result)


class FakeFactsOwner:
    def __init__(self, initial=None):
        self.snapshot = initial
        self.refresh_calls = []

    def query(self, *, filters=None, search=""):
        if self.snapshot is None:
            return ProjectFactsWebOwner._state("no_snapshot")
        return {"state": "ready", "projects": self.snapshot["projects"], "facets": []}

    def refresh(self, username, password):
        self.refresh_calls.append((username, password))
        self.snapshot = {"projects": [{"project_id": "A"}]}
        return self.query()


def make_client(authenticator=None, sessions=None, facts=None):
    return TestClient(create_app(
        authenticator=lambda: authenticator or FakeAuthenticator(),
        session_store=lambda: sessions or InMemorySessionStore(ttl_seconds=3600),
        project_facts_owner=lambda: facts or FakeFactsOwner({"projects": []}),
    ), base_url="https://testserver")


def test_login_authenticates_once_and_reuses_server_side_session_without_password_response():
    auth = FakeAuthenticator()
    client = make_client(authenticator=auth)
    response = client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    assert response.status_code == 200
    assert auth.calls == [("coco", "secret")]
    assert "secret" not in response.text
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    assert client.get("/api/auth/session").json() == {
        "authenticated": True, "username": "coco", "displayName": "Coco Chen", "avatarUrl": "/api/auth/avatar",
    }
    assert auth.calls == [("coco", "secret")]


def test_logout_and_expiry_clear_session_credentials():
    clock = [100.0]
    sessions = InMemorySessionStore(ttl_seconds=10, now=lambda: clock[0])
    client = make_client(sessions=sessions)
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    assert sessions.count == 1
    client.post("/api/auth/logout")
    assert sessions.count == 0
    assert client.get("/api/auth/session").json() == {"authenticated": False}
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    clock[0] += 11
    assert client.get("/api/auth/session").json() == {"authenticated": False}
    assert sessions.count == 0


def test_invalid_login_returns_safe_failure_without_password():
    auth = FakeAuthenticator({"success": False, "code": "invalid_credentials", "detail": "secret"})
    response = make_client(authenticator=auth).post("/api/auth/login", json={"username": "coco", "password": "secret"})
    assert response.status_code == 401
    assert response.json() == {"detail": {"state": "invalid_credentials"}}
    assert "secret" not in response.text


def test_existing_fact_cache_is_read_without_login_or_refresh():
    facts = FakeFactsOwner({"projects": [{"project_id": "cached"}]})
    response = make_client(facts=facts).get("/api/confluence/project-facts")
    assert response.status_code == 200
    assert response.json()["projects"][0]["project_id"] == "cached"
    assert facts.refresh_calls == []


def test_no_cache_uses_current_session_once_and_concurrent_requests_deduplicate_refresh():
    class SlowFacts(FakeFactsOwner):
        def __init__(self):
            super().__init__(); self.started = Event(); self.release = Event()

        def refresh(self, username, password):
            self.refresh_calls.append((username, password)); self.started.set(); self.release.wait(2)
            self.snapshot = {"projects": [{"project_id": "A"}]}

    facts = SlowFacts()
    client = make_client(facts=facts)
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    started_at = monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.get("/api/confluence/project-facts"), range(2)))
    assert monotonic() - started_at < 1
    assert [response.status_code for response in responses] == [200, 200]
    assert all(response.json()["state"] == "loading" for response in responses)
    assert all(len(response.json()["facets"]) == 21 for response in responses)
    assert all(len(response.json()["ownerHierarchy"]) == 3 for response in responses)
    assert facts.started.wait(1)
    assert facts.refresh_calls == [("coco", "secret")]
    facts.release.set()
    for _ in range(50):
        ready = client.get("/api/confluence/project-facts").json()
        if ready["state"] == "ready": break
        sleep(.01)
    assert ready["state"] == "ready"


def test_explicit_refresh_requires_login():
    facts = FakeFactsOwner()
    client = make_client(facts=facts)
    assert client.post("/api/confluence/project-facts/refresh").status_code == 401
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    assert client.post("/api/confluence/project-facts/refresh").json()["state"] == "loading"
    for _ in range(50):
        if facts.refresh_calls: break
        sleep(.01)
    assert facts.refresh_calls == [("coco", "secret")]


def test_background_refresh_failure_returns_safe_state_and_explicit_retry(capsys):
    class FailingFacts(FakeFactsOwner):
        def refresh(self, username, password):
            self.refresh_calls.append((username, password))
            raise RuntimeError(f"remote failure for {password}")

    facts = FailingFacts()
    client = make_client(facts=facts)
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    response = client.get("/api/confluence/project-facts")
    assert response.json()["state"] == "loading"
    for _ in range(50):
        failed = client.get("/api/confluence/project-facts").json()
        if failed["state"] == "failed": break
        sleep(.01)
    assert failed["state"] == "failed"
    retry = client.post("/api/confluence/project-facts/refresh")
    assert retry.status_code == 200
    assert retry.json()["state"] == "loading"
    for _ in range(50):
        if len(facts.refresh_calls) == 2: break
        sleep(.01)
    assert len(facts.refresh_calls) == 2
    assert "secret" not in response.text + failed.__repr__() + retry.text
    assert "secret" not in capsys.readouterr().out
