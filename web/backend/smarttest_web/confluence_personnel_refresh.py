from __future__ import annotations

from threading import Lock

from core.logging import smart_log

from .task_manager import WEB_TASKS


class ConfluencePersonnelRefreshScheduler:
    """Schedule one non-blocking personnel refresh per account and process start."""

    def __init__(self, task_manager=WEB_TASKS):
        self._task_manager = task_manager
        self._accounts = set()
        self._lock = Lock()

    def schedule(self, account, password, owner_factory) -> bool:
        normalized = str(account or "").strip().casefold()
        if not normalized or not password:
            return False
        with self._lock:
            if normalized in self._accounts:
                return False
            self._accounts.add(normalized)
        try:
            self._task_manager.submit(
                "Refresh Confluence personnel assignments",
                lambda _token, _progress: self._run(account, password, owner_factory),
            )
        except Exception:
            with self._lock:
                self._accounts.discard(normalized)
            raise
        return True

    @staticmethod
    def _run(account, password, owner_factory):
        try:
            return owner_factory(account, password).refresh()
        except Exception as error:
            exception_type = type(error).__name__
            stage = str(getattr(error, "sync_stage", "unknown"))
            code = str(getattr(error, "sync_code", "personnel_refresh_failed"))
            status = getattr(error, "status_code", None) or getattr(getattr(error, "response", None), "status_code", None)
            reason = str(getattr(error, "sync_reason", code))
            smart_log(
                f"Confluence personnel assignment refresh failed stage={stage} code={code} "
                f"type={exception_type} http_status={status or 'unknown'} reason={reason}",
                platform="web", domain="framework", source="confluence_personnel_refresh",
                level="error", extra={
                    "exception_type": exception_type, "stage": stage,
                    "exception_code": code, "exception_message": code,
                    "http_status": status, "reason": reason,
                },
                emit_runtime_event=False,
            )
            return False
