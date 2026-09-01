from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from core.confluence.audit import (
    AuditPeriod,
    ConfluencePageDocument,
    ConfluenceWeeklyAuditUseCase,
    export_audit_xlsx_by_product_line,
    manual_audit_period,
)
from core.confluence.project import (
    ProjectDetails,
    ProjectQuery,
)
from core.domain.detail import DetailState

from ..task_manager import WEB_TASKS
from ..project_facts_api import ProjectFactsWebOwner
from ..resource_access import remote_status


@dataclass(frozen=True)
class ResolvedConfluenceAudit:
    projects: tuple
    period: AuditPeriod


class WebConfluenceAuditOwner:
    def __init__(self, cache_service, repository, page_gateway, *, access):
        self._cache = cache_service
        self._repository = repository
        self._gateway = page_gateway
        self._access = access

    @classmethod
    def from_credentials(cls, access, password: str):
        facts = ProjectFactsWebOwner()
        return cls(*facts.audit_dependencies(access, password), access=access)

    def resolve(self, payload: dict) -> ResolvedConfluenceAudit:
        try:
            period = manual_audit_period(
                date.fromisoformat(str(payload.get("startDate") or "")),
                date.fromisoformat(str(payload.get("endDate") or "")),
            )
        except (TypeError, ValueError) as error:
            raise ValueError("invalid_input") from error
        project_ids = tuple(
            dict.fromkeys(str(item) for item in payload.get("projectIds") or ())
        )
        if project_ids:
            for project_id in project_ids:
                self._access.require("project", project_id, "catalog")
            projects = tuple(
                project for project_id in project_ids
                if (project := self._repository.get(project_id, ProjectDetails()))
                is not None
            )
        else:
            projects = self._repository.list(
                ProjectQuery.from_filters(payload.get("filters") or {}),
                0, 10000,
                visible_ids=self._access.ids("project", "catalog"),
            ).projects
        if not projects:
            raise ValueError("invalid_input")
        return ResolvedConfluenceAudit(projects, period)

    def run(self, resolved, cancellation, progress):
        cancellation.raise_if_cancelled()
        progress("refreshing_projects", 0, len(resolved.projects))
        return ConfluenceWeeklyAuditUseCase(self).run(
            resolved.projects, resolved.period,
            cancellation=cancellation, progress=progress,
            task_manager=WEB_TASKS, parent_task_id=getattr(cancellation, "task_id", ""),
        )

    def load_project_details(self, project_id, details, cancellation):
        cancellation.raise_if_cancelled()
        try:
            project = self._cache.refresh_project(
                project_id, details, cancellation=cancellation,
            )
        except Exception as error:
            cancellation.raise_if_cancelled()
            raise RuntimeError("remote_unavailable") from error
        cancellation.raise_if_cancelled()
        if project is None:
            raise RuntimeError("not_found")
        if any(
            getattr(project, name).state is DetailState.FAILED
            for name in details.sections()
        ):
            raise RuntimeError("remote_unavailable")
        return project

    def load_current_page(self, page_id, cancellation):
        cancellation.raise_if_cancelled()
        self._access.require("page", page_id, "metadata")
        page = self._read_page(page_id)
        cancellation.raise_if_cancelled()
        return _document(page)

    def load_page_versions(self, page_id, period, current, cancellation):
        cancellation.raise_if_cancelled()
        pages = [current]
        if current.updated_at is None:
            raise RuntimeError("remote_unavailable")
        if current.updated_at >= period.start:
            for version in range(current.version - 1, 0, -1):
                cancellation.raise_if_cancelled()
                page = self._read_page(page_id, version)
                cancellation.raise_if_cancelled()
                pages.append(_document(page))
                if page.updated_at is None or page.updated_at < period.start:
                    break
        return tuple(reversed(pages))

    def _read_page(self, page_id, version=None):
        self._access.require_active()
        try:
            page = (self._gateway.get_page(page_id) if version is None
                    else self._gateway.get_page_version(page_id, version))
        except Exception as error:
            self._access.require_active()
            if remote_status(error) == 403:
                self._access.revoke("page", page_id)
            if remote_status(error) == 401:
                raise PermissionError("reauthentication_required") from error
            raise
        if str(page.id) != str(page_id):
            raise PermissionError("permission_denied")
        self._access.publish((("page", page_id, "body", scope)
            for scope in self._access.scopes("page", page_id, "metadata")), lambda: None)
        return page

    @staticmethod
    def export(batch, output_dir: Path):
        return export_audit_xlsx_by_product_line(batch, output_dir)


def _document(page):
    return ConfluencePageDocument(
        page.id, page.title, page.url, page.body, page.view_body,
        page.version, page.updated_at,
    )
