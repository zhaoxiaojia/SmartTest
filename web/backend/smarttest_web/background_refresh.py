from __future__ import annotations

from threading import Lock, Thread


class BackgroundFactsRefresh:
    """Process-local single-flight refresh state; credentials live only in the worker closure."""

    def __init__(self, submit=None):
        self._submit = submit or self._start_thread
        self._lock = Lock()
        self._state = "idle"

    @staticmethod
    def _start_thread(work):
        Thread(target=work, name="smarttest-confluence-facts", daemon=True).start()

    @property
    def state(self):
        with self._lock:
            return self._state

    def start(self, owner, username, password):
        with self._lock:
            if self._state == "loading":
                return False
            self._state = "loading"

        def work():
            try:
                owner.refresh(username, password)
            except Exception:  # noqa: BLE001 - the public state is intentionally safe
                with self._lock:
                    self._state = "failed"
            else:
                with self._lock:
                    self._state = "idle"

        self._submit(work)
        return True
