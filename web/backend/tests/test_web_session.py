from time import sleep

from fastapi.testclient import TestClient

from smarttest_web.app import create_app
from smarttest_web.project_facts_api import ProjectFactsWebOwner
from smarttest_web.session import PersistentSessionStore


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

    def query(self, username, *, filters=None, search=""):
        if self.snapshot is None:
            return ProjectFactsWebOwner._state("no_snapshot")
        return {"state": "ready", "projects": self.snapshot["projects"], "facets": []}

    def refresh(self, username, password):
        self.refresh_calls.append((username.account, password))
        self.snapshot = {"projects": [{"project_id": "A"}]}
        return self.query(username)


def make_client(tmp_path, authenticator=None, sessions=None, facts=None):
    store = sessions or PersistentSessionStore(tmp_path / "web.db")
    return TestClient(create_app(
        authenticator=lambda: authenticator or FakeAuthenticator(), session_store=lambda: store,
        project_facts_owner=lambda: facts or FakeFactsOwner({"projects": []}),
    ), base_url="https://testserver"), store


def test_sqlite_session_survives_restart_and_recovers_password_outside_database(tmp_path):
    client, store = make_client(tmp_path)
    response = client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    token = client.cookies.get("smarttest_session")
    assert response.status_code == 200
    assert "secret" not in (tmp_path / "web.db").read_bytes().decode("latin1")
    value = PersistentSessionStore(tmp_path / "web.db").get(token)
    assert value.username == "coco" and value.password == "secret"
    assert store.journal_mode == "wal"


def test_login_cookie_is_90_days_and_database_only_contains_hash(tmp_path):
    client, store = make_client(tmp_path)
    response = client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    token = client.cookies.get("smarttest_session")
    cookie = response.headers["set-cookie"].lower()
    assert all(flag in cookie for flag in ("httponly", "secure", "samesite=lax", "max-age=7776000"))
    assert store.contains_token_hash(token)
    assert not store.contains_raw_token(token)


def test_sliding_expiry_is_renewed_only_after_refresh_interval(tmp_path):
    clock = [1_000.0]
    store = PersistentSessionStore(tmp_path / "web.db", ttl_seconds=100, refresh_interval_seconds=20, now=lambda: clock[0])
    token = store.create("coco", "secret")
    initial = store.get(token).expires_at
    clock[0] += 10
    assert store.get(token).expires_at == initial
    clock[0] += 11
    assert store.get(token).expires_at == clock[0] + 100
    clock[0] += 101
    assert store.get(token) is None


def test_eligible_activity_renews_browser_cookie_with_database_expiry(tmp_path):
    clock = [1_000.0]
    store = PersistentSessionStore(tmp_path / "web.db", ttl_seconds=100, refresh_interval_seconds=20, now=lambda: clock[0])
    client, _ = make_client(tmp_path, sessions=store)
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    clock[0] += 10
    assert "set-cookie" not in client.get("/api/auth/session").headers
    clock[0] += 11
    renewed = client.get("/api/auth/session")
    assert "max-age=100" in renewed.headers["set-cookie"].lower()
    assert "httponly" in renewed.headers["set-cookie"].lower()
    clock[0] += 10
    assert "set-cookie" not in client.get("/api/auth/session").headers


def test_multiple_devices_current_and_all_logout(tmp_path):
    client1, store = make_client(tmp_path)
    client2, _ = make_client(tmp_path, sessions=store)
    client1.post("/api/auth/login", json={"username": "coco", "password": "one"})
    client2.post("/api/auth/login", json={"username": "coco", "password": "two"})
    assert store.count == 2
    client1.post("/api/auth/logout")
    assert client1.get("/api/auth/session").json() == {"authenticated": False}
    assert client2.get("/api/auth/session").json()["authenticated"] is True
    assert client2.post("/api/auth/logout-all").status_code == 200
    assert client2.get("/api/auth/session").json() == {"authenticated": False}


def test_restored_session_recovers_server_credential_for_page_catalog_load(tmp_path):
    client, _ = make_client(tmp_path, facts=FakeFactsOwner())
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    token = client.cookies.get("smarttest_session")
    restarted_facts = FakeFactsOwner()
    restarted, _ = make_client(
        tmp_path, sessions=PersistentSessionStore(tmp_path / "web.db"), facts=restarted_facts,
    )
    restarted.cookies.set("smarttest_session", token)
    assert restarted.get("/api/auth/session").json()["authenticated"] is True
    response = restarted.get("/api/confluence/project-facts?catalog=1")
    assert response.status_code == 200
    assert response.json()["state"] in {"loading", "ready"}
    for _ in range(50):
        if restarted_facts.refresh_calls:
            break
        sleep(.01)
    assert restarted_facts.refresh_calls == [("coco", "secret")]


def test_invalid_login_returns_safe_failure(tmp_path):
    auth = FakeAuthenticator({"success": False, "code": "invalid_credentials", "detail": "secret"})
    response = make_client(tmp_path, authenticator=auth)[0].post("/api/auth/login", json={"username": "coco", "password": "secret"})
    assert response.status_code == 401
    assert response.json() == {"detail": {"state": "invalid_credentials"}}
    assert "secret" not in response.text


def test_existing_fact_cache_is_read_after_login(tmp_path):
    facts = FakeFactsOwner({"projects": [{"project_id": "cached"}]})
    client, _ = make_client(tmp_path, facts=facts)
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    response = client.get("/api/confluence/project-facts")
    assert response.json()["projects"][0]["project_id"] == "cached"
    assert facts.refresh_calls == []


def test_concurrent_no_cache_refresh_is_deduplicated(tmp_path):
    from threading import Event
    started, release, finished = Event(), Event(), Event()
    class SlowFacts(FakeFactsOwner):
        def refresh(self, username, password):
            self.refresh_calls.append((username.account, password))
            started.set()
            try:
                assert release.wait(5)
                self.snapshot = {"projects": [{"project_id": "A"}]}
            finally:
                finished.set()

    facts = SlowFacts()
    client, _ = make_client(tmp_path, facts=facts)
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    try:
        first = client.get("/api/confluence/project-facts?catalog=1")
        assert started.wait(2)
        second = client.get("/api/confluence/project-facts?catalog=1")
        assert first.json()["state"] == second.json()["state"] == "loading"
        assert facts.refresh_calls == [("coco", "secret")]
    finally:
        release.set()
        assert finished.wait(2)
