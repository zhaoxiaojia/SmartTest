from __future__ import annotations

from concurrent.futures import as_completed

from core.confluence.project import ProjectDetails
from .task_manager import WEB_TASKS


class ConfluenceProjectSyncCoordinator:
    """Bounded foreground orchestration over the current-cache service."""

    def __init__(self, cache_service, *, max_workers: int = 4):
        self._cache_service = cache_service
        self._max_workers = max(1, int(max_workers))

    def sync(
        self,
        project_ids,
        details: ProjectDetails,
        *,
        cancelled=lambda: False,
        progress=lambda *_: None,
    ) -> list[str]:
        identifiers = tuple(str(project_id) for project_id in project_ids)

        def refresh(project_id: str) -> str:
            if cancelled():
                return "cancelled"
            try:
                self._cache_service.refresh_project(project_id, details)
            except Exception:
                return "failed"
            return "updated"

        results = ["cancelled"] * len(identifiers)
        pending = iter(enumerate(identifiers))
        futures = {}
        for _ in range(min(self._max_workers, len(identifiers))):
            index, project_id = next(pending, (None, None))
            if project_id is not None:
                futures[WEB_TASKS.submit("confluence-project-detail", lambda _token, _progress, project_id=project_id: refresh(project_id))] = index
        completed = 0
        while futures:
            future = next(as_completed(futures))
            index = futures.pop(future)
            results[index] = future.result()
            completed += 1
            progress(completed, len(identifiers))
            next_index, project_id = next(pending, (None, None))
            if project_id is not None:
                futures[WEB_TASKS.submit("confluence-project-detail", lambda _token, _progress, project_id=project_id: refresh(project_id))] = next_index
        return results
