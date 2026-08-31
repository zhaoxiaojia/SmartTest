from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from core.confluence.project import ProjectDetails


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
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(refresh, project_id): index
                for index, project_id in enumerate(identifiers)
            }
            completed = 0
            for future in as_completed(futures):
                results[futures[future]] = future.result()
                completed += 1
                progress(completed, len(identifiers))
        return results
