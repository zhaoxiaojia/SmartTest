from __future__ import annotations

from threading import Lock
from time import perf_counter

from core.logging import smart_log

from .task_manager import WEB_TASKS, snapshot_payload


class BackgroundFactsRefresh:
    """Process-local single-flight refresh state; credentials live only in the worker closure."""

    def __init__(self, submit=None):
        self._submit = submit or self._start_thread
        self._lock = Lock()
        self._jobs = {}

    @staticmethod
    def _start_thread(work):
        return WEB_TASKS.submit("confluence-facts", lambda _token, progress: work(progress))

    @property
    def state(self):
        return self.state_for("")

    def state_for(self, access):
        with self._lock:
            return self._jobs.get(str(access).strip().casefold(), {}).get("state", "idle")

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

    def start_details(self, owner, access, password, *, filters=None, search="", on_error=None):
        account = access.session_hash
        with self._lock:
            if self._jobs.get(account, {}).get("state") == "loading":
                return False
            job = {
                "state": "loading", "completed": 0, "total": 0,
                "cancelled": False, "kind": "details",
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
                owner.refresh_and_sync_details(
                    access, password, filters=filters, search=search,
                    cancelled=cancelled,
                    progress=lambda completed, total: progress(completed, total, manager_progress),
                )
            except Exception as error:  # noqa: BLE001 - only safe job state crosses the API
                error_state = on_error(error) if on_error is not None else "failed"
                with self._lock:
                    if not job["cancelled"]:
                        job["state"] = error_state
            else:
                with self._lock:
                    if not job["cancelled"]:
                        job["state"] = "ready"

        submitted = self._submit(work)
        if submitted is not None:
            job["task_id"] = WEB_TASKS.task_id(submitted)
        return True

    def cancel(self, access):
        account = str(access).strip().casefold()
        with self._lock:
            job = self._jobs.get(account)
            if not job or job.get("kind") != "details" or job["state"] != "loading":
                return False
            job.update(cancelled=True, state="cancelled")
            return True

    def start(self, owner, access, password, *, on_error=None):
        account = access.session_hash
        with self._lock:
            if self._jobs.get(account, {}).get("state") == "loading":
                return False
            job = {"state": "loading", "completed": 0, "total": 0, "kind": "catalog"}
            self._jobs[account] = job
        smart_log("Confluence catalog background state", platform="web", domain="framework", source="confluence_catalog_refresh", emit_runtime_event=False,
                  extra={"stage": "filter.background_schedule", "duration_ms": 0, "outcome": "scheduled", "credential_present": bool(password)})

        def work(_manager_progress=lambda _completed, _total: None):
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
                    job["state"] = error_state
            else:
                with self._lock:
                    job["state"] = "ready"
                smart_log("Confluence catalog background timing", platform="web", domain="framework", source="confluence_catalog_refresh", emit_runtime_event=False,
                          extra={"stage": "filter.background_total", "duration_ms": round((perf_counter() - started) * 1000, 3),
                                 "outcome": "success", "refresh_state": "ready"})

        self._submit(work)
        return True
