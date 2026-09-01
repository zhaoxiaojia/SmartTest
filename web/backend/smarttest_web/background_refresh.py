from __future__ import annotations

from threading import Lock

from .task_manager import WEB_TASKS, snapshot_payload


class BackgroundFactsRefresh:
    """Process-local single-flight refresh state; credentials live only in the worker closure."""

    def __init__(self, submit=None):
        self._submit = submit or self._start_thread
        self._lock = Lock()
        self._states = {}
        self._jobs = {}

    @staticmethod
    def _start_thread(work):
        return WEB_TASKS.submit("confluence-facts", lambda _token, progress: work(progress))

    @property
    def state(self):
        return self.state_for("")

    def state_for(self, access):
        with self._lock:
            return self._states.get(str(access).strip().casefold(), "idle")

    def record_selection(self, access, filters, search, result) -> None:
        if result.get("state") not in {"ready", "partial_success"}:
            return
        project_ids = tuple(dict.fromkeys(
            str(row.get("project_id") or "") for row in result.get("projects", ())
            if str(row.get("project_id") or "")
        ))
        account = str(access).strip().casefold()
        with self._lock:
            job = self._jobs.setdefault(account, {
                "state": "idle", "completed": 0, "total": 0, "cancelled": False,
            })
            if job["state"] != "loading":
                job.update(filters=filters or {}, search=search, project_ids=project_ids)

    def applied_selection(self, access):
        account = str(access).strip().casefold()
        with self._lock:
            job = self._jobs.get(account)
            if not job or job["state"] in {"loading", "failed", "cancelled"} or "project_ids" not in job:
                return None
            return {
                "filters": job.get("filters", {}), "search": job.get("search", ""),
                "project_ids": job.get("project_ids", ()),
            }

    def status_for(self, access):
        account = str(access).strip().casefold()
        with self._lock:
            job = self._jobs.get(account)
            if not job:
                return {"state": "idle", "completed": 0, "total": 0}
            status = {key: job[key] for key in ("state", "completed", "total")}
            task_id = job.get("task_id")
        if task_id:
            try:
                status["task"] = snapshot_payload(WEB_TASKS.snapshot(task_id))
            except KeyError:
                pass
        return status

    def start_details(self, owner, access, password, *, filters=None, search=""):
        account = access.session_hash
        with self._lock:
            if self._jobs.get(account, {}).get("state") == "loading":
                return False
            job = {
                "state": "loading", "completed": 0, "total": 0, "cancelled": False,
                "filters": filters or {}, "search": search, "project_ids": (),
            }
            self._jobs[account] = job

        def cancelled():
            with self._lock:
                return bool(job["cancelled"])

        def progress(completed, total, manager_progress=lambda _completed, _total: None):
            with self._lock:
                if not job["cancelled"]:
                    job.update(completed=completed, total=total)
            manager_progress(completed, total)

        def work(manager_progress=lambda _completed, _total: None):
            if cancelled():
                return
            try:
                result = owner.sync_details(access, password, filters=filters, search=search,
                                            cancelled=cancelled,
                                            progress=lambda completed, total: progress(completed, total, manager_progress))
                project_ids = tuple(dict.fromkeys(
                    str(row.get("project_id") or "") for row in result.get("projects", ())
                    if str(row.get("project_id") or "")
                ))
            except Exception:  # noqa: BLE001 - only safe job state crosses the API
                with self._lock:
                    if not job["cancelled"]:
                        job["state"] = "failed"
            else:
                with self._lock:
                    if not job["cancelled"]:
                        job.update(state="ready", project_ids=project_ids)

        submitted = self._submit(work)
        if submitted is not None:
            job["task_id"] = WEB_TASKS.task_id(submitted)
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
