from threading import RLock

from core.async_tasks import AsyncTaskManager


class ScopedTaskIndex:
    """Authorization-only mapping from a Web scope to its current manager task."""

    def __init__(self, manager):
        self.manager = manager
        self._lock = RLock()
        self._tasks = {}

    def replace(self, scope, task_id):
        key = tuple(str(value) for value in scope)
        with self._lock:
            previous = self._tasks.get(key)
            self._tasks[key] = str(task_id)
        if previous and previous != str(task_id):
            self.manager.cancel(previous)

    def owns(self, scope, task_id):
        key = tuple(str(value) for value in scope)
        with self._lock:
            return self._tasks.get(key) == str(task_id)

    def current(self, scope):
        key = tuple(str(value) for value in scope)
        with self._lock:
            return self._tasks.get(key, "")

    def clear_prefix(self, *prefix):
        prefix = tuple(str(value) for value in prefix)
        with self._lock:
            owned = [self._tasks.pop(key) for key in tuple(self._tasks) if key[:len(prefix)] == prefix]
        for task_id in owned:
            self.manager.cancel(task_id)


class WebTaskManager:
    """Stable process reference whose concrete owner follows the app lifespan."""

    def __init__(self, factory=AsyncTaskManager.from_environment):
        self._factory = factory
        self._lock = RLock()
        self._manager = None
        self._leases = 0

    def open(self):
        with self._lock:
            self._leases += 1
            if self._manager is None:
                self._manager = self._factory()

    def close(self):
        with self._lock:
            if self._leases:
                self._leases -= 1
            if self._leases:
                return
            manager, self._manager = self._manager, None
        if manager is not None:
            manager.close()

    def __getattr__(self, name):
        with self._lock:
            if self._manager is None:
                self._manager = self._factory()
            return getattr(self._manager, name)


def snapshot_payload(snapshot):
    """Return the safe root-task fields used by existing Confluence status responses."""
    child = snapshot.visible_child
    return {
        "state": snapshot.state,
        "progress": {"processed": snapshot.progress[0], "total": snapshot.progress[1]},
        "revision": snapshot.revision,
        "visibleChild": None if child is None else {"label": child.label, "state": child.state},
    }


WEB_TASKS = WebTaskManager()


def open_web_tasks() -> None:
    WEB_TASKS.open()


def close_web_tasks() -> None:
    WEB_TASKS.close()
