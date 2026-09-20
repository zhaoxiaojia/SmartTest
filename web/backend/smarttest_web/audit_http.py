from __future__ import annotations

import hashlib
import os

from fastapi import HTTPException

from .audit.registry import AuditNotFoundError
from .task_manager import snapshot_payload


def session_owner(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def request_session_id(request) -> str:
    return session_owner(request.cookies.get("smarttest_session", ""))


def confluence_access(sessions, database, request):
    base = os.getenv("SMARTTEST_CONFLUENCE_BASE_URL", "https://confluence.amlogic.com")
    return sessions.resource_access(
        request.cookies.get("smarttest_session", ""),
        f"confluence:{base.rstrip('/').lower()}", database,
    )


def owned_task(registry, audit_id, session_id):
    try:
        return registry.get(audit_id, session_id)
    except AuditNotFoundError as error:
        raise HTTPException(status_code=404, detail={"state": "not_found"}) from error


def get_audit_payload(registry, audit_id, session_id):
    return audit_task_payload(owned_task(registry, audit_id, session_id))


def cancel_audit(registry, audit_id, session_id):
    try:
        return audit_task_payload(registry.cancel(audit_id, session_id))
    except AuditNotFoundError as error:
        raise HTTPException(status_code=404, detail={"state": "not_found"}) from error


def audit_task_payload(task) -> dict:
    payload = {
        "auditId": task.id, "source": task.source, "status": task.status,
        "stage": task.stage, "progress": {"processed": task.processed, "total": task.total},
        "errorCode": task.error_code,
    }
    if task.manager_task_id:
        try:
            payload["task"] = snapshot_payload(task.manager.snapshot(task.manager_task_id))
        except KeyError:
            pass
    return payload


def download_payload(artifact) -> dict:
    return {"id": artifact.id, "fileName": artifact.file_name,
            "mediaType": artifact.media_type}


def audit_dates(context) -> tuple[str, str]:
    if isinstance(context, dict):
        return str(context.get("startDate")), str(context.get("endDate"))
    period = getattr(context, "period", context)
    return str(period.start.date()), str(period.end.date())
