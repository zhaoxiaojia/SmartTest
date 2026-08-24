from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Request

from .config import DatabaseSettings
from .database import ReadonlyDatabase
from .filters import WifiFilters
from .service import WifiDatabaseQueries


@lru_cache(maxsize=1)
def default_query_owner():
    return WifiDatabaseQueries(ReadonlyDatabase(DatabaseSettings.from_environment()))


def create_app(query_owner=default_query_owner) -> FastAPI:
    app = FastAPI(title="SmartTest Wi-Fi Database", docs_url=None, redoc_url=None, openapi_url=None)

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


app = create_app()
