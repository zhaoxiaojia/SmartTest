from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Event, RLock
from uuid import uuid4


class AuditConflictError(RuntimeError):
    pass


class AuditNotFoundError(KeyError):
    pass


class AuditCancelled(RuntimeError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise AuditCancelled("cancelled")


@dataclass
class ManualAuditTask:
    id: str
    source: str
    session_id: str
    status: str = "queued"
    stage: str = ""
    processed: int = 0
    total: int = 0
    result: object | None = None
    error_code: str = ""
    download_id: str = ""
    context: object | None = None
    token: CancellationToken = field(default_factory=CancellationToken, repr=False)
    future: Future | None = field(default=None, repr=False)
    validate: object = field(default=lambda: None, repr=False)


class ManualAuditRegistry:
    _ACTIVE = {"queued", "running"}

    def __init__(self, *, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
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
            task = ManualAuditTask(uuid4().hex, source, session_id, context=context, validate=validate)
            self._tasks[task.id] = task
            task.future = self._executor.submit(
                self._run, task, runner, finalizer,
            )
            return task

    def close(self) -> None:
        with self._lock:
            tasks = tuple(self._tasks.values())
        for task in tasks:
            if task.status in self._ACTIVE:
                task.token.cancel()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _run(self, task: ManualAuditTask, runner, finalizer) -> None:
        with self._lock:
            task.status = "running"
        try:
            task.validate()
            result = runner(task.token, lambda *values: self._progress(task, *values))
            task.token.raise_if_cancelled()
            task.validate()
            download_id = ""
            if finalizer is not None:
                self._progress(task, "exporting", task.processed, task.total)
                download_id = str(finalizer(task, result))
                task.token.raise_if_cancelled()
                task.validate()
        except AuditCancelled:
            with self._lock:
                task.status = "cancelled"
                task.error_code = "cancelled"
        except Exception as error:
            with self._lock:
                task.status = "failed"
                task.error_code = _error_code(error)
        else:
            with self._lock:
                task.result = result
                task.download_id = download_id
                task.status = "completed"

    def _progress(self, task: ManualAuditTask, stage: str, processed=0, total=0) -> None:
        task.validate()
        with self._lock:
            task.stage = str(stage)
            task.processed = int(processed)
            task.total = int(total)

    def cancel_session(self, session_id):
        with self._lock:
            for task in self._tasks.values():
                if task.session_id == session_id:
                    task.token.cancel()

    def get(self, audit_id: str, session_id: str) -> ManualAuditTask:
        with self._lock:
            task = self._tasks.get(audit_id)
            if task is None or task.session_id != session_id:
                raise AuditNotFoundError(audit_id)
            return task

    def wait(self, audit_id: str, session_id: str) -> ManualAuditTask:
        task = self.get(audit_id, session_id)
        if task.future is not None:
            task.future.result(timeout=10)
        return self.get(audit_id, session_id)

    def cancel(self, audit_id: str, session_id: str) -> ManualAuditTask:
        task = self.get(audit_id, session_id)
        task.token.cancel()
        return task

    def exported(
        self, audit_id: str, session_id: str, download_id: str,
    ) -> ManualAuditTask:
        task = self.get(audit_id, session_id)
        with self._lock:
            task.download_id = download_id
            task.status = "exported"
        return task


def _error_code(error: Exception) -> str:
    code = str(getattr(error, "code", "") or error)
    allowed = {
        "invalid_input", "authentication_failed", "permission_denied",
        "not_found", "rate_limited", "remote_unavailable",
        "mapping_failed", "audit_failed", "export_failed", "cancelled",
    }
    return code if code in allowed else "audit_failed"
