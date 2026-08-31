from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
from threading import RLock
import time

from core.config.jsonTool import app_data_dir
from core.logging import smart_log
from .credentials import CredentialStoreError, create_credential_store


SESSION_TTL_SECONDS = 90 * 24 * 60 * 60


@dataclass(frozen=True)
class WebSession:
    username: str
    display_name: str
    avatar_bytes: bytes
    expires_at: float
    password: str | None = None
    cookie_renewal_required: bool = False


def default_web_database_path() -> Path:
    return app_data_dir() / "web" / "smarttest-web.db"


class PersistentSessionStore:
    def __init__(self, path=None, *, ttl_seconds=SESSION_TTL_SECONDS,
                 refresh_interval_seconds=24 * 60 * 60, now=time.time, credential_store=None):
        self.path = Path(path or default_web_database_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl_seconds
        self._refresh_interval = refresh_interval_seconds
        self._now = now
        self._credentials: dict[str, str] = {}
        self._lock = RLock()
        self._migrate()
        self._credential_store = credential_store or create_credential_store(self.path)

    @property
    def ttl_seconds(self):
        return self._ttl

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _migrate(self):
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            if connection.execute("PRAGMA user_version").fetchone()[0] > 2:
                raise RuntimeError("Unsupported SmartTest Web database schema.")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS web_sessions (
                    id INTEGER PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    avatar BLOB,
                    created_at REAL NOT NULL,
                    last_seen_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    revoked_at REAL
                );
                CREATE INDEX IF NOT EXISTS ix_web_sessions_user ON web_sessions(username);
                CREATE TABLE IF NOT EXISTS user_preferences (
                    username TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (username, scope, key)
                );
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(web_sessions)")}
            if "credential_ref" not in columns:
                connection.execute("ALTER TABLE web_sessions ADD COLUMN credential_ref TEXT")
            connection.execute("PRAGMA user_version=2")

    @property
    def journal_mode(self):
        with self._connect() as connection:
            return connection.execute("PRAGMA journal_mode").fetchone()[0]

    @staticmethod
    def _hash(token):
        return hashlib.sha256((token or "").encode("utf-8")).hexdigest()

    def create(self, username, password, display_name="", avatar_bytes=b""):
        self.cleanup()
        token = secrets.token_urlsafe(32)
        token_hash = self._hash(token)
        credential_ref = token_hash
        now = self._now()
        self._credential_store.write(credential_ref, username, password)
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                "INSERT INTO web_sessions(token_hash,username,display_name,avatar,created_at,last_seen_at,expires_at,credential_ref) VALUES(?,?,?,?,?,?,?,?)",
                (token_hash, str(username).strip().lower(), display_name or username, avatar_bytes or None,
                 now, now, now + self._ttl, credential_ref),
                )
            except Exception:
                self._credential_store.delete(credential_ref)
                raise
            self._credentials[token_hash] = password
        return token

    def get(self, token):
        if not token:
            return None
        token_hash = self._hash(token)
        now = self._now()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT username,display_name,avatar,last_seen_at,expires_at,credential_ref FROM web_sessions WHERE token_hash=? AND revoked_at IS NULL",
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            if row[4] <= now:
                connection.execute("DELETE FROM web_sessions WHERE token_hash=?", (token_hash,))
                connection.commit()
                self._credentials.pop(token_hash, None)
                if row[5]:
                    self._delete_credential(row[5])
                return None
            expires_at = row[4]
            renewed = False
            if now - row[3] >= self._refresh_interval:
                expires_at = now + self._ttl
                connection.execute("UPDATE web_sessions SET last_seen_at=?,expires_at=? WHERE token_hash=?",
                                   (now, expires_at, token_hash))
                renewed = True
            password = self._credentials.get(token_hash)
            if password is None and row[5]:
                try:
                    _stored_username, password = self._credential_store.read(row[5])
                    self._credentials[token_hash] = password
                except CredentialStoreError as exc:
                    smart_log("Persistent Web credential recovery failed", platform="web", domain="auth",
                              source="PersistentSessionStore", level="warning",
                              extra={"exception_type": type(exc).__name__})
            return WebSession(row[0], row[1], row[2] or b"", expires_at, password, renewed)

    def resource_access(self, token, platform, database):
        from .resource_access import ResourceAccess

        value = self.get(token)
        if value is None:
            raise PermissionError("reauthentication_required")
        access = ResourceAccess(database, value.username, platform, self._hash(token), now=self._now)
        access.require_active()
        return access

    def delete(self, token):
        token_hash = self._hash(token)
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT credential_ref FROM web_sessions WHERE token_hash=?", (token_hash,)).fetchone()
            connection.execute("UPDATE web_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                               (self._now(), token_hash))
            self._credentials.pop(token_hash, None)
        if row and row[0]:
            self._delete_credential(row[0])

    def delete_all(self, username):
        now = self._now()
        with self._lock, self._connect() as connection:
            rows = list(connection.execute(
                "SELECT token_hash,credential_ref FROM web_sessions WHERE username=? AND revoked_at IS NULL", (username,)))
            cursor = connection.execute("UPDATE web_sessions SET revoked_at=? WHERE username=? AND revoked_at IS NULL",
                                        (now, username))
            for token_hash, _credential_ref in rows:
                self._credentials.pop(token_hash, None)
        for _token_hash, credential_ref in rows:
            if credential_ref: self._delete_credential(credential_ref)
        return cursor.rowcount

    def cleanup(self, limit=100):
        with self._connect() as connection:
            rows = list(connection.execute(
                "SELECT id,credential_ref FROM web_sessions WHERE expires_at<=? OR revoked_at IS NOT NULL LIMIT ?",
                (self._now(), limit),
            ))
            cursor = connection.execute(
                "DELETE FROM web_sessions WHERE id IN (SELECT id FROM web_sessions WHERE expires_at<=? OR revoked_at IS NOT NULL LIMIT ?)",
                (self._now(), limit),
            )
        for _id, credential_ref in rows:
            if credential_ref: self._delete_credential(credential_ref)
        return cursor.rowcount

    def _delete_credential(self, credential_ref):
        try:
            self._credential_store.delete(credential_ref)
        except CredentialStoreError as exc:
            smart_log("Persistent Web credential deletion failed", platform="web", domain="auth",
                      source="PersistentSessionStore", level="warning",
                      extra={"exception_type": type(exc).__name__})

    @property
    def count(self):
        self.cleanup()
        with self._connect() as connection:
            return connection.execute("SELECT count(*) FROM web_sessions WHERE revoked_at IS NULL AND expires_at>?", (self._now(),)).fetchone()[0]

    def contains_token_hash(self, token):
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM web_sessions WHERE token_hash=?", (self._hash(token),)).fetchone() is not None

    def contains_raw_token(self, token):
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM web_sessions WHERE token_hash=?", (token,)).fetchone() is not None

    def get_preferences(self, username, scope):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key,value_json,schema_version,updated_at FROM user_preferences WHERE username=? AND scope=?",
                (username, scope),
            ).fetchall()
        return {"scope": scope, "items": {key: json.loads(value) for key, value, _, _ in rows},
                "schemaVersion": max((row[2] for row in rows), default=1),
                "updatedAt": max((row[3] for row in rows), default=None)}

    def upsert_preferences(self, username, scope, items, schema_version=1):
        now = self._now()
        with self._connect() as connection:
            connection.executemany("""
                INSERT INTO user_preferences(username,scope,key,value_json,schema_version,updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(username,scope,key) DO UPDATE SET
                  value_json=excluded.value_json,schema_version=excluded.schema_version,updated_at=excluded.updated_at
            """, [(username, scope, key, json.dumps(value, ensure_ascii=False, separators=(",", ":")), schema_version, now)
                    for key, value in items.items()])
        return self.get_preferences(username, scope)

    def delete_preferences(self, username, scope):
        with self._connect() as connection:
            return connection.execute("DELETE FROM user_preferences WHERE username=? AND scope=?", (username, scope)).rowcount


# Compatibility name for existing imports; the implementation is persistent.
InMemorySessionStore = PersistentSessionStore
