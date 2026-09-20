from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Request

from .audit_http import download_payload, request_session_id
from .report_workspace import ReportNotFoundError


def create_router(authenticated_session, report_owner, downloads) -> APIRouter:
    router = APIRouter()

    def resolve_report_owner():
        try:
            return report_owner()
        except Exception as error:
            raise HTTPException(status_code=503, detail={"state": "config_missing"}) from error

    @router.get("/api/report-workspaces/{source}")
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

    @router.get("/api/report-workspaces/{source}/{report_id}")
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

    @router.post("/api/report-workspaces/{source}/{report_id}/export")
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
                request_session_id(request), path, path.name,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            return {"download": download_payload(artifact)}
        except ReportNotFoundError as error:
            raise HTTPException(status_code=404, detail="Report not found.") from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail={"state": "unauthorized"}) from error
        except Exception as error:
            raise HTTPException(status_code=502, detail={"state": "external_failure"}) from error

    return router
