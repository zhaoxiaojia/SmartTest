import base64
import sqlite3

import pytest

from smarttest_web.credentials import CredentialStoreError, create_credential_store
from smarttest_web.session import PersistentSessionStore


class NativeCredentials:
    def __init__(self): self.values = {}
    def write_generic(self, target, username, blob): self.values[target] = (username, bytes(blob))
    def read_generic(self, target):
        username, blob = self.values[target]
        return username, bytearray(blob)
    def delete_generic(self, target): self.values.pop(target, None)
    @staticmethod
    def clear(blob):
        for index in range(len(blob)): blob[index] = 0


def test_windows_backend_reuses_core_credential_manager_owner(tmp_path):
    native = NativeCredentials()
    store = create_credential_store(tmp_path / "web.db", platform_name="win32", windows_native=native)
    store.write("abc_123", "coco", "secret")
    assert store.read("abc_123") == ("coco", "secret")
    assert next(iter(native.values)).startswith("SmartTest/WebSession/")


def test_linux_backend_encrypts_credentials_without_storing_plaintext_or_master_key(tmp_path):
    database = tmp_path / "web.db"
    master = b"k" * 32
    store = create_credential_store(database, platform_name="linux", environ={
        "SMARTTEST_WEB_CREDENTIAL_KEY": base64.urlsafe_b64encode(master).decode(),
    })
    store.write("abc_123", "coco", "top-secret-password")
    assert store.read("abc_123") == ("coco", "top-secret-password")
    raw = database.read_bytes()
    assert b"top-secret-password" not in raw
    assert master not in raw
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT key_version FROM web_credentials").fetchone() == (1,)


def test_persistent_session_restores_credential_after_process_restart_and_logout_is_per_device(tmp_path):
    database = tmp_path / "web.db"
    environment = {"SMARTTEST_WEB_CREDENTIAL_KEY": base64.urlsafe_b64encode(b"m" * 32).decode()}
    first = PersistentSessionStore(database, credential_store=create_credential_store(database, platform_name="linux", environ=environment))
    one = first.create("coco", "one")
    two = first.create("coco", "two")
    restarted = PersistentSessionStore(database, credential_store=create_credential_store(database, platform_name="linux", environ=environment))
    assert restarted.get(one).password == "one"
    assert restarted.get(two).password == "two"
    restarted.delete(one)
    assert restarted.get(one) is None
    assert restarted.get(two).password == "two"
    restarted.delete_all("coco")
    assert restarted.get(two) is None


def test_expired_session_removes_its_persisted_credential(tmp_path):
    database = tmp_path / "web.db"
    environment = {"SMARTTEST_WEB_CREDENTIAL_KEY": base64.urlsafe_b64encode(b"e" * 32).decode()}
    clock = [100.0]
    credentials = create_credential_store(database, platform_name="linux", environ=environment)
    sessions = PersistentSessionStore(database, credential_store=credentials, ttl_seconds=10, now=lambda: clock[0])
    token = sessions.create("coco", "secret")
    clock[0] = 111.0
    assert sessions.get(token) is None
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM web_credentials").fetchone() == (0,)


@pytest.mark.parametrize("configured", [None, "not-base64", base64.urlsafe_b64encode(b"short").decode()])
def test_linux_backend_fails_safely_for_missing_or_invalid_master_key(tmp_path, configured):
    environment = {} if configured is None else {"SMARTTEST_WEB_CREDENTIAL_KEY": configured}
    store = create_credential_store(tmp_path / "web.db", platform_name="linux", environ=environment)
    with pytest.raises(CredentialStoreError, match="credential key"):
        store.write("abc_123", "coco", "never-stored")
    assert b"never-stored" not in (tmp_path / "web.db").read_bytes()


def test_restart_with_wrong_key_logs_only_safe_failure_and_keeps_session_authenticated(tmp_path, monkeypatch):
    import smarttest_web.session as session_module
    records = []
    monkeypatch.setattr(session_module, "smart_log", lambda message, **kwargs: records.append((message, kwargs)))
    database = tmp_path / "web.db"
    correct = {"SMARTTEST_WEB_CREDENTIAL_KEY": base64.urlsafe_b64encode(b"a" * 32).decode()}
    wrong = {"SMARTTEST_WEB_CREDENTIAL_KEY": base64.urlsafe_b64encode(b"b" * 32).decode()}
    first = PersistentSessionStore(database, credential_store=create_credential_store(database, platform_name="linux", environ=correct))
    token = first.create("coco", "do-not-log-this")
    restarted = PersistentSessionStore(database, credential_store=create_credential_store(database, platform_name="linux", environ=wrong))

    value = restarted.get(token)
    assert value.username == "coco" and value.password is None
    assert records[0][0] == "Persistent Web credential recovery failed"
    assert records[0][1]["extra"] == {"exception_type": "CredentialStoreError"}
    assert "do-not-log-this" not in repr(records)
