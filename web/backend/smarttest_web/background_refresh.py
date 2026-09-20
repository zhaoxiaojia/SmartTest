from __future__ import annotations

from threading import Lock
from time import perf_counter

from core.logging import smart_log

from .task_manager import WEB_TASKS, ScopedTaskIndex, snapshot_payload


class BackgroundFactsRefresh:
    """Process-local single-flight refresh state; credentials live only in the worker closure."""

    def __init__(self, submit=None):
        self._submit = submit or self._start_thread
        self._lock = Lock()
        self._jobs = {}
        self._index = ScopedTaskIndex(WEB_TASKS)

    @staticmethod
    def _start_thread(work):
        return WEB_TASKS.submit("confluence-facts", lambda token, progress: work(progress, token))

    @property
    def state(self):
        return self.state_for("")

    def state_for(self, access):
        return self.status_for(access)["state"]

    def status_for(self, access):
        account = str(access).strip().casefold()
        with self._lock:
            job = self._jobs.get(account)
            if not job:
                return {"state": "idle", "completed": 0, "total": 0}
            status = {"state": job.get("terminal") or "loading",
                      "completed": job["completed"], "total": job["total"]}
            task_id = self._index.current((account, "confluence"))
        if task_id:
            try:
                task = WEB_TASKS.snapshot(task_id)
                status.update(
                    state={"queued": "loading", "running": "loading", "completed": job.get("terminal") or "ready"}.get(task.state, task.state),
                    completed=task.progress[0], total=task.progress[1], task=snapshot_payload(task),
                )
            except KeyError:
                pass
        return status

    def start_details(self, owner, access, password, *, filters=None, search="", on_error=None):
        account = access.session_hash
        with self._lock:
            if self._active(account, self._jobs.get(account)):
                return False
            job = {
                "terminal": "", "completed": 0, "total": 0, "kind": "details",
            }
            self._jobs[account] = job

        def cancelled():
            with self._lock:
                task_id = self._index.current((account, "confluence"))
            if not task_id:
                return bool(job.get("terminal") == "cancelled")
            try:
                return WEB_TASKS.snapshot(task_id).state == "cancelled"
            except KeyError:
                return True

        def progress(completed, total, manager_progress=lambda _completed, _total: None):
            with self._lock:
                job.update(completed=completed, total=total)
            manager_progress(completed, total)

        def work(manager_progress=lambda _completed, _total: None, manager_token=None):
            if cancelled():
                return
            try:
                options = {
                    "filters": filters, "search": search, "cancelled": cancelled,
                    "progress": lambda completed, total: progress(completed, total, manager_progress),
                }
                if manager_token is not None:
                    options["parent_task_id"] = manager_token.task_id
                owner.refresh_and_sync_details(access, password, **options)
            except Exception as error:  # noqa: BLE001 - only safe job state crosses the API
                error_state = on_error(error) if on_error is not None else "failed"
                with self._lock:
                    job["terminal"] = error_state
            else:
                if not cancelled():
                    with self._lock:
                        job["terminal"] = "ready"

        submitted = self._submit(work)
        if submitted is not None:
            self._index.replace((account, "confluence"), WEB_TASKS.task_id(submitted))
        return True

    def cancel(self, access):
        account = str(access).strip().casefold()
        with self._lock:
            job = self._jobs.get(account)
            if not job or job.get("kind") != "details" or not self._active(account, job):
                return False
            job["terminal"] = "cancelled"
            task_id = self._index.current((account, "confluence"))
        return WEB_TASKS.cancel(task_id) if task_id else True

    def start(self, owner, access, password, *, on_error=None):
        account = access.session_hash
        with self._lock:
            if self._active(account, self._jobs.get(account)):
                return False
            job = {"terminal": "", "completed": 0, "total": 0, "kind": "catalog"}
            self._jobs[account] = job
        smart_log("Confluence catalog background state", platform="web", domain="framework", source="confluence_catalog_refresh", emit_runtime_event=False,
                  extra={"stage": "filter.background_schedule", "duration_ms": 0, "outcome": "scheduled", "credential_present": bool(password)})

        def work(_manager_progress=lambda _completed, _total: None, _manager_token=None):
            started = perf_counter()
            smart_log("Confluence catalog background state", platform="web", domain="framework", source="confluence_catalog_refresh", emit_runtime_event=False,
                      extra={"stage": "filter.background_start", "duration_ms": 0, "outcome": "started"})
            try:
                result = owner.refresh(access, password)
                smart_log("Confluence catalog background timing", platform="web", domain="framework", source="confluence_catalog_refresh", emit_runtime_event=False,
                          extra={"stage": "filter.background_owner", "duration_ms": round((perf_counter() - started) * 1000, 3),
                                 "result_state": str(result.get("state") or "") if isinstance(result, dict) else "complete",
                                 "project_count": len(result.get("projects") or ()) if isinstance(result, dict) else 0})
            except Exception as error:  # noqa: BLE001 - the public state is intentionally safe
                error_state = on_error(error) if on_error is not None else "failed"
                smart_log("Confluence catalog background timing", platform="web", domain="framework", level="error", source="confluence_catalog_refresh", emit_runtime_event=False,
                          extra={"stage": "filter.background_total", "duration_ms": round((perf_counter() - started) * 1000, 3),
                                 "outcome": "failure", "error_state": error_state, "exception_type": type(error).__name__,
                                 "sqlite_error_name": str(getattr(error, "sqlite_errorname", "") or "")})
                with self._lock:
                    job["terminal"] = error_state
            else:
                with self._lock:
                    job["terminal"] = "ready"
                smart_log("Confluence catalog background timing", platform="web", domain="framework", source="confluence_catalog_refresh", emit_runtime_event=False,
                          extra={"stage": "filter.background_total", "duration_ms": round((perf_counter() - started) * 1000, 3),
                                 "outcome": "success", "refresh_state": "ready"})

        submitted = self._submit(work)
        if submitted is not None:
            self._index.replace((account, "confluence"), WEB_TASKS.task_id(submitted))
        return True

    def _active(self, account, job):
        if not job or job.get("terminal"):
            return False
        task_id = self._index.current((account, "confluence"))
        if not task_id:
            return True
        try:
            return WEB_TASKS.snapshot(task_id).state in {"queued", "running"}
        except KeyError:
            return False
