from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


class ConfluenceProjectSyncCoordinator:
    """Bounded, process-wide single-flight coordinator for current project details."""

    _guard = Lock()
    _inflight = {}

    def __init__(self, repository, *, max_workers=4):
        self.repository = repository
        self.max_workers = max(1, int(max_workers))

    def sync(self, projects, fetch, *, cancelled=lambda: False, progress=lambda *_: None):
        rows = list(projects)

        def one(project):
            if cancelled():
                return "cancelled"
            key = str(project.get("page_id") or project.get("identity"))
            source_version = int((project.get("detail_source") or {}).get("version") or 0)
            if source_version and self.repository.stored_version(key) == source_version:
                return "skipped"
            with self._guard:
                future = self._inflight.get(key)
                if future is None:
                    future = _SharedResult()
                    self._inflight[key] = future
                    owner = True
                else:
                    owner = False
            if owner:
                try:
                    self.repository.upsert_project(fetch(project))
                    future.set("updated")
                except Exception as exc:  # noqa: BLE001
                    self.repository.mark_project_stale(key, type(exc).__name__)
                    future.set("failed")
            try:
                return future.get()
            finally:
                if owner:
                    with self._guard:
                        self._inflight.pop(key, None)

        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [pool.submit(one, row) for row in rows]
            for future in as_completed(futures):
                results.append(future.result()); progress(len(results), len(futures))
        return results


class _SharedResult:
    def __init__(self):
        from threading import Event
        self._event = Event(); self._value = None; self._error = None

    def set(self, value): self._value = value; self._event.set()
    def get(self):
        self._event.wait()
        if self._error: raise self._error
        return self._value
