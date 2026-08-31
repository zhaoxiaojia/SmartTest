from __future__ import annotations

from typing import Any

from core.confluence.project import Project, ProjectDetails, ProjectPage, ProjectQuery, ProjectSyncResult, ProjectSyncScope
from core.confluence.project_mapper import ConfluenceProjectMapper


class ProjectRepository:
    def __init__(self, gateway: Any, mapper: ConfluenceProjectMapper | None = None) -> None:
        self._gateway = gateway
        self._mapper = mapper or ConfluenceProjectMapper()

    def query(self, filters: ProjectQuery, page: int = 0) -> ProjectPage:
        payload = self._gateway.query_project_catalog(filters, page)
        rows = payload.get("projects") or ()
        return ProjectPage(tuple(self._mapper.from_catalog(row) for row in rows), int(payload.get("page") or page), int(payload.get("page_size") or len(rows)), int(payload.get("total") or len(rows)))

    def get(self, project_id: str) -> Project:
        return self._mapper.from_catalog(self._gateway.get_project_catalog(project_id))

    def load_details(self, project: Project, details: ProjectDetails) -> Project:
        sections = details.sections()
        if not sections:
            return project
        return self._mapper.with_sections(project, self._gateway.load_project_sections(project.identity.project_id, sections), sections)

    def refresh_catalogs(self, scope: ProjectSyncScope) -> ProjectSyncResult:
        payload = self._gateway.refresh_project_catalogs(scope)
        return ProjectSyncResult(tuple(self._mapper.from_catalog(row) for row in payload.get("projects") or ()), tuple(str(item) for item in payload.get("failed_product_spaces") or ()))
