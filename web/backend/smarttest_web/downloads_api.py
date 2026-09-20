from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse

from .audit_http import (
    audit_dates as _audit_dates,
    confluence_access,
    download_payload as _download_payload,
    owned_task as _owned_task,
    request_session_id,
)
from .downloads import DownloadNotFoundError


def create_router(authenticated_session, downloads, sessions, cache_database, audits,
                  confluence_audit_owner) -> APIRouter:
    router = APIRouter()

    def audit_session(request):
        return request_session_id(request)

    def access_context(request):
        return confluence_access(sessions, cache_database, request)

    @router.post("/api/audits/confluence/{audit_id}/export")
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

    @router.get("/api/downloads/{download_id}")
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

    return router
