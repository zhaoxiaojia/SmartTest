import sqlite3

from fastapi.testclient import TestClient

from smarttest_web.app import create_app
from smarttest_web.session import PersistentSessionStore
from test_web_session import FakeAuthenticator, FakeFactsOwner


def client_for(tmp_path, username="coco"):
    store = PersistentSessionStore(tmp_path / "web.db")
    auth = FakeAuthenticator({"success": True, "username": username, "display_name": username, "avatar_bytes": b""})
    client = TestClient(create_app(authenticator=lambda: auth, session_store=lambda: store,
                                   project_facts_owner=lambda: FakeFactsOwner({"projects": []})),
                        base_url="https://testserver")
    client.post("/api/auth/login", json={"username": username, "password": "secret"})
    return client, store


def test_preferences_are_account_scoped_and_last_write_wins(tmp_path):
    coco, store = client_for(tmp_path, "coco")
    atlas, _ = client_for(tmp_path, "atlas")
    payload = {"items": {"theme": "dark", "filters": ["ready"]}, "schemaVersion": 1}
    assert coco.put("/api/preferences/global", json=payload).status_code == 200
    assert coco.get("/api/preferences/global").json()["items"] == payload["items"]
    assert atlas.get("/api/preferences/global").json()["items"] == {}
    coco.put("/api/preferences/global", json={"items": {"theme": "light"}})
    assert coco.get("/api/preferences/global").json()["items"]["theme"] == "light"
    assert store.journal_mode == "wal"


def test_preference_reset_and_authentication_boundary(tmp_path):
    client, store = client_for(tmp_path)
    client.put("/api/preferences/wifi.rvr", json={"items": {"standards": ["11be"]}})
    assert client.delete("/api/preferences/wifi.rvr").json()["deleted"] == 1
    assert client.get("/api/preferences/wifi.rvr").json()["items"] == {}
    anonymous = TestClient(create_app(session_store=lambda: store), base_url="https://testserver")
    assert anonymous.get("/api/preferences/global").status_code == 401


def test_sensitive_invalid_and_oversized_preferences_are_rejected(tmp_path):
    client, _ = client_for(tmp_path)
    for items in ({"password": "secret"}, {"apiToken": "secret"}, {"cookie_value": "secret"}, {"form": {"credential": "secret"}}):
        assert client.put("/api/preferences/global", json={"items": items}).status_code == 422
    assert client.put("/api/preferences/global", json={"items": {"x": "x" * 70000}}).status_code == 413


def test_schema_migration_is_idempotent_and_upsert_is_atomic(tmp_path):
    path = tmp_path / "web.db"
    first = PersistentSessionStore(path)
    first.upsert_preferences("coco", "global", {"theme": "dark"}, 1)
    second = PersistentSessionStore(path)
    second.upsert_preferences("coco", "global", {"theme": "light", "compact": True}, 2)
    assert second.get_preferences("coco", "global")["items"] == {"compact": True, "theme": "light"}
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_newer_unknown_schema_is_not_silently_downgraded(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=3")
    try:
        PersistentSessionStore(path)
    except RuntimeError as error:
        assert str(error) == "Unsupported SmartTest Web database schema."
    else:
        raise AssertionError("Future schema must be rejected")
