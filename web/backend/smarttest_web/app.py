from __future__ import annotations

from dataclasses import asdict, is_dataclass
from functools import lru_cache
from contextlib import asynccontextmanager
from datetime import date, datetime
import hashlib
import os
from pathlib import Path
from threading import Lock
from time import perf_counter
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from core.authentication import LdapAuthenticator
from core.confluence.audit import manual_audit_period
from core.logging import configure_external_logging, configure_platform, smart_log
from core.jira.domain import IssueDetails
from core.jira.gateway import JiraGateway
from core.jira.mapper import JiraIssueMapper

from .config import DatabaseSettings
from .database import ReadonlyDatabase, WebDatabase
from .jira.cache_service import JiraIssueCacheService
from .jira.issue_repository import JiraIssueRepository
from .filters import WifiFilters
from .service import WifiDatabaseQueries
from .report_workspace import ClientAuditReportOwner, ReportNotFoundError
from .project_facts_api import ProjectFactsWebOwner
from .session import PersistentSessionStore, default_web_database_path
from .background_refresh import BackgroundFactsRefresh
from .query_snapshot_repository import ConfluenceQuerySnapshotRepository
from .release_query import ProjectReleaseQueryService
from .release_snapshot_repository import ReleaseQuerySnapshotRepository
from .test_suite_repository import NameConflictError, RevisionConflictError, TestSuiteRepository
from .credentials import CredentialMissingError, CredentialStoreError
from .resource_access import remote_credentials_rejected
from .audit.registry import (
    AuditConflictError,
    AuditNotFoundError,
    ManualAuditRegistry,
)
from .downloads import DownloadArtifactService, DownloadNotFoundError

SESSION_COOKIE = "smarttest_session"


@lru_cache(maxsize=1)
def default_query_owner():
    return WifiDatabaseQueries(ReadonlyDatabase(DatabaseSettings.from_environment()))


def default_authenticator():
    return LdapAuthenticator(platform="web")


def default_jira_cache_owner(username: str, password: str):
    base_url = os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
    gateway = JiraGateway(base_url, username, password)
    return JiraIssueCacheService(
        gateway,
        JiraIssueMapper(base_url),
        JiraIssueRepository(WebDatabase(default_web_database_path())),
    )


def default_jira_audit_owner(username: str, password: str):
    from .audit.jira_adapter import WebJiraAuditOwner
    return WebJiraAuditOwner.from_credentials(username, password)


def default_confluence_audit_owner(username: str, password: str):
    from .audit.confluence_adapter import WebConfluenceAuditOwner
    return WebConfluenceAuditOwner.from_credentials(username, password)


def create_app(query_owner=default_query_owner, report_owner=ClientAuditReportOwner.from_environment,
               project_facts_owner=ProjectFactsWebOwner, authenticator=default_authenticator,
               session_store=PersistentSessionStore, facts_refresh=BackgroundFactsRefresh,
               jira_cache_owner=default_jira_cache_owner,
               release_query_owner=ProjectReleaseQueryService,
               audit_registry=ManualAuditRegistry,
               download_service=DownloadArtifactService,
               jira_audit_owner=default_jira_audit_owner,
               confluence_audit_owner=default_confluence_audit_owner) -> FastAPI:
    auth = authenticator()
    sessions = session_store()
    cache_database = WebDatabase(sessions.path)
    facts = project_facts_owner()
    refresh = facts_refresh()
    snapshots = ConfluenceQuerySnapshotRepository(cache_database)
    release_snapshots = ReleaseQuerySnapshotRepository(cache_database)
    releases = release_query_owner(cache_database)
    test_suites = TestSuiteRepository(cache_database)
    audits = audit_registry()
    downloads = download_service()

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            audits.close()
            downloads.close()

    app = FastAPI(title="SmartTest Wi-Fi Database", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)

    def set_session_cookie(request: Request, response: Response, token: str) -> None:
        secure = request.url.scheme.lower() == "https"
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            secure=secure,
            samesite="lax",
            max_age=sessions.ttl_seconds,
            path="/",
        )
        smart_log(
            f"Web session cookie cookie_action=set secure={str(secure).lower()} "
            f"request_id={request.state.request_id}",
            platform="web", domain="auth", source="session_cookie",
            request_id=request.state.request_id,
            extra={"cookie_action": "set", "secure": secure,
                   "request_scheme": request.url.scheme.lower(),
                   "request_id": request.state.request_id},
            emit_runtime_event=False,
        )

    def clear_session_cookie(request: Request, response: Response) -> None:
        secure = request.url.scheme.lower() == "https"
        response.delete_cookie(
            SESSION_COOKIE,
            path="/",
            httponly=True,
            secure=secure,
            samesite="lax",
        )
        smart_log(
            f"Web session cookie cookie_action=clear secure={str(secure).lower()} "
            f"request_id={request.state.request_id}",
            platform="web", domain="auth", source="session_cookie",
            request_id=request.state.request_id,
            extra={"cookie_action": "clear", "secure": secure,
                   "request_scheme": request.url.scheme.lower(),
                   "request_id": request.state.request_id},
            emit_runtime_event=False,
        )

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        started = perf_counter()
        request_id = request.headers.get("x-request-id", "").strip() or str(uuid4())
        request.state.request_id = request_id
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            if getattr(request.state, "renew_session_cookie", False):
                set_session_cookie(request, response, request.cookies[SESSION_COOKIE])
            response.headers["x-request-id"] = request_id
            return response
        finally:
            smart_log(
                f"{request.method} {request.url.path} {status} request_id={request_id}",
                platform="web",
                domain="web",
                level="error" if status >= 500 else "warning" if status >= 400 else "info",
                source="request",
                request_id=request_id,
                extra={"method": request.method, "path": request.url.path, "status": status,
                       "request_id": request_id,
                       "duration_ms": round((perf_counter() - started) * 1000, 3)},
                emit_runtime_event=False,
            )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    def current_session(request: Request):
        cookie_present = bool(request.cookies.get(SESSION_COOKIE, ""))
        value = sessions.get(request.cookies.get(SESSION_COOKIE, ""))
        smart_log(
            f"Web session resolve cookie_present={str(cookie_present).lower()} "
            f"session_found={str(value is not None).lower()} "
            f"request_id={request.state.request_id}",
            platform="web", domain="auth", source="session_resolve",
            request_id=request.state.request_id,
            extra={"cookie_present": cookie_present, "session_found": value is not None,
                   "request_id": request.state.request_id},
            emit_runtime_event=False,
        )
        if value is not None and value.cookie_renewal_required:
            request.state.renew_session_cookie = True
        return value

    def public_session(value):
        if value is None:
            return {"authenticated": False}
        return {"authenticated": True, "username": value.username,
                "displayName": value.display_name,
                "avatarUrl": "/api/auth/avatar" if value.avatar_bytes else ""}

    def establish_session(request: Request, response: Response, *, username: str,
                          password: str | None, display_name: str = "",
                          avatar_bytes: bytes = b""):
        try:
            if password is None:
                session_id = sessions.create_from_saved(username, display_name, avatar_bytes)
            else:
                session_id = sessions.create(username, password, display_name, avatar_bytes)
        except CredentialStoreError as error:
            smart_log("Persistent Web credential storage failed", platform="web", domain="auth",
                      source="session", level="error",
                      extra={"exception_type": type(error).__name__})
            raise HTTPException(
                status_code=503,
                detail={"state": "credential_store_unavailable"},
            ) from error
        old_token = request.cookies.get(SESSION_COOKIE, "")
        if old_token:
            sessions.delete(old_token)
            audits.cancel_session(_session_owner(old_token))
        set_session_cookie(request, response, session_id)
        return public_session(sessions.get(session_id))

    @app.post("/api/auth/login")
    def login(request: Request, response: Response, payload: dict = Body(...)):
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        try:
            sessions.saved_credentials(username)
        except CredentialMissingError:
            pass
        except CredentialStoreError as error:
            raise HTTPException(
                status_code=503,
                detail={"state": "credential_store_unavailable"},
            ) from error
        else:
            return establish_session(
                request,
                response,
                username=username,
                password=None,
                display_name=username,
            )
        result = auth.authenticate(username, password)
        if not result.get("success"):
            code = result.get("code") if result.get("code") in {"invalid_credentials", "ldap_unavailable"} else "ldap_unavailable"
            raise HTTPException(status_code=401 if code == "invalid_credentials" else 503,
                                detail={"state": code})
        return establish_session(
            request,
            response,
            username=result["username"],
            password=password,
            display_name=result.get("display_name", ""),
            avatar_bytes=result.get("avatar_bytes", b""),
        )

    @app.post("/api/auth/client-session")
    def client_session(request: Request, response: Response, payload: dict = Body(...)):
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        if not username or not password:
            raise HTTPException(status_code=422, detail={"state": "invalid_input"})
        return establish_session(
            request,
            response,
            username=username,
            password=password,
            display_name=username,
        )

    @app.get("/api/auth/session")
    def session(request: Request):
        return public_session(current_session(request))

    @app.get("/api/auth/avatar")
    def avatar(request: Request):
        value = current_session(request)
        if value is None or not value.avatar_bytes:
            raise HTTPException(status_code=404, detail="Avatar not found.")
        return Response(value.avatar_bytes, media_type="image/jpeg")

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        token = request.cookies.get(SESSION_COOKIE, "")
        downloads.clear_session(_session_owner(token))
        sessions.delete(token)
        audits.cancel_session(_session_owner(token))
        clear_session_cookie(request, response)
        return {"authenticated": False}

    @app.post("/api/auth/logout-all")
    def logout_all(request: Request, response: Response):
        value = current_session(request)
        if value is None:
            raise HTTPException(status_code=401, detail={"state": "unauthenticated"})
        downloads.clear_session(audit_session(request))
        sessions.delete_all(value.username)
        request.state.renew_session_cookie = False
        clear_session_cookie(request, response)
        return {"authenticated": False}

    def authenticated_session(request: Request):
        value = current_session(request)
        if value is None:
            state = sessions.rejection_state(request.cookies.get(SESSION_COOKIE, ""))
            raise HTTPException(status_code=401, detail={"state": state or "unauthenticated"})
        return value

    def suite_payload(record, *, detail: bool = False):
        payload = {
            "id": record.id, "ownerUsername": record.owner_username,
            "ownerDisplayName": record.owner_display_name, "name": record.name,
            "description": record.description, "visibility": record.visibility,
            "caseCount": len(record.ordered_nodeids), "revision": record.revision,
            "createdAt": record.created_at, "updatedAt": record.updated_at,
        }
        if detail:
            payload["orderedNodeids"] = list(record.ordered_nodeids)
        return payload

    def suite_input(payload: dict, *, revision_required: bool = False):
        name = payload.get("name")
        description = payload.get("description", "")
        visibility = payload.get("visibility", "private")
        nodeids = payload.get("orderedNodeids")
        revision = payload.get("revision")
        if (not isinstance(name, str) or not name.strip() or
                not isinstance(description, str) or visibility not in {"private", "shared"} or
                not isinstance(nodeids, list) or not nodeids or
                any(not isinstance(item, str) or not item.strip() for item in nodeids) or
                revision_required and (not isinstance(revision, int) or isinstance(revision, bool))):
            raise HTTPException(status_code=422, detail={"state": "invalid_input"})
        return name, description, visibility, nodeids, revision

    @app.get("/api/test-suites")
    def list_test_suites(scope: str, value=Depends(authenticated_session)):
        if scope == "mine":
            rows = test_suites.list_mine(value.username)
        elif scope == "shared":
            rows = test_suites.list_shared(value.username)
        else:
            raise HTTPException(status_code=422, detail={"state": "invalid_input"})
        return [suite_payload(row) for row in rows]

    @app.get("/api/test-suites/{suite_id}")
    def get_test_suite(suite_id: str, value=Depends(authenticated_session)):
        record = test_suites.get_visible(suite_id, value.username)
        if record is None:
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        return suite_payload(record, detail=True)

    @app.post("/api/test-suites")
    def create_test_suite(payload: dict = Body(...), value=Depends(authenticated_session)):
        name, description, visibility, nodeids, _ = suite_input(payload)
        try:
            record = test_suites.create(owner_username=value.username,
                owner_display_name=value.display_name or value.username, name=name,
                description=description, visibility=visibility, ordered_nodeids=nodeids)
        except NameConflictError as error:
            raise HTTPException(status_code=409, detail={"state": "name_conflict"}) from error
        return suite_payload(record, detail=True)

    @app.put("/api/test-suites/{suite_id}")
    def update_test_suite(suite_id: str, payload: dict = Body(...), value=Depends(authenticated_session)):
        name, description, visibility, nodeids, revision = suite_input(payload, revision_required=True)
        try:
            record = test_suites.update(suite_id, owner_username=value.username, revision=revision,
                name=name, description=description, visibility=visibility, ordered_nodeids=nodeids)
        except NameConflictError as error:
            raise HTTPException(status_code=409, detail={"state": "name_conflict"}) from error
        except RevisionConflictError as error:
            raise HTTPException(status_code=409, detail={"state": "revision_conflict"}) from error
        if record is None:
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        return suite_payload(record, detail=True)

    @app.delete("/api/test-suites/{suite_id}")
    def delete_test_suite(suite_id: str, value=Depends(authenticated_session)):
        if not test_suites.delete(suite_id, owner_username=value.username):
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        return {"deleted": True}

    @app.post("/api/test-suites/{suite_id}/copy")
    def copy_test_suite(suite_id: str, payload: dict = Body(...), value=Depends(authenticated_session)):
        name = payload.get("name")
        visibility = payload.get("visibility", "private")
        if not isinstance(name, str) or not name.strip() or visibility not in {"private", "shared"}:
            raise HTTPException(status_code=422, detail={"state": "invalid_input"})
        try:
            record = test_suites.copy(suite_id, reader_username=value.username,
                owner_display_name=value.display_name or value.username, name=name, visibility=visibility)
        except NameConflictError as error:
            raise HTTPException(status_code=409, detail={"state": "name_conflict"}) from error
        if record is None:
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        return suite_payload(record, detail=True)

    def audit_session(request: Request) -> str:
        return _session_owner(request.cookies.get(SESSION_COOKIE, ""))

    def access_context(request):
        base = os.getenv("SMARTTEST_CONFLUENCE_BASE_URL", "https://confluence.amlogic.com")
        return sessions.resource_access(request.cookies.get(SESSION_COOKIE, ""),
                                        f"confluence:{base.rstrip('/').lower()}", cache_database)

    def release_access(request):
        access = access_context(request)
        access.require_active()
        return access

    def release_filters(request, names):
        return {
            name: tuple(value for value in request.query_params.getlist(name) if str(value).strip())
            for name in names if request.query_params.getlist(name)
        }

    def release_snapshot_payload(snapshot):
        return {
            "scope": snapshot.scope,
            "updatedAt": snapshot.updated_at,
            "confluenceFactsVersion": snapshot.confluence_facts_version,
            "jiraCacheVersion": snapshot.jira_cache_version,
        }

    def record_release_snapshot(value, access, scope, filters, search, result, project_ids=()):
        release_rows = tuple(row for row in result.get("releases", ()) if row.get("projectId"))
        selected = result.get("selectedRelease") or {}
        if release_rows:
            selected_ids = tuple(row["projectId"] for row in release_rows)
            release_names = tuple(
                "" if row.get("releaseName") == "版本未填写" else str(row.get("releaseName") or "")
                for row in release_rows
            )
        elif selected.get("projectId"):
            selected_ids = (selected["projectId"],)
            release_names = (
                "" if selected.get("releaseName") == "版本未填写" else str(selected.get("releaseName") or ""),
            )
        else:
            selected_ids = tuple(project_ids) or tuple(dict.fromkeys(
                row.get("projectId") for row in result.get("issues", ()) if row.get("projectId")
            ))
            release_names = ()
        freshness = result.get("sourceFreshness") or {}
        release_snapshots.record(
            access.session_hash, scope, filters, search, selected_ids, release_names,
            freshness.get("confluence", ""), freshness.get("jira", ""), expires_at=value.expires_at,
        )
        return release_snapshots.get(access.session_hash, scope)

    @app.get("/api/dashboard/releases")
    def dashboard_releases(request: Request, value=Depends(authenticated_session)):
        access = release_access(request)
        filters = release_filters(request, ("productLine", "stage", "project", "release", "owner", "qa", "status"))
        search = request.query_params.get("search", "")
        project_ids = ()
        if request.query_params.get("snapshot") == "1":
            selection = release_snapshots.get(access.session_hash, "release-dashboard")
            if selection is not None:
                filters, search, project_ids = selection.filters, selection.search, selection.project_ids
        elif request.query_params.get("reset") == "1":
            filters, search = {}, ""
        result = releases.dashboard(
            visible_ids=access.ids("project", "catalog"), project_ids=project_ids, filters=filters,
        )
        selection = record_release_snapshot(
            value, access, "release-dashboard", filters, search, result, project_ids,
        )
        return {**result, "querySnapshot": release_snapshot_payload(selection), "syncState": "idle"}

    def refresh_jira_release_scope(value, project_ids):
        if not project_ids:
            return
        quoted = ",".join(f'"{str(project_id).replace(chr(34), chr(92) + chr(34))}"' for project_id in project_ids)
        query = f'"Project ID" in ({quoted})'
        owner = resolve_jira_cache(value)
        page = 0
        while True:
            refreshed = owner.refresh_release_issues(query, page=page)
            page_size = max(1, int(refreshed.get("page_size") or 100))
            if (page + 1) * page_size >= int(refreshed.get("total") or 0):
                break
            page += 1

    @app.post("/api/dashboard/releases/sync")
    def sync_dashboard_releases(request: Request, value=Depends(authenticated_session)):
        access = release_access(request)
        selection = release_snapshots.get(access.session_hash, "release-dashboard")
        if selection is None:
            raise HTTPException(status_code=409, detail={"state": "no_snapshot"})
        try:
            facts.sync_details(
                access, value.password, filters={"project id": selection.project_ids}, search="",
            )
            refresh_jira_release_scope(value, selection.project_ids)
            sync_state = "ready"
        except Exception as error:
            sync_state = downstream_refresh_error(value, error)
        result = releases.dashboard(
            visible_ids=access.ids("project", "catalog"), project_ids=selection.project_ids,
            filters=selection.filters,
        )
        updated = record_release_snapshot(
            value, access, "release-dashboard", selection.filters, selection.search,
            result, selection.project_ids,
        )
        return {**result, "querySnapshot": release_snapshot_payload(updated), "syncState": sync_state}

    @app.get("/api/dashboard/releases/{project_id}")
    def dashboard_release(project_id: str, request: Request, value=Depends(authenticated_session)):
        del value
        access = release_access(request)
        selection = release_snapshots.get(access.session_hash, "release-dashboard")
        if selection is None or project_id not in selection.project_ids:
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        result = releases.dashboard(
            visible_ids=access.ids("project", "catalog"), project_ids=(project_id,), filters={},
        )
        if not result.get("releases"):
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        return result["releases"][0]

    @app.get("/api/jira/release-issues")
    def jira_release_issues(request: Request, value=Depends(authenticated_session)):
        access = release_access(request)
        try:
            page = int(request.query_params.get("page", "0"))
            page_size = int(request.query_params.get("pageSize", "50"))
            if page < 0 or not 1 <= page_size <= 200:
                raise ValueError
        except ValueError as error:
            raise HTTPException(status_code=422, detail={"state": "invalid_pagination"}) from error
        filters = release_filters(request, (
            "productLine", "project", "release", "fixVersion", "softwareRelease", "status", "resolution", "priority", "severity",
            "component", "assignee", "qaAssignee", "association",
        ))
        search = request.query_params.get("search", "")
        project_ids = ()
        snapshot_mode = request.query_params.get("snapshot", "")
        selection = None
        if snapshot_mode == "dashboard":
            selection = release_snapshots.get(access.session_hash, "release-dashboard")
            requested_project = request.query_params.get("projectId", "")
            if selection is None:
                raise HTTPException(status_code=409, detail={"state": "no_snapshot"})
            if not requested_project and len(selection.project_ids) == 1:
                requested_project = selection.project_ids[0]
            if requested_project not in selection.project_ids:
                raise HTTPException(status_code=404, detail={"state": "not_found"})
            release_index = selection.project_ids.index(requested_project)
            if release_index >= len(selection.release_names):
                raise HTTPException(status_code=409, detail={"state": "stale_snapshot"})
            project_ids = (requested_project,)
            filters.update({
                "_scopeRelease": (selection.release_names[release_index],),
                "_openOnly": True,
                "_drilldownScope": True,
            })
        elif snapshot_mode == "1":
            selection = release_snapshots.get(access.session_hash, "jira-release-workbench")
            if selection is not None:
                project_ids = selection.project_ids
                filters, search = selection.filters, selection.search
        elif request.query_params.get("reset") == "1":
            selection = release_snapshots.get(access.session_hash, "jira-release-workbench")
            if selection is not None and selection.filters.get("_drilldownScope"):
                project_ids = selection.project_ids
                filters = {
                    key: value for key, value in selection.filters.items() if key.startswith("_")
                }
            else:
                filters, search = {}, ""
        else:
            selection = release_snapshots.get(access.session_hash, "jira-release-workbench")
            if selection is not None and selection.filters.get("_drilldownScope"):
                project_ids = selection.project_ids
                constraints = {
                    key: value for key, value in selection.filters.items() if key.startswith("_")
                }
                filters.update(constraints)
        result = releases.issues(
            visible_ids=access.ids("project", "catalog"), project_ids=project_ids,
            filters=filters, page=page, page_size=page_size,
        )
        selection = record_release_snapshot(
            value, access, "jira-release-workbench", filters, search, result, project_ids,
        )
        return {**result, "querySnapshot": release_snapshot_payload(selection), "syncState": "idle"}

    @app.post("/api/jira/release-issues/sync")
    def sync_jira_release_issues(request: Request, value=Depends(authenticated_session)):
        access = release_access(request)
        selection = release_snapshots.get(access.session_hash, "jira-release-workbench")
        if selection is None:
            raise HTTPException(status_code=409, detail={"state": "no_snapshot"})
        try:
            refresh_jira_release_scope(value, selection.project_ids)
            sync_state = "ready"
        except Exception as error:
            sync_state = downstream_refresh_error(value, error)
        result = releases.issues(
            visible_ids=access.ids("project", "catalog"), project_ids=selection.project_ids,
            filters=selection.filters, page=0, page_size=50,
        )
        updated = record_release_snapshot(
            value, access, "jira-release-workbench", selection.filters, selection.search,
            result, selection.project_ids,
        )
        return {**result, "querySnapshot": release_snapshot_payload(updated), "syncState": sync_state}

    @app.get("/api/jira/release-issues/{issue_key}")
    def jira_release_issue(issue_key: str, request: Request, value=Depends(authenticated_session)):
        access = release_access(request)
        selection = release_snapshots.get(access.session_hash, "jira-release-workbench")
        if selection is None:
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        release_detail = releases.issue_detail(
            issue_key, visible_ids=access.ids("project", "catalog"), project_ids=selection.project_ids,
            filters=selection.filters,
        )
        if release_detail is None:
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        names = tuple(dict.fromkeys(request.query_params.getlist("details")))
        allowed = {"description", "comments", "attachments", "links", "custom_fields"}
        if any(name not in allowed for name in names):
            raise HTTPException(status_code=422, detail={"state": "invalid_details"})
        details = IssueDetails(**{name: True for name in names})
        try:
            issue = resolve_jira_cache(value).get_issue(issue_key, details)
        except Exception as error:
            raise_downstream_error(value, error)
        if issue is None:
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        current = _issue_payload(issue, names)
        return {**release_detail, "details": current["details"]}

    @app.exception_handler(PermissionError)
    async def permission_error(_request, error):
        from fastapi.responses import JSONResponse
        state = "reauthentication_required" if str(error) == "reauthentication_required" else "permission_denied"
        return JSONResponse(status_code=401 if state == "reauthentication_required" else 403,
                            content={"detail": {"state": state}})

    def validate_preference_payload(scope: str, payload: dict):
        import json
        import re
        if not re.fullmatch(r"[A-Za-z0-9._/-]{1,160}", scope):
            raise HTTPException(status_code=422, detail={"state": "invalid_scope"})
        items = payload.get("items")
        if not isinstance(items, dict) or any(not isinstance(key, str) or not key for key in items):
            raise HTTPException(status_code=422, detail={"state": "invalid_preferences"})
        sensitive = re.compile(r"password|passwd|secret|token|cookie|credential|authorization", re.I)
        def contains_sensitive_key(value):
            if isinstance(value, dict):
                return any(sensitive.search(str(key)) or contains_sensitive_key(child) for key, child in value.items())
            if isinstance(value, list):
                return any(contains_sensitive_key(child) for child in value)
            return False
        if contains_sensitive_key(items):
            raise HTTPException(status_code=422, detail={"state": "sensitive_preference"})
        try:
            encoded = json.dumps(items, ensure_ascii=False)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail={"state": "invalid_preferences"}) from error
        if len(encoded.encode("utf-8")) > 64 * 1024:
            raise HTTPException(status_code=413, detail={"state": "preferences_too_large"})
        version = payload.get("schemaVersion", 1)
        if not isinstance(version, int) or not 1 <= version <= 1000:
            raise HTTPException(status_code=422, detail={"state": "invalid_schema_version"})
        return items, version

    @app.get("/api/preferences/{scope:path}")
    def get_preferences(scope: str, value=Depends(authenticated_session)):
        return sessions.get_preferences(value.username, scope)

    @app.put("/api/preferences/{scope:path}")
    def put_preferences(scope: str, payload: dict = Body(...), value=Depends(authenticated_session)):
        items, version = validate_preference_payload(scope, payload)
        return sessions.upsert_preferences(value.username, scope, items, version)

    @app.delete("/api/preferences/{scope:path}")
    def delete_preferences(scope: str, value=Depends(authenticated_session)):
        return {"deleted": sessions.delete_preferences(value.username, scope)}

    def filters_from_request(request: Request) -> WifiFilters:
        try:
            return WifiFilters.from_query(request.query_params)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail="Invalid Wi-Fi Database query parameters.") from error

    def resolve_query_owner():
        try:
            return query_owner()
        except Exception as error:
            raise HTTPException(status_code=503, detail="Wi-Fi Database is unavailable.") from error

    @app.get("/api/filters")
    def filters(filters: WifiFilters = Depends(filters_from_request), owner=Depends(resolve_query_owner)):
        try:
            return owner.get_filters(filters)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Wi-Fi Database is unavailable.") from error

    @app.get("/api/performance")
    def performance(filters: WifiFilters = Depends(filters_from_request), owner=Depends(resolve_query_owner)):
        try:
            return owner.get_performance(filters)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Wi-Fi Database is unavailable.") from error

    def resolve_report_owner():
        try:
            return report_owner()
        except Exception as error:
            raise HTTPException(status_code=503, detail={"state": "config_missing"}) from error

    def resolve_project_facts_owner():
        return facts

    def resolve_jira_cache(value):
        try:
            return jira_cache_owner(value.username, value.password)
        except Exception as error:
            raise HTTPException(status_code=503, detail={"state": "cache_unavailable"}) from error

    def raise_downstream_error(value, error):
        if remote_credentials_rejected(error):
            sessions.invalidate_credentials(value.username)
            raise HTTPException(
                status_code=401, detail={"state": "invalid_credentials"},
            ) from error
        raise error

    @app.get("/api/jira/issues")
    def jira_issues(
        query: str = "", page: int = 0, pageSize: int = 100,
        value=Depends(authenticated_session),
    ):
        owner = resolve_jira_cache(value)
        try:
            result = owner.list_issues(query, page, pageSize)
        except Exception as error:
            raise_downstream_error(value, error)
        return {
            "issues": [_issue_payload(issue, ()) for issue in result.issues],
            "pagination": {"page": result.page, "pageSize": result.page_size, "total": result.total},
        }

    @app.get("/api/jira/issues/{issue_key}")
    def jira_issue(issue_key: str, request: Request, value=Depends(authenticated_session)):
        names = tuple(dict.fromkeys(request.query_params.getlist("details")))
        allowed = {"description", "comments", "attachments", "links", "custom_fields"}
        if any(name not in allowed for name in names):
            raise HTTPException(status_code=422, detail={"state": "invalid_details"})
        details = IssueDetails(**{name: True for name in names})
        try:
            issue = resolve_jira_cache(value).get_issue(issue_key, details)
        except Exception as error:
            raise_downstream_error(value, error)
        if issue is None:
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        return _issue_payload(issue, names)

    @app.delete("/api/jira/issues/{issue_key}")
    def invalidate_jira_issue(issue_key: str, value=Depends(authenticated_session)):
        resolve_jira_cache(value).invalidate_issue(issue_key)
        return {"invalidated": issue_key}

    @app.delete("/api/confluence/projects/{project_id}")
    def invalidate_confluence_project(project_id: str, request: Request, value=Depends(authenticated_session)):
        facts.invalidate_project(project_id, access_context(request))
        return {"invalidated": project_id}

    def record_query_snapshot(access, value, filters, search, result):
        if result.get("state") in {"ready", "partial_success"}:
            snapshots.record(
                access.session_hash, filters, search,
                (row.get("identity") or row.get("project_id") for row in result.get("projects", ())),
                getattr(facts, "facts_version", lambda: "")(), expires_at=value.expires_at,
            )

    def downstream_refresh_error(value, error):
        if not remote_credentials_rejected(error):
            return "failed"
        sessions.invalidate_credentials(value.username)
        return "invalid_credentials"

    @app.get("/api/confluence/project-facts/status")
    def confluence_project_facts_status(request: Request, value=Depends(authenticated_session)):
        del value
        return refresh.status_for(access_context(request).session_hash)

    @app.get("/api/confluence/project-facts")
    def confluence_project_facts(request: Request, owner=Depends(resolve_project_facts_owner),
                                 value=Depends(authenticated_session)):
        api_started = perf_counter()
        access = access_context(request)
        filters = {
            key.removeprefix("field."): tuple(value for value in request.query_params.getlist(key) if str(value).strip())
            for key, _value in request.query_params.multi_items()
            if key.startswith("field.")
        }
        search = request.query_params.get("search", "")
        load_details = request.query_params.get("details") == "1"
        replay_snapshot = request.query_params.get("snapshot") == "1"
        reset_snapshot = request.query_params.get("reset") == "1"
        if replay_snapshot:
            selection = snapshots.get(access.session_hash)
            if selection is not None:
                filters, search = selection.filters, selection.search
        elif reset_snapshot:
            filters, search = {}, ""
        pagination = {}
        if "page" in request.query_params or "pageSize" in request.query_params:
            try:
                pagination = {
                    "page": int(request.query_params.get("page", "0")),
                    "page_size": int(request.query_params.get("pageSize", "100")),
                }
            except ValueError as error:
                raise HTTPException(status_code=422, detail={"state": "invalid_pagination"}) from error
        def query_current():
            return owner.query(
                access, filters=filters, search=search, **pagination,
            )
        if load_details and value.password:
            result = query_current()
            record_query_snapshot(access, value, filters, search, result)
            selection = snapshots.get(access.session_hash)
            refresh.start_details(
                owner, access, value.password,
                filters=selection.filters if selection is not None else filters,
                search=selection.search if selection is not None else search,
                on_error=lambda error: downstream_refresh_error(value, error),
            )
        elif load_details:
            result = {**query_current(),
                      "detailState": "reauthentication_required"}
            record_query_snapshot(access, value, filters, search, result)
        else:
            result = query_current()
            record_query_snapshot(access, value, filters, search, result)
        catalog_scheduled = False
        if (
            result.get("state") == "no_snapshot"
            and value.password
            and refresh.state_for(access.session_hash) == "idle"
        ):
            catalog_scheduled = refresh.start(
                owner, access, value.password,
                on_error=lambda error: downstream_refresh_error(value, error),
            )
        refresh_state = refresh.state_for(access.session_hash)
        if refresh_state == "failed":
            result = {**result, "state": "failed"}
        elif refresh_state == "invalid_credentials":
            result = {**result, "state": "invalid_credentials"}
        elif refresh_state == "loading":
            result = {**result, "state": "loading"}
        elif refresh_state == "ready" and result.get("state") == "no_snapshot":
            result = {**result, "state": "ready"}
        elif result.get("state") == "no_snapshot" and not value.password:
            result = {**result, "state": "reauthentication_required"}
        result = {**result, "sync": refresh.status_for(access.session_hash)}
        smart_log("Confluence filter API timing", platform="web", domain="framework", source="project_facts", emit_runtime_event=False,
                  extra={"stage": "filter.api_total", "duration_ms": round((perf_counter() - api_started) * 1000, 3),
                         "request_state": str(result.get("state") or ""), "refresh_state": refresh_state,
                         "credential_present": bool(value.password),
                         "details_requested": load_details, "background_scheduled": catalog_scheduled,
                         "project_count": len(result.get("projects") or ())})
        return result

    @app.post("/api/confluence/project-facts/cancel")
    def cancel_confluence_project_sync(request: Request, value=Depends(authenticated_session)):
        key = audit_session(request)
        return {"cancelled": refresh.cancel(key), "sync": refresh.status_for(key)}

    @app.post("/api/audits/jira")
    def create_jira_audit(
        request: Request, payload: dict = Body(...),
        value=Depends(authenticated_session),
    ):
        owner = jira_audit_owner(value.username, value.password)
        session_id = audit_session(request)
        try:
            scope = owner.resolve(payload.get("input"))
            def finalize(task, report):
                directory = downloads.task_dir(task.id)
                try:
                    path = owner.export(
                        report, directory / f"Jira_Weekly_Review_{task.id}.xlsx",
                    )
                    artifact = downloads.register(
                        session_id, path, Path(path).name,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                except Exception as error:
                    raise RuntimeError("export_failed") from error
                return artifact.id
            task = audits.create(
                "jira", session_id,
                lambda token, progress: owner.run(scope, token, progress),
                context=scope,
                finalizer=finalize,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail={"state": "invalid_input"}) from error
        except AuditConflictError as error:
            raise HTTPException(status_code=409, detail={"state": "audit_running"}) from error
        return _audit_task_payload(task)

    @app.get("/api/audits/jira/{audit_id}")
    def get_jira_audit(
        audit_id: str, request: Request, value=Depends(authenticated_session),
    ):
        del value
        return _get_audit_payload(audits, audit_id, audit_session(request))

    @app.post("/api/audits/jira/{audit_id}/cancel")
    def cancel_jira_audit(
        audit_id: str, request: Request, value=Depends(authenticated_session),
    ):
        del value
        return _cancel_audit(audits, audit_id, audit_session(request))

    @app.post("/api/audits/jira/{audit_id}/export")
    def export_jira_audit(
        audit_id: str, request: Request, value=Depends(authenticated_session),
    ):
        del value
        session_id = audit_session(request)
        task = _owned_task(audits, audit_id, session_id)
        if task.status != "completed" or not task.download_id:
            raise HTTPException(status_code=409, detail={"state": "invalid_state"})
        try:
            artifact = downloads.get(task.download_id, session_id)
        except DownloadNotFoundError as error:
            raise HTTPException(status_code=404, detail={"state": "download_expired"}) from error
        return {"status": task.status, "download": _download_payload(artifact)}

    @app.post("/api/audits/confluence")
    def create_confluence_audit(
        request: Request, payload: dict = Body(...),
        value=Depends(authenticated_session),
    ):
        access = access_context(request)
        requested = payload.get("filters") or {}
        filters = {
            str(key): tuple(str(item) for item in values if str(item).strip())
            for key, values in (requested.get("fields") or {}).items()
        }
        search = str(requested.get("search") or "")
        snapshots.record(
            access.session_hash, filters, search, (),
            getattr(facts, "facts_version", lambda: "")(), expires_at=value.expires_at,
        )
        owner = confluence_audit_owner(access, value.password)
        try:
            period = manual_audit_period(
                date.fromisoformat(str(payload.get("startDate") or "")),
                date.fromisoformat(str(payload.get("endDate") or "")),
            )
            def run_review(token, progress):
                facts.refresh(access, value.password)
                result = facts.query(access, filters=filters, search=search)
                record_query_snapshot(access, value, filters, search, result)
                project_ids = tuple(
                    str(row.get("identity") or row.get("project_id"))
                    for row in result.get("projects", ())
                    if row.get("identity") or row.get("project_id")
                )
                resolved = owner.resolve({
                    "projectIds": list(project_ids),
                    "startDate": payload.get("startDate"),
                    "endDate": payload.get("endDate"),
                })
                return owner.run(resolved, token, progress)
            task = audits.create(
                "confluence", audit_session(request),
                run_review,
                context=period,
                validate=access.require_active,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail={"state": "invalid_input"}) from error
        except AuditConflictError as error:
            raise HTTPException(status_code=409, detail={"state": "audit_running"}) from error
        return _audit_task_payload(task)

    @app.get("/api/audits/confluence/{audit_id}")
    def get_confluence_audit(
        audit_id: str, request: Request, value=Depends(authenticated_session),
    ):
        del value
        return _get_audit_payload(audits, audit_id, audit_session(request))

    @app.post("/api/audits/confluence/{audit_id}/cancel")
    def cancel_confluence_audit(
        audit_id: str, request: Request, value=Depends(authenticated_session),
    ):
        del value
        return _cancel_audit(audits, audit_id, audit_session(request))

    @app.post("/api/audits/confluence/{audit_id}/export")
    def export_confluence_audit(
        audit_id: str, request: Request, value=Depends(authenticated_session),
    ):
        import zipfile
        session_id = audit_session(request)
        task = _owned_task(audits, audit_id, session_id)
        if task.status == "exported" and task.download_id:
            try:
                artifact = downloads.get(task.download_id, session_id)
                return {"status": task.status, "download": _download_payload(artifact)}
            except DownloadNotFoundError:
                pass
        if task.status != "completed":
            raise HTTPException(status_code=409, detail={"state": "invalid_state"})
        access = access_context(request)
        owner = confluence_audit_owner(access, value.password)
        directory = downloads.task_dir(task.id)
        start, end = _audit_dates(task.context)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_name = f"Confluence_Weekly_Review_{start}_{end}_{timestamp}.zip"
        target = directory / file_name
        try:
            paths = owner.export(task.result, directory)
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in paths:
                    archive.write(path, Path(path).name)
            artifact = access.publish((), lambda: downloads.register(
                session_id, target, file_name, "application/zip",
            ))
        except Exception as error:
            raise HTTPException(status_code=500, detail={"state": "export_failed"}) from error
        audits.exported(task.id, session_id, artifact.id)
        return {"status": "exported", "download": _download_payload(artifact)}

    @app.get("/api/downloads/{download_id}")
    def download_artifact(
        download_id: str, request: Request, value=Depends(authenticated_session),
    ):
        del value
        try:
            artifact = downloads.get(download_id, audit_session(request))
        except DownloadNotFoundError as error:
            raise HTTPException(
                status_code=404, detail={"state": "download_expired"},
            ) from error
        return FileResponse(
            artifact.file_path, filename=artifact.file_name,
            media_type=artifact.media_type,
        )

    @app.get("/api/report-workspaces/{source}")
    def report_list(source: str, request: Request, owner=Depends(resolve_report_owner)):
        if source != "jira":
            raise HTTPException(status_code=404, detail="Report source not found.")
        try:
            filters = {key: request.query_params.get(key) for key in ("product_line", "year", "report_type", "search", "jql")}
            return owner.list_reports(source, filters)
        except ReportNotFoundError as error:
            raise HTTPException(status_code=404, detail="Report source not found.") from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail={"state": "unauthorized"}) from error
        except Exception as error:
            raise HTTPException(status_code=502, detail={"state": "external_failure"}) from error

    @app.get("/api/report-workspaces/{source}/{report_id}")
    def report_detail(source: str, report_id: str, owner=Depends(resolve_report_owner)):
        if source != "jira":
            raise HTTPException(status_code=404, detail="Report source not found.")
        try:
            return owner.get_report(source, report_id)
        except ReportNotFoundError as error:
            raise HTTPException(status_code=404, detail="Report not found.") from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail={"state": "unauthorized"}) from error
        except Exception as error:
            raise HTTPException(status_code=502, detail={"state": "external_failure"}) from error

    @app.post("/api/report-workspaces/{source}/{report_id}/export")
    def report_export(
        source: str, report_id: str, request: Request,
        owner=Depends(resolve_report_owner), value=Depends(authenticated_session),
    ):
        del value
        if source != "jira":
            raise HTTPException(status_code=404, detail="Report source not found.")
        try:
            path = owner.download_path(source, report_id)
            artifact = downloads.stage(
                audit_session(request), path, path.name,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            return {"download": _download_payload(artifact)}
        except ReportNotFoundError as error:
            raise HTTPException(status_code=404, detail="Report not found.") from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail={"state": "unauthorized"}) from error
        except Exception as error:
            raise HTTPException(status_code=502, detail={"state": "external_failure"}) from error

    return app


def _issue_payload(issue, detail_names) -> dict:
    payload = {
        "id": issue.identity.id,
        "key": issue.identity.key,
        "webUrl": issue.identity.web_url,
        "summary": issue.summary,
        "project": {"id": issue.project.id, "key": issue.project.key, "name": issue.project.name},
        "status": {"id": issue.status.id, "name": issue.status.name},
        "issueType": {"id": issue.issue_type.id, "name": issue.issue_type.name},
        "priority": _json_value(issue.priority),
        "assignee": _json_value(issue.assignee),
        "reporter": _json_value(issue.reporter),
        "createdAt": _json_value(issue.created_at),
        "updatedAt": _json_value(issue.updated_at),
        "labels": list(issue.labels),
        "sourceRevision": issue.revision.value,
    }
    payload["details"] = {
        name: {
            "state": getattr(issue, name).state.value,
            "value": _json_value(getattr(issue, name).value),
            "sourceRevision": getattr(issue, name).source_revision,
            "errorCode": getattr(issue, name).error_code,
        }
        for name in detail_names
    }
    return payload


def _session_owner(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _owned_task(registry, audit_id, session_id):
    try:
        return registry.get(audit_id, session_id)
    except AuditNotFoundError as error:
        raise HTTPException(status_code=404, detail={"state": "not_found"}) from error


def _get_audit_payload(registry, audit_id, session_id):
    return _audit_task_payload(_owned_task(registry, audit_id, session_id))


def _cancel_audit(registry, audit_id, session_id):
    try:
        return _audit_task_payload(registry.cancel(audit_id, session_id))
    except AuditNotFoundError as error:
        raise HTTPException(status_code=404, detail={"state": "not_found"}) from error


def _audit_task_payload(task) -> dict:
    payload = {
        "auditId": task.id,
        "source": task.source,
        "status": task.status,
        "stage": task.stage,
        "progress": {"processed": task.processed, "total": task.total},
        "errorCode": task.error_code,
    }
    if task.manager_task_id:
        try:
            from .task_manager import WEB_TASKS, snapshot_payload
            payload["task"] = snapshot_payload(WEB_TASKS.snapshot(task.manager_task_id))
        except KeyError:
            pass
    return payload


def _download_payload(artifact) -> dict:
    return {
        "id": artifact.id,
        "fileName": artifact.file_name,
        "mediaType": artifact.media_type,
    }


def _audit_dates(context) -> tuple[str, str]:
    if isinstance(context, dict):
        return str(context.get("startDate")), str(context.get("endDate"))
    period = getattr(context, "period", context)
    return str(period.start.date()), str(period.end.date())


def _json_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return str(value)


configure_platform("web")
configure_external_logging("uvicorn", "uvicorn.error", platform="web", domain="web")
_default_app = None
_default_app_lock = Lock()


def _get_default_app():
    global _default_app
    if _default_app is None:
        with _default_app_lock:
            if _default_app is None:
                _default_app = create_app()
    return _default_app


async def app(scope, receive, send):
    """Create the default ASGI application lazily so imports never mutate app-data."""
    await _get_default_app()(scope, receive, send)
