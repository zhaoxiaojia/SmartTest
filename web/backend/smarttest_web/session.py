from __future__ import annotations

from dataclasses import dataclass
import secrets
from threading import RLock
import time


@dataclass
class WebSession:
    username: str
    password: str
    display_name: str
    avatar_bytes: bytes
    expires_at: float


class InMemorySessionStore:
    def __init__(self, ttl_seconds=8 * 60 * 60, now=time.monotonic):
        self._ttl = ttl_seconds
        self._now = now
        self._items = {}
        self._lock = RLock()

    def create(self, username, password, display_name="", avatar_bytes=b""):
        with self._lock:
            session_id = secrets.token_urlsafe(32)
            self._items[session_id] = WebSession(username, password, display_name or username,
                                                 avatar_bytes or b"", self._now() + self._ttl)
            return session_id

    def get(self, session_id):
        with self._lock:
            value = self._items.get(session_id or "")
            if value is None:
                return None
            if value.expires_at <= self._now():
                self._items.pop(session_id, None)
                return None
            return value

    def delete(self, session_id):
        with self._lock:
            self._items.pop(session_id or "", None)

    @property
    def count(self):
        with self._lock:
            self._purge()
            return len(self._items)

    def _purge(self):
        expired = [key for key, value in self._items.items() if value.expires_at <= self._now()]
        for key in expired:
            self._items.pop(key, None)
