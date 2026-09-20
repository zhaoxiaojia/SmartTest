from __future__ import annotations

from fastapi import APIRouter
from fastapi import Body, Depends, HTTPException, Request

from .filters import WifiFilters


def create_router(authenticated_session, sessions, query_owner) -> APIRouter:
    router = APIRouter()

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

    @router.get("/api/preferences/{scope:path}")
    def get_preferences(scope: str, value=Depends(authenticated_session)):
        return sessions.get_preferences(value.username, scope)

    @router.put("/api/preferences/{scope:path}")
    def put_preferences(scope: str, payload: dict = Body(...), value=Depends(authenticated_session)):
        items, version = validate_preference_payload(scope, payload)
        return sessions.upsert_preferences(value.username, scope, items, version)

    @router.delete("/api/preferences/{scope:path}")
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

    @router.get("/api/filters")
    def filters(filters: WifiFilters = Depends(filters_from_request), owner=Depends(resolve_query_owner)):
        try:
            return owner.get_filters(filters)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Wi-Fi Database is unavailable.") from error

    @router.get("/api/performance")
    def performance(filters: WifiFilters = Depends(filters_from_request), owner=Depends(resolve_query_owner)):
        try:
            return owner.get_performance(filters)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Wi-Fi Database is unavailable.") from error

    return router
