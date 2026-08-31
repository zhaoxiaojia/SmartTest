from __future__ import annotations

from threading import Event, Lock, Thread


class PeriodicConfluenceRefresh:
    """Web-process lifecycle loop for current-account Confluence refresh."""

    def __init__(self, sessions, facts, refresh, *, interval_seconds=600,
                 thread_factory=None):
        self.interval_seconds = max(300, min(900, int(interval_seconds)))
        self._sessions = sessions; self._facts = facts; self._refresh = refresh
        self._stop = Event(); self._lock = Lock(); self._thread = None
        self._thread_factory = thread_factory or self._new_thread

    @staticmethod
    def _new_thread(target):
        return Thread(target=target, name="smarttest-confluence-periodic", daemon=True)

    def start(self):
        with self._lock:
            if self._thread is not None:
                return False
            self._thread = self._thread_factory(self._run)
            self._thread.start()
            return True

    def tick(self):
        for username, password in self._sessions.active_account_credentials():
            self._refresh.start(self._facts, username, password)

    def _run(self):
        while not self._stop.wait(self.interval_seconds):
            self.tick()

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2)
