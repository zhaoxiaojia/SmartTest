from __future__ import annotations

from functools import lru_cache
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from core.logging import configure_external_logging, configure_platform, smart_log

from .config import DatabaseSettings
from .database import ReadonlyDatabase
from .filters import WifiFilters
from .service import WifiDatabaseQueries


@lru_cache(maxsize=1)
def default_query_owner():
    return WifiDatabaseQueries(ReadonlyDatabase(DatabaseSettings.from_environment()))


def create_app(query_owner=default_query_owner) -> FastAPI:
    app = FastAPI(title="SmartTest Wi-Fi Database", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        started = perf_counter()
        request_id = request.headers.get("x-request-id", "").strip() or str(uuid4())
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
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

    return app


configure_platform("web")
app = create_app()
configure_external_logging("uvicorn", "uvicorn.error", platform="web", domain="web")
