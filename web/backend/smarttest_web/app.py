from __future__ import annotations

from functools import lru_cache
from time import perf_counter
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from core.authentication import LdapAuthenticator
from core.logging import configure_external_logging, configure_platform, smart_log
from core.tools.common.project_weekly_audit import summarize_project_fact_filters

from .config import DatabaseSettings
from .database import ReadonlyDatabase
from .filters import WifiFilters
from .service import WifiDatabaseQueries
from .report_workspace import ClientAuditReportOwner, ReportNotFoundError
from .project_facts_api import ProjectFactsWebOwner
from .session import PersistentSessionStore
from .background_refresh import BackgroundFactsRefresh
from .credentials import CredentialStoreError

SESSION_COOKIE = "smarttest_session"


@lru_cache(maxsize=1)
def default_query_owner():
    return WifiDatabaseQueries(ReadonlyDatabase(DatabaseSettings.from_environment()))


def default_authenticator():
    return LdapAuthenticator(platform="web")


def create_app(query_owner=default_query_owner, report_owner=ClientAuditReportOwner.from_environment,
               project_facts_owner=ProjectFactsWebOwner, authenticator=default_authenticator,
               session_store=PersistentSessionStore, facts_refresh=BackgroundFactsRefresh) -> FastAPI:
    app = FastAPI(title="SmartTest Wi-Fi Database", docs_url=None, redoc_url=None, openapi_url=None)
    auth = authenticator()
    sessions = session_store()
    facts = project_facts_owner()
    refresh = facts_refresh()

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
                response.set_cookie(
                    SESSION_COOKIE, request.cookies[SESSION_COOKIE], httponly=True, secure=True,
                    samesite="lax", max_age=sessions.ttl_seconds, path="/",
                )
            response.headers["x-request-id"] = request_id
            return response
        finally:
            smart_log(
                f"{request.method} {request.url.path} {status}",
                platform="web",
                domain="web",
                level="error" if status >= 500 else "warning" if status >= 400 else "info",
                source="request",
                request_id=request_id,
                extra={"method": request.method, "path": request.url.path, "status": status,
                       "duration_ms": round((perf_counter() - started) * 1000, 3)},
                emit_runtime_event=False,
            )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    def current_session(request: Request):
        value = sessions.get(request.cookies.get(SESSION_COOKIE, ""))
        if value is not None and value.cookie_renewal_required:
            request.state.renew_session_cookie = True
        return value

    def public_session(value):
        if value is None:
            return {"authenticated": False}
        return {"authenticated": True, "username": value.username,
                "displayName": value.display_name,
                "avatarUrl": "/api/auth/avatar" if value.avatar_bytes else ""}

    @app.post("/api/auth/login")
    def login(response: Response, payload: dict = Body(...)):
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        result = auth.authenticate(username, password)
        if not result.get("success"):
            code = result.get("code") if result.get("code") in {"invalid_credentials", "ldap_unavailable"} else "ldap_unavailable"
            raise HTTPException(status_code=401 if code == "invalid_credentials" else 503,
                                detail={"state": code})
        try:
            session_id = sessions.create(result["username"], password,
                                         result.get("display_name", ""), result.get("avatar_bytes", b""))
        except CredentialStoreError as error:
            smart_log("Persistent Web credential storage failed", platform="web", domain="auth",
                      source="login", level="error", extra={"exception_type": type(error).__name__})
            raise HTTPException(status_code=503, detail={"state": "credential_store_unavailable"}) from error
        if facts.query(result["username"]).get("state") == "no_snapshot":
            refresh.start(facts, result["username"], password)
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, secure=True,
                            samesite="lax", max_age=sessions.ttl_seconds, path="/")
        return public_session(sessions.get(session_id))

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
        sessions.delete(request.cookies.get(SESSION_COOKIE, ""))
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=True, samesite="lax")
        return {"authenticated": False}

    @app.post("/api/auth/logout-all")
    def logout_all(request: Request, response: Response):
        value = current_session(request)
        if value is None:
            raise HTTPException(status_code=401, detail={"state": "unauthenticated"})
        sessions.delete_all(value.username)
        request.state.renew_session_cookie = False
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=True, samesite="lax")
        return {"authenticated": False}

    def authenticated_session(request: Request):
        value = current_session(request)
        if value is None:
            raise HTTPException(status_code=401, detail={"state": "unauthenticated"})
        return value

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

    @app.get("/api/confluence/project-facts")
    def confluence_project_facts(request: Request, owner=Depends(resolve_project_facts_owner),
                                 value=Depends(authenticated_session)):
        filters = {
            key.removeprefix("field."): tuple(value for value in request.query_params.getlist(key) if str(value).strip())
            for key, _value in request.query_params.multi_items()
            if key.startswith("field.")
        }
        search = request.query_params.get("search", "")
        load_details = request.query_params.get("details") == "1"
        safe_filters = summarize_project_fact_filters(filters)
        smart_log("Confluence project facts request received", platform="web", domain="confluence",
                  source="confluence_project_facts", request_id=request.state.request_id,
                  extra={"filters": safe_filters, "search_enabled": bool(search.strip())})
        if load_details and value.password:
            result = owner.enrich(value.username, value.password, filters=filters, search=search)
        elif load_details:
            result = {**owner.query(value.username, filters=filters, search=search),
                      "detailState": "reauthentication_required"}
        else:
            result = owner.query(value.username, filters=filters, search=search)
        refresh_state = refresh.state_for(value.username)
        if refresh_state == "failed":
            result = {**result, "state": "failed"}
        elif refresh_state == "loading":
            result = {**result, "state": "loading"}
        elif result.get("state") == "no_snapshot":
            if value.password:
                refresh.start(owner, value.username, value.password)
                result = {**result, "state": "loading"}
            else:
                result = {**result, "state": "reauthentication_required"}
        hierarchy = result.get("ownerHierarchy", [])
        hierarchy_summary = {
            "roles": len(hierarchy),
            "people": sum(len(role.get("people", [])) for role in hierarchy),
            "projects": sum(len(person.get("projects", []))
                            for role in hierarchy for person in role.get("people", [])),
        }
        smart_log("Confluence project facts response ready", platform="web", domain="confluence",
                  source="confluence_project_facts", request_id=request.state.request_id,
                  extra={"state": result.get("state"), "snapshot_time": result.get("snapshotTime"),
                         "project_count": len(result.get("projects", [])),
                         "facet_count": len(result.get("facets", [])), "hierarchy": hierarchy_summary})
        return result

    @app.post("/api/confluence/project-facts/refresh")
    def refresh_confluence_project_facts(request: Request, owner=Depends(resolve_project_facts_owner)):
        value = current_session(request)
        if value is None:
            raise HTTPException(status_code=401, detail={"state": "unauthenticated"})
        if not value.password:
            raise HTTPException(status_code=401, detail={"state": "reauthentication_required"})
        result = owner.query(value.username)
        refresh.start(owner, value.username, value.password)
        return {**result, "state": "loading"}

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

    @app.get("/api/report-workspaces/{source}/{report_id}/download")
    def report_download(source: str, report_id: str, owner=Depends(resolve_report_owner)):
        if source != "jira":
            raise HTTPException(status_code=404, detail="Report source not found.")
        try:
            path = owner.download_path(source, report_id)
            return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except ReportNotFoundError as error:
            raise HTTPException(status_code=404, detail="Report not found.") from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail={"state": "unauthorized"}) from error
        except Exception as error:
            raise HTTPException(status_code=502, detail={"state": "external_failure"}) from error

    return app


configure_platform("web")
app = create_app()
configure_external_logging("uvicorn", "uvicorn.error", platform="web", domain="web")
