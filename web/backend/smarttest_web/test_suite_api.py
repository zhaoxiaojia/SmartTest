from __future__ import annotations

from fastapi import APIRouter
from fastapi import Body, Depends, HTTPException

from .test_suite_repository import NameConflictError, RevisionConflictError


def create_router(authenticated_session, test_suites) -> APIRouter:
    router = APIRouter()

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

    @router.get("/api/test-suites")
    def list_test_suites(scope: str, value=Depends(authenticated_session)):
        if scope == "mine":
            rows = test_suites.list_mine(value.username)
        elif scope == "shared":
            rows = test_suites.list_shared(value.username)
        else:
            raise HTTPException(status_code=422, detail={"state": "invalid_input"})
        return [suite_payload(row) for row in rows]

    @router.get("/api/test-suites/{suite_id}")
    def get_test_suite(suite_id: str, value=Depends(authenticated_session)):
        record = test_suites.get_visible(suite_id, value.username)
        if record is None:
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        return suite_payload(record, detail=True)

    @router.post("/api/test-suites")
    def create_test_suite(payload: dict = Body(...), value=Depends(authenticated_session)):
        name, description, visibility, nodeids, _ = suite_input(payload)
        try:
            record = test_suites.create(owner_username=value.username,
                owner_display_name=value.display_name or value.username, name=name,
                description=description, visibility=visibility, ordered_nodeids=nodeids)
        except NameConflictError as error:
            raise HTTPException(status_code=409, detail={"state": "name_conflict"}) from error
        return suite_payload(record, detail=True)

    @router.put("/api/test-suites/{suite_id}")
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

    @router.delete("/api/test-suites/{suite_id}")
    def delete_test_suite(suite_id: str, value=Depends(authenticated_session)):
        if not test_suites.delete(suite_id, owner_username=value.username):
            raise HTTPException(status_code=404, detail={"state": "not_found"})
        return {"deleted": True}

    @router.post("/api/test-suites/{suite_id}/copy")
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

    return router
