from __future__ import annotations

from threading import Lock, Thread


class BackgroundFactsRefresh:
    """Process-local single-flight refresh state; credentials live only in the worker closure."""

    def __init__(self, submit=None):
        self._submit = submit or self._start_thread
        self._lock = Lock()
        self._states = {}

    @staticmethod
    def _start_thread(work):
        Thread(target=work, name="smarttest-confluence-facts", daemon=True).start()

    @property
    def state(self):
        return self.state_for("")

    def state_for(self, username):
        with self._lock:
            return self._states.get(str(username).strip().casefold(), "idle")

    def start(self, owner, username, password):
        account = str(username).strip().casefold()
        with self._lock:
            if self._states.get(account) == "loading":
                return False
            self._states[account] = "loading"

        def work():
            try:
                owner.refresh(username, password)
            except Exception:  # noqa: BLE001 - the public state is intentionally safe
                with self._lock:
                    self._states[account] = "failed"
            else:
                with self._lock:
                    self._states[account] = "idle"

        self._submit(work)
        return True
