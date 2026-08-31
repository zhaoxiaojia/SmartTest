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

    def state_for(self, access):
        with self._lock:
            return self._states.get(str(access).strip().casefold(), "idle")

    def status_for(self, access):
        account = str(access).strip().casefold()
        with self._lock:
            job = self._jobs.get(account)
            if job:
                return {key: job[key] for key in ("state", "completed", "total")}
            return {"state": "idle", "completed": 0, "total": 0}

    def start_details(self, owner, access, password, *, filters=None, search=""):
        account = access.session_hash
        with self._lock:
            if self._jobs.get(account, {}).get("state") == "loading":
                return False
            job = {
                "state": "loading", "completed": 0, "total": 0, "cancelled": False,
            }
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
                owner.sync_details(access, password, filters=filters, search=search,
                                   cancelled=cancelled, progress=progress)
            except Exception:  # noqa: BLE001 - only safe job state crosses the API
                with self._lock:
                    if not job["cancelled"]:
                        job["state"] = "failed"
            else:
                with self._lock:
                    if not job["cancelled"]:
                        job["state"] = "ready"

        self._submit(work)
        return True

    def cancel(self, access):
        account = str(access).strip().casefold()
        with self._lock:
            job = self._jobs.get(account)
            if not job or job["state"] != "loading":
                return False
            job.update(cancelled=True, state="cancelled")
            return True

    def start(self, owner, access, password):
        account = access.session_hash
        with self._lock:
            if self._states.get(account) == "loading":
                return False
            self._states[account] = "loading"

        def work():
            try:
                owner.refresh(access, password)
            except Exception:  # noqa: BLE001 - the public state is intentionally safe
                with self._lock:
                    self._states[account] = "failed"
            else:
                with self._lock:
                    self._states[account] = "ready"

        self._submit(work)
        return True
