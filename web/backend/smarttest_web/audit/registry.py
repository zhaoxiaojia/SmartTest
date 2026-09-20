from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from uuid import uuid4

from core.async_tasks import TaskCancelled

from ..task_manager import WEB_TASKS


class AuditConflictError(RuntimeError):
    pass


class AuditNotFoundError(KeyError):
    pass


class AuditCancelled(RuntimeError):
    pass


@dataclass
class ManualAuditTask:
    id: str
    source: str
    session_id: str
    stage: str = ""
    result: object | None = None
    error_code: str = ""
    download_id: str = ""
    context: object | None = None
    manager_task_id: str = field(default="", repr=False)
    manager: object = field(default=WEB_TASKS, repr=False)
    exported_state: bool = field(default=False, repr=False)
    validate: object = field(default=lambda: None, repr=False)

    @property
    def status(self):
        if self.exported_state:
            return "exported"
        if not self.manager_task_id:
            return "queued"
        return self.manager.snapshot(self.manager_task_id).state

    @property
    def processed(self):
        return self.manager.snapshot(self.manager_task_id).progress[0] if self.manager_task_id else 0

    @property
    def total(self):
        return self.manager.snapshot(self.manager_task_id).progress[1] if self.manager_task_id else 0


class ManualAuditRegistry:
    _ACTIVE = {"queued", "running"}

    def __init__(self):
        self._tasks_manager = WEB_TASKS
        self._tasks: dict[str, ManualAuditTask] = {}
        self._lock = RLock()

    def create(
        self, source: str, session_id: str, runner, *, context=None,
        finalizer=None,
        validate=lambda: None,
    ) -> ManualAuditTask:
        with self._lock:
            if any(
                task.session_id == session_id
                and task.source == source
                and task.status in self._ACTIVE
                for task in self._tasks.values()
            ):
                raise AuditConflictError(source)
            task = ManualAuditTask(uuid4().hex, source, session_id, context=context,
                                   manager=self._tasks_manager, validate=validate)
            self._tasks[task.id] = task
            future = self._tasks_manager.submit_coordinator(
                "manual-audit", lambda manager_token, progress: self._run(
                    task, runner, finalizer, progress, manager_token,
                ),
            )
            task.manager_task_id = self._tasks_manager.task_id(future)
            return task

    def close(self) -> None:
        with self._lock:
            tasks = tuple(self._tasks.values())
        for task in tasks:
            if task.status in self._ACTIVE:
                self._tasks_manager.cancel(task.manager_task_id)

    def _run(self, task: ManualAuditTask, runner, finalizer, manager_progress, manager_token) -> None:
        try:
            task.validate()
            result = runner(
                manager_token,
                lambda *values: self._progress(task, *values, manager_progress=manager_progress),
            )
            manager_token.raise_if_cancelled()
            task.validate()
            download_id = ""
            if finalizer is not None:
                self._progress(task, "exporting", task.processed, task.total)
                download_id = str(finalizer(task, result))
                manager_token.raise_if_cancelled()
                task.validate()
        except (AuditCancelled, TaskCancelled) as error:
            with self._lock:
                task.error_code = "cancelled"
            raise TaskCancelled("cancelled") from error
        except Exception as error:
            with self._lock:
                task.error_code = _error_code(error)
            raise
        else:
            with self._lock:
                task.result = result
                task.download_id = download_id

    def _progress(self, task: ManualAuditTask, stage: str, processed=0, total=0, manager_progress=None) -> None:
        task.validate()
        with self._lock:
            task.stage = str(stage)
        if manager_progress is not None:
            manager_progress(processed, total)

    def cancel_session(self, session_id):
        with self._lock:
            for task in self._tasks.values():
                if task.session_id == session_id:
                    self._tasks_manager.cancel(task.manager_task_id)

    def get(self, audit_id: str, session_id: str) -> ManualAuditTask:
        with self._lock:
            task = self._tasks.get(audit_id)
            if task is None or task.session_id != session_id:
                raise AuditNotFoundError(audit_id)
            return task

    def wait(self, audit_id: str, session_id: str) -> ManualAuditTask:
        task = self.get(audit_id, session_id)
        self._tasks_manager.join(task.manager_task_id, timeout=10)
        return self.get(audit_id, session_id)

    def cancel(self, audit_id: str, session_id: str) -> ManualAuditTask:
        task = self.get(audit_id, session_id)
        self._tasks_manager.cancel(task.manager_task_id)
        return task

    def exported(
        self, audit_id: str, session_id: str, download_id: str,
    ) -> ManualAuditTask:
        task = self.get(audit_id, session_id)
        with self._lock:
            task.download_id = download_id
            task.exported_state = True
        return task


def _error_code(error: Exception) -> str:
    code = str(getattr(error, "code", "") or error)
    allowed = {
        "invalid_input", "authentication_failed", "permission_denied",
        "not_found", "rate_limited", "remote_unavailable",
        "mapping_failed", "audit_failed", "export_failed", "cancelled",
    }
    return code if code in allowed else "audit_failed"
