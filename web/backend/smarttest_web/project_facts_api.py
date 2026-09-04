from __future__ import annotations

from .task_manager import WEB_TASKS

import os
from threading import Lock
from time import perf_counter

from core.confluence import ConfluenceGateway, ConfluenceGatewayConfig
from core.confluence.project import (
    ProjectDetails,
    ProjectQuery,
    ProjectSyncScope,
)
from core.confluence.project_catalog import (
    PRODUCT_SPACE_FACET,
    PROJECT_SPACE_FACET_DEFINITIONS,
    extract_project_detail,
    query_project_facts,
    refresh_project_catalogs,
)
from core.confluence.project_discovery import PRODUCT_LINES
from core.confluence.project_mapper import ConfluenceProjectMapper
from core.logging import smart_log

from .confluence.cache_service import ConfluenceProjectCacheService
from .confluence.project_repository import ConfluenceProjectRepository
from .confluence_sync import ConfluenceProjectSyncCoordinator
from .database import WebDatabase
from .session import default_web_database_path

PAGE_CATALOG_PRODUCT_SPACES = ("TV", "SDPL", "DOPL", "OOPL")


class _QueryAccessSnapshot:
    """Stable authorization view for one cached query while catalog grants update."""

    _keys = (
        ("project", "catalog"), ("project", "roles"), ("project", "evidence"),
        ("catalog", "ready"),
        ("page", "metadata"),
    )

    def __init__(self, access):
        access.require_active()
        self._ids = {key: frozenset(access.ids(*key)) for key in self._keys}

    def ids(self, kind, capability):
        return self._ids.get((kind, capability), frozenset())

    def allows(self, kind, resource_id, capability):
        return str(resource_id) in self.ids(kind, capability)

    def require(self, kind, resource_id, capability):
        if not self.allows(kind, resource_id, capability):
            raise PermissionError("permission_denied")


class ProjectFactsWebOwner:
    """Web presentation owner over the Confluence current-state cache."""

    def __init__(
        self,
        *,
        repository: ConfluenceProjectRepository | None = None,
        client_factory=None,
        data_root=None,
        sync_coordinator_factory=ConfluenceProjectSyncCoordinator,
    ):
        database_path = (
            data_root / "smarttest-web.db" if data_root else default_web_database_path()
        )
        self._repository = repository or ConfluenceProjectRepository(WebDatabase(database_path))
        self._client_factory = client_factory or self._make_client
        self._sync_coordinator_factory = sync_coordinator_factory
        self._refresh_lock = Lock()

    @staticmethod
    def _make_client(username, password):
        base_url = os.getenv("SMARTTEST_CONFLUENCE_BASE_URL", "https://confluence.amlogic.com")
        return ConfluenceGateway(ConfluenceGatewayConfig(base_url), username, password)

    def refresh(self, access, password):
        with self._refresh_lock:
            started = perf_counter()
            service = self._service(access, password)
            result = service.refresh_projects(
                ProjectSyncScope(product_space_keys=PAGE_CATALOG_PRODUCT_SPACES),
            )
            smart_log("Confluence filter preparation timing", platform="web", domain="framework", source="project_facts_owner", emit_runtime_event=False,
                      extra={"stage": "filter.catalog_refresh", "duration_ms": round((perf_counter() - started) * 1000, 3),
                             "product_space_count": len(PAGE_CATALOG_PRODUCT_SPACES), "project_count": len(result.get("projects") or ()),
                             "failure_count": len(result.get("failed") or ())})
            if result['failed']:
                raise RuntimeError('remote_unavailable')
        return None

    def sync_details(
        self, access, password, *, filters=None, search="", cancelled=None, progress=None,
    ):
        selected = self.query(access, filters=filters, search=search)
        project_ids = tuple(row["identity"] for row in selected["projects"])
        progress = progress or (lambda *_: None)
        progress(0, len(project_ids))
        service = self._service(access, password)
        coordinator = self._sync_coordinator_factory(service)
        coordinator.sync(
            project_ids,
            ProjectDetails(roles=True, facts=True, evidence=True),
            cancelled=cancelled or (lambda: False),
            progress=progress,
        )

    def refresh_and_sync_details(
        self, access, password, *, filters=None, search="", cancelled=None, progress=None,
    ):
        self.refresh(access, password)
        self.sync_details(
            access, password, filters=filters, search=search,
            cancelled=cancelled, progress=progress,
        )

    def query(self, access, *, filters=None, search="", page=0, page_size=10000):
        started = perf_counter()
        query_access = _QueryAccessSnapshot(access)
        ready_product_spaces = query_access.ids("catalog", "ready")
        cached = self._repository.list(
            ProjectQuery(), 0, 100000,
            visible_ids=query_access.ids("project", "catalog"),
        )
        if cached.total == 0:
            state = "ready" if set(PAGE_CATALOG_PRODUCT_SPACES) <= ready_product_spaces else "no_snapshot"
            self._log_query_timing(started, state, cached.total, query_access, ready_product_spaces, 0)
            return self._state(state, ready_product_spaces)
        projects = self._repository.load_many(
            cached.projects, ProjectDetails(roles=True, facts=True),
        )
        snapshot = {"projects": [_project_snapshot_row(project) for project in projects if project]}
        result = query_project_facts(snapshot, filters=filters, search=search)
        start = int(page) * int(page_size)
        visible = result["projects"]
        self._log_query_timing(started, "ready", cached.total, query_access, ready_product_spaces, len(visible))
        return {
            "state": "ready",
            "accessibleProjectCount": cached.total,
            "productSpaces": _product_space_rows(),
            "facets": _facet_rows(result["facets"], ready_product_spaces),
            "projects": visible[start:start + int(page_size)],
            "pagination": {
                "page": int(page),
                "pageSize": int(page_size),
                "total": len(visible),
            },
            "ownerHierarchy": result["ownerHierarchy"],
            "discrepancies": [],
            "counts": {"stale": 0, "failed": 0, "inactive": 0},
        }

    @staticmethod
    def _log_query_timing(started, state, cached_count, access, ready_spaces, visible_count):
        smart_log("Confluence filter query timing", platform="web", domain="framework", source="project_facts_owner", emit_runtime_event=False,
                  extra={"stage": "filter.query_aggregate", "duration_ms": round((perf_counter() - started) * 1000, 3),
                         "result_state": state, "cached_count": cached_count,
                         "visible_grant_count": len(access.ids("project", "catalog")),
                         "ready_space_count": len(ready_spaces), "visible_count": visible_count})

    def facts_version(self) -> str:
        return self._repository.facts_version()

    def invalidate_project(self, project_id: str, access) -> None:
        access.require("project", project_id, "catalog")
        access.revoke("project", project_id)

    def _service(self, access, password):
        client = self._client_factory(access.account, password)
        gateway = _ProjectFactsGateway(client, self._repository)
        return ConfluenceProjectCacheService(
            gateway, ConfluenceProjectMapper(), self._repository, access=access,
        )

    def audit_dependencies(self, access, password):
        client = self._client_factory(access.account, password)
        gateway = _ProjectFactsGateway(client, self._repository)
        return (
            ConfluenceProjectCacheService(
                gateway, ConfluenceProjectMapper(), self._repository, access=access,
            ),
            self._repository,
            client,
        )

    @staticmethod
    def _state(state, ready_product_spaces=()):
        return {
            "state": state, "accessibleProjectCount": 0,
            "productSpaces": _product_space_rows(),
            "facets": [
                {"key": key, "label": label, "labels": [label],
                 "options": _product_space_rows(ready_product_spaces) if key == PRODUCT_SPACE_FACET else []}
                for key, label in PROJECT_SPACE_FACET_DEFINITIONS
            ],
            "projects": [], "ownerHierarchy": [], "discrepancies": [],
            "counts": {"stale": 0, "failed": 0, "inactive": 0},
        }


class _ProjectFactsGateway:
    def __init__(self, client, repository):
        self._client = client
        self._repository = repository
        self._details = {}

    def refresh_project_catalogs(self, scope):
        buffer = _CatalogSyncBuffer()
        snapshot = refresh_project_catalogs(self._client, buffer, manager=WEB_TASKS)
        rows = snapshot.get("projects") or ()
        if scope.product_space_keys:
            allowed = set(scope.product_space_keys)
            rows = [row for row in rows if row.get("space_key") in allowed]
        return {"projects": rows, "failed_product_spaces": snapshot.get("failed_product_spaces") or (),
                "complete_spaces": snapshot.get("complete_spaces") or ()}

    def query_project_catalog(self, query, page):
        payload = self.refresh_project_catalogs(ProjectSyncScope())
        rows = payload["projects"]
        return {"projects": rows, "page": page, "page_size": len(rows), "total": len(rows)}

    def get_project_catalog(self, project_id):
        self._details.pop(project_id, None)
        project = self._repository.get(project_id, ProjectDetails(facts=True))
        if project is None:
            raise KeyError(project_id)
        return _catalog_row(project)

    def load_project_sections(self, project_id, sections):
        if project_id not in self._details:
            project = self._repository.get(project_id, ProjectDetails(facts=True))
            if project is None:
                raise KeyError(project_id)
            self._details[project_id] = extract_project_detail(self._client, _catalog_row(project))
        detail = self._details[project_id]
        result = {}
        if "roles" in sections:
            result["roles"] = detail.get("roles") or {}
        if "facts" in sections:
            result["facts"] = detail.get("fields") or {}
        if "evidence" in sections:
            result["evidence"] = [
                {"source": "catalog", **detail["catalog_source"]},
                *detail["evidence"],
            ]
            result["access_grants"] = [
                ("page", item["page_id"], "metadata", f"{project_id}:evidence")
                for item in detail["evidence"]
            ]
        for name in ("milestones", "hardware", "software"):
            if name in sections:
                result[name] = {}
        return result


class _CatalogSyncBuffer:
    def __init__(self):
        self._snapshot = None

    def load(self):
        return self._snapshot

    def save(self, snapshot):
        self._snapshot = snapshot


def _catalog_row(project):
    fields = dict(project.facts.value.values) if project.facts.value is not None else {}
    return {
        "identity": project.identity.confluence_id,
        "page_id": project.catalog_page.page_id,
        "project_id": project.identity.project_id,
        "name": project.name,
        "space_key": project.product_space.key,
        "space_name": project.product_space.name,
        "space_url": project.product_space.url,
        "page_url": project.catalog_page.url,
        "catalog_source": {
            "page_id": project.catalog_page.page_id,
            "title": project.catalog_page.title,
            "url": project.catalog_page.url,
            "version": project.revision.value,
        },
        "fields": {**fields,
            "project status": project.status.name if project.status else "",
            "current stage": project.stage.name if project.stage else "",
            "support mode": project.support_mode.name if project.support_mode else "",
            "oem/operator": project.customer_summary,
        },
    }


def _project_snapshot_row(project):
    fields = dict(project.facts.value.values) if project.facts.value is not None else {}
    fields.update({
        "project id": project.identity.project_id,
        "project status": project.status.name if project.status else "",
        "current stage": project.stage.name if project.stage else "",
        "support mode": project.support_mode.name if project.support_mode else "",
    })
    roles = {
        role.role.name: [
            {"identity": person.identity, "account": person.account, "name": person.display_name}
            for person in role.people
        ]
        for role in (project.roles.value or ())
    }
    return {
        "identity": project.identity.confluence_id,
        "project_id": project.identity.project_id,
        "name": project.name,
        "space_key": project.product_space.key,
        "status": project.status.name if project.status else "",
        "stage": project.stage.name if project.stage else "",
        "support_mode": project.support_mode.name if project.support_mode else "",
        "customer_summary": project.customer_summary,
        "page_id": project.catalog_page.page_id,
        "page_url": project.catalog_page.url,
        "active": True,
        "fields": fields,
        "roles": roles,
    }


def _product_space_rows(allowed=None):
    allowed = None if allowed is None else set(allowed)
    return [
        {"value": line.key, "label": line.display_name}
        for line in PRODUCT_LINES
        if allowed is None or line.key in allowed
    ]


def _facet_rows(values, ready_product_spaces=()):
    labels = dict(PROJECT_SPACE_FACET_DEFINITIONS)
    fixed = tuple(labels)
    keys = (*fixed, *(key for key in sorted(values, key=str.casefold) if key not in labels))
    return [{
        "key": key,
        "label": labels.get(key, key.title()),
        "labels": [labels.get(key, key.title())],
        "options": (_product_space_rows(ready_product_spaces)
                    if key == PRODUCT_SPACE_FACET else values.get(key, [])),
    } for key in keys]
