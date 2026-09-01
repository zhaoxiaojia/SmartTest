from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import RLock


class RefreshState(str, Enum):
    CACHED = "cached"
    FIRST_LOADING = "first_loading"
    REFRESHING = "refreshing"
    UPDATED = "updated"
    REFRESH_FAILED = "refresh_failed"


@dataclass(frozen=True)
class DynamicSourceEvent:
    state: RefreshState
    snapshot: object | None
    generation: int
    account_hash: str
    error_kind: str = ""


class AccountDynamicSource:
    """Account-scoped stale-while-revalidate coordinator.

    An injected submitter/executor remains caller-owned; close only invalidates
    this coordinator's logical work.
    """

    def __init__(
        self, cache, domain, source, serialize, deserialize, *,
        ttl, now=None, submit=None,
    ):
        self.cache = cache
        self.domain = domain
        self.source = source
        self.serialize = serialize
        self.deserialize = deserialize
        self.ttl = ttl
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.submit = submit or (lambda work: work())
        self._lock = RLock()
        self._generation = 0
        self._account_hash = ""
        self._closed = False
        self._callbacks_in_flight = 0

    def _active_locked(self, generation, account_hash):
        return (
            not self._closed
            and generation == self._generation
            and account_hash == self._account_hash
        )

    def _publish_if_active(self, publish, event):
        with self._lock:
            if not self._active_locked(event.generation, event.account_hash):
                return False
            # Reservation defines callback start. close() invalidates future
            # reservations but deliberately does not wait for this callback.
            self._callbacks_in_flight += 1
        try:
            publish(event)
        except Exception:
            pass
        finally:
            with self._lock:
                self._callbacks_in_flight -= 1
                active = self._active_locked(
                    event.generation, event.account_hash,
                )
        return active

    def open(self, account, refresh, publish, *, force=False):
        account_hash = self.cache.identity(account)
        with self._lock:
            if self._closed:
                return None
            self._generation += 1
            generation = self._generation
            self._account_hash = account_hash

        cached = self.cache.load(self.domain, self.source, account)
        value = None
        cache_corrupt = False
        if cached:
            try:
                value = self.deserialize(cached.payload)
            except Exception:
                cached = None
                cache_corrupt = True
            else:
                event = DynamicSourceEvent(
                    RefreshState.CACHED, value, generation, account_hash,
                )
                if not self._publish_if_active(publish, event):
                    return generation

        fresh = bool(
            cached
            and self.now().astimezone(timezone.utc) - cached.fetched_at <= self.ttl
        )
        if fresh and not force:
            return generation

        loading = DynamicSourceEvent(
            RefreshState.REFRESHING if cached else RefreshState.FIRST_LOADING,
            value, generation, account_hash,
            "cache_corrupt" if cache_corrupt else "",
        )
        if not self._publish_if_active(publish, loading):
            return generation

        def work():
            try:
                result = refresh()
                payload = self.serialize(result)
                fetched_at = self.now().astimezone(timezone.utc)
                with self._lock:
                    if not self._active_locked(generation, account_hash):
                        return
                    self.cache.save(
                        self.domain, self.source, account, payload,
                        fetched_at=fetched_at,
                    )
                event = DynamicSourceEvent(
                    RefreshState.UPDATED, result, generation, account_hash,
                )
            except Exception as exc:
                event = DynamicSourceEvent(
                    RefreshState.REFRESH_FAILED, value, generation, account_hash,
                    self._error_kind(exc, cache_corrupt),
                )
            self._publish_if_active(publish, event)

        try:
            self.submit(work)
        except Exception as exc:
            event = DynamicSourceEvent(
                RefreshState.REFRESH_FAILED, value, generation, account_hash,
                self._error_kind(exc, cache_corrupt),
            )
            self._publish_if_active(publish, event)
        return generation

    def invalidate(self):
        with self._lock:
            if not self._closed:
                self._generation += 1
                self._account_hash = ""

    def close(self):
        with self._lock:
            self._closed = True
            self._generation += 1
            self._account_hash = ""

    @staticmethod
    def _error_kind(exc, cache_corrupt=False):
        if cache_corrupt:
            return "cache_corrupt"
        if exc.__class__.__name__.endswith("DependencyError"):
            return "dependency"
        if getattr(getattr(exc, "response", None), "status_code", None) in {401, 403}:
            return "auth"
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return "network"
        return "source"
