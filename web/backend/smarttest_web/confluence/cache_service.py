from __future__ import annotations

from dataclasses import replace
from core.confluence.project import (
    Project,
    ProjectDetails,
    ProjectPage,
    ProjectQuery,
    ProjectSyncScope,
)
from core.domain.detail import DetailSection, DetailState

from .project_repository import ConfluenceProjectRepository
from ..resource_access import remote_status


_ERROR_CODES = {
    "authentication_failed", "permission_denied", "not_found", "rate_limited",
    "remote_unavailable", "mapping_failed", "database_failed",
}


class ConfluenceProjectCacheService:
    def __init__(self, gateway, mapper, repository: ConfluenceProjectRepository, *, access):
        self._gateway = gateway
        self._mapper = mapper
        self._repository = repository
        self._access = access

    def list_projects(self, query: ProjectQuery, page: int = 0, page_size: int = 100) -> ProjectPage:
        visible = self._access.ids("project", "catalog")
        cached = self._repository.list(query, page, page_size, visible_ids=visible)
        if visible:
            return cached
        payload = self._gateway.query_project_catalog(query, page)
        projects = self._map_projects(payload.get("projects") or ())
        self._publish_catalog(projects[0], ())
        return self._repository.list(query, page, page_size, visible_ids=self._access.ids("project", "catalog"))

    def read_project(self, project_id, details):
        self._access.require("project", project_id, "catalog")
        allowed = tuple(name for name in details.sections()
                        if name == "facts" or self._access.allows("project", project_id, name))
        project = self._repository.get(project_id, ProjectDetails(**{name: True for name in allowed}))
        if project is None:
            return None
        evidence = project.evidence
        if evidence.value is not None:
            pages = self._access.ids("page", "metadata")
            evidence = replace(evidence, value=tuple(item for item in evidence.value if item.source == "catalog" or item.page.page_id in pages))
        owners = tuple(person for role in project.roles.value or () for person in role.people)
        return replace(project, evidence=evidence, owner_summary=owners)

    def get_project(self, project_id: str, details: ProjectDetails, cancellation=None) -> Project | None:
        project = self.read_project(project_id, details)
        for section in details.sections():
            if getattr(project, section).state is DetailState.UNLOADED:
                _raise_if_cancelled(cancellation)
                loaded = self._refresh_section(project_id, section)
                _raise_if_cancelled(cancellation)
                project = replace(self.read_project(project_id, details), **{section: loaded})
        return project

    def refresh_projects(self, scope: ProjectSyncScope) -> dict:
        self._access.require_active()
        try:
            payload = self._gateway.refresh_project_catalogs(scope)
        except Exception as error:
            if remote_status(error) == 401:
                raise PermissionError("reauthentication_required") from error
            raise
        projects, failures = self._map_projects(payload.get("projects") or ())
        self._publish_catalog(projects, () if failures else payload.get("complete_spaces") or ())
        failures.extend(str(item) for item in payload.get("failed_product_spaces") or ())
        return {"projects": tuple(projects), "failed": tuple(failures)}

    def refresh_project(self, project_id: str, details: ProjectDetails, cancellation=None) -> Project:
        _raise_if_cancelled(cancellation)
        self._access.require("project", project_id, "catalog")
        self._gateway.get_project_catalog(project_id)  # Reset this request's extracted-detail buffer.
        _raise_if_cancelled(cancellation)
        project = self.read_project(project_id, details)
        for section in details.sections():
            _raise_if_cancelled(cancellation)
            loaded = self._refresh_section(project_id, section)
            project = replace(project, **{section: loaded})
            _raise_if_cancelled(cancellation)
        return project

    def invalidate_project(self, project_id: str) -> None:
        self._access.require("project", project_id, "catalog")
        self._access.revoke("project", project_id)

    def clear(self) -> None:
        for key in self._access.ids("project", "catalog"):
            self._access.revoke("project", key)

    def _refresh_section(self, project_id: str, name: str) -> None:
        details = ProjectDetails(**{name: True})
        current = self.read_project(project_id, details)
        try:
            self._access.require_active()
            payload = self._gateway.load_project_sections(project_id, (name,))
            if name not in payload:
                raise PermissionError("permission_denied")
            refreshed = self._mapper.with_sections(current, payload, (name,))
            section = getattr(refreshed, name)
        except Exception as error:
            self._access.require_active()
            if remote_status(error) == 401:
                raise PermissionError("reauthentication_required") from error
            if remote_status(error) == 403:
                self._access.revoke("project", project_id, name)
                self._access.publish((), lambda: None, replace_scopes=(f"{project_id}:{name}",))
                raise PermissionError("permission_denied") from error
            if isinstance(error, PermissionError):
                raise
            previous = getattr(current, name)
            return DetailSection.failed(
                _error_code(error), value=previous.value,
                source_revision=previous.source_revision,
            )
        scope = f"{project_id}:{name}"
        grants = [("project", project_id, name, scope), *payload.get("access_grants", ())]
        stored = section
        if name == "evidence":
            old = self._repository.get(project_id, details).evidence.value or ()
            merged = {(item.source, item.page.page_id): item for item in old}
            merged.update({(item.source, item.page.page_id): item for item in section.value or ()})
            stored = replace(section, value=tuple(merged.values()))
        self._access.publish(grants, lambda: getattr(self._repository, f"replace_{name}")(project_id, stored),
                             replace_scopes=(scope,))
        return section

    def _publish_catalog(self, projects, complete_spaces):
        self._access.publish(
            [("project", project.identity.project_id, "catalog", project.product_space.key) for project in projects]
            + [("catalog", space, "ready", space) for space in complete_spaces],
            lambda: self._save_catalog_projects(projects), replace_scopes=complete_spaces,
        )

    def _map_projects(self, rows) -> tuple[list[Project], list[str]]:
        projects, failures = [], []
        for row in rows:
            try:
                project = self._mapper.from_catalog(row)
                if not project.identity.project_id or not project.product_space.key:
                    raise ValueError("mapping_failed")
                projects.append(project)
            except Exception:
                failures.append(str(row.get("project_id") or row.get("identity") or "mapping_failed"))
        return projects, failures

    def _save_catalog_projects(self, projects) -> None:
        projects = tuple(projects)
        self._repository.save_core(projects)
        for project in projects:
            if project.facts.state is DetailState.LOADED:
                self._repository.replace_facts(project.identity.project_id, project.facts)


def _error_code(error: Exception) -> str:
    code = str(getattr(error, "code", "") or "")
    return code if code in _ERROR_CODES else "remote_unavailable"


def _raise_if_cancelled(cancellation) -> None:
    if cancellation is not None:
        cancellation.raise_if_cancelled()
