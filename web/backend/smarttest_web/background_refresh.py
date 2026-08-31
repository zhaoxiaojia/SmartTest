from __future__ import annotations

from threading import Lock, Thread


class BackgroundFactsRefresh:
    """Process-local single-flight refresh state; credentials live only in the worker closure."""

    def __init__(self, submit=None):
        self._submit = submit or self._start_thread
        self._lock = Lock()
        self._states = {}
        self._jobs = {}

    @staticmethod
    def _start_thread(work):
        Thread(target=work, name="smarttest-confluence-facts", daemon=True).start()

    @property
    def state(self):
        return self.state_for("")

    def state_for(self, username):
        with self._lock:
            return self._states.get(str(username).strip().casefold(), "idle")

    def status_for(self, username):
        account = str(username).strip().casefold()
        with self._lock:
            job = self._jobs.get(account)
            if job:
                return {key: job[key] for key in ("state", "completed", "total", "revision")}
            return {"state": self._states.get(account, "idle"), "completed": 0,
                    "total": 0, "revision": None}

    def start_details(self, owner, username, password, *, filters=None, search=""):
        account = str(username).strip().casefold()
        with self._lock:
            if self._jobs.get(account, {}).get("state") == "loading":
                return False
            previous_revision = self._jobs.get(account, {}).get("revision")
            job = {"state": "loading", "completed": 0, "total": 0,
                   "revision": previous_revision if previous_revision is not None else 0,
                   "cancelled": False}
            self._jobs[account] = job

        def cancelled():
            with self._lock:
                return bool(job["cancelled"])

        def progress(completed, total):
            with self._lock:
                if not job["cancelled"]:
                    job.update(completed=completed, total=total)

        def work():
            if cancelled():
                return
            try:
                result = owner.sync_details(username, password, filters=filters, search=search,
                                            cancelled=cancelled, progress=progress)
            except Exception:  # noqa: BLE001 - only safe job state crosses the API
                with self._lock:
                    if not job["cancelled"]:
                        job["state"] = "failed"
            else:
                with self._lock:
                    if not job["cancelled"]:
                        job.update(state="ready", revision=(result or {}).get("revision"))

        self._submit(work)
        return True

    def cancel(self, username):
        account = str(username).strip().casefold()
        with self._lock:
            job = self._jobs.get(account)
            if not job or job["state"] != "loading":
                return False
            job.update(cancelled=True, state="cancelled")
            return True

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
