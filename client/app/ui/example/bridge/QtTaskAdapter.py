from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import Lock
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication

from core.async_tasks import AsyncTaskManager


@dataclass(frozen=True)
class _Completion:
    key: int
    result: object = None
    error: Exception | None = None


class QtTaskAdapter(QObject):
    """Deliver AsyncTaskManager completions to QObject owners on the GUI thread."""

    _completed = Signal(object)
    _invoked = Signal(object)

    def __init__(self, *, manager: AsyncTaskManager):
        super().__init__(QGuiApplication.instance())
        self._manager = manager
        self._callbacks: dict[int, tuple[Callable | None, Callable | None]] = {}
        self._lock = Lock()
        self._next_key = 0
        self._completed.connect(self._deliver, Qt.QueuedConnection)
        self._invoked.connect(self._invoke, Qt.QueuedConnection)

    def submit(self, label: str, work: Callable, *, on_success: Callable | None = None,
               on_error: Callable | None = None):
        with self._lock:
            self._next_key += 1
            key = self._next_key
            self._callbacks[key] = (on_success, on_error)
        future = self._manager.submit(label, lambda _token, _progress: work())

        def completed(done):
            try:
                result = done.result()
            except Exception as error:  # noqa: BLE001 - delivered to the QObject owner
                self._completed.emit(_Completion(key, error=error))
            else:
                self._completed.emit(_Completion(key, result=result))

        future.add_done_callback(completed)
        return future

    def to_thread(self, label: str, work: Callable, *args, **kwargs):
        future = self._manager.submit(label, lambda _token, _progress: work(*args, **kwargs))
        return asyncio.wrap_future(future)

    def schedule_coroutine(self, loop, label: str, coroutine):
        coroutine_future = asyncio.run_coroutine_threadsafe(coroutine, loop)

        def wait(token, _progress):
            while True:
                token.raise_if_cancelled()
                try:
                    return coroutine_future.result(timeout=0.05)
                except TimeoutError:
                    continue

        return self._manager.submit(label, wait)

    def post(self, callback: Callable, *args) -> None:
        self._invoked.emit((callback, args))

    @Slot(object)
    def _deliver(self, completion: _Completion) -> None:
        with self._lock:
            success, failure = self._callbacks.pop(completion.key, (None, None))
        if completion.error is None:
            if success is not None:
                success(completion.result)
        elif failure is not None:
            failure(completion.error)

    @Slot(object)
    def _invoke(self, invocation) -> None:
        callback, args = invocation
        callback(*args)
