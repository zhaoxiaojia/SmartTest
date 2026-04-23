from __future__ import annotations

import traceback
import uuid
from contextlib import contextmanager
import re
from typing import Any, Iterator

from .events import current_case_nodeid, current_step, emit_event, pop_step, push_step


_DEFINITION_ID_RE = re.compile(r"^[a-z0-9]+(?:[._][a-z0-9]+)*$")


def _normalize_definition_id(definition_id: str | None) -> str | None:
    if definition_id is None:
        return None
    normalized = str(definition_id).strip()
    if not normalized:
        return None
    if not _DEFINITION_ID_RE.fullmatch(normalized):
        raise ValueError(
            "SmartTest step definition_id must use lowercase letters/numbers separated by '.' or '_'."
        )
    return normalized


@contextmanager
def step(
    title: str,
    *,
    phase: str = "call",
    kind: str = "case",
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    case_nodeid = current_case_nodeid()
    if not case_nodeid:
        raise RuntimeError("SmartTest step used outside of an active pytest test case.")

    normalized_definition_id = _normalize_definition_id(definition_id)
    payload_meta = dict(meta or {})
    if normalized_definition_id is not None:
        payload_meta.setdefault("definition_id", normalized_definition_id)

    parent = current_step()
    step_id = f"step:{uuid.uuid4().hex}"
    payload = {
        "id": step_id,
        "title": str(title),
        "phase": str(phase),
        "kind": str(kind),
        "definition_id": normalized_definition_id,
        "case_nodeid": case_nodeid,
        "parent_id": parent["id"] if parent else None,
        "meta": payload_meta,
    }
    token = push_step(payload)
    emit_event(
        "step_started",
        step_id=payload["id"],
        case_nodeid=case_nodeid,
        parent_id=payload["parent_id"],
        title=payload["title"],
        phase=payload["phase"],
        kind=payload["kind"],
        definition_id=payload["definition_id"],
        meta=payload["meta"],
    )
    try:
        yield payload
    except Exception as exc:  # noqa: BLE001
        emit_event(
            "step_finished",
            step_id=payload["id"],
            case_nodeid=case_nodeid,
            status="failed",
            error=str(exc),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
        raise
    else:
        emit_event(
            "step_finished",
            step_id=payload["id"],
            case_nodeid=case_nodeid,
            status="passed",
        )
    finally:
        pop_step(token)


def step_log(message: str, *, level: str = "info", extra: dict[str, Any] | None = None) -> None:
    case_nodeid = current_case_nodeid()
    if not case_nodeid:
        return
    current = current_step()
    emit_event(
        "log",
        case_nodeid=case_nodeid,
        step_id=current["id"] if current else None,
        level=str(level),
        message=str(message),
        extra=dict(extra or {}),
    )


def setup_step(title: str, *, definition_id: str | None = None, meta: dict[str, Any] | None = None):
    return step(title, phase="setup", kind="setup", definition_id=definition_id, meta=meta)


def teardown_step(title: str, *, definition_id: str | None = None, meta: dict[str, Any] | None = None):
    return step(title, phase="teardown", kind="teardown", definition_id=definition_id, meta=meta)


def case_step(title: str, *, definition_id: str | None = None, meta: dict[str, Any] | None = None):
    return step(title, phase="call", kind="case", definition_id=definition_id, meta=meta)


def action_step(
    title: str,
    *,
    phase: str = "call",
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
):
    return step(title, phase=phase, kind="action", definition_id=definition_id, meta=meta)


def loop_step(
    title: str,
    *,
    index: int,
    total: int,
    phase: str = "call",
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
):
    payload = dict(meta or {})
    payload.update({"index": index, "total": total})
    return step(
        f"{title} ({index}/{total})",
        phase=phase,
        kind="loop",
        definition_id=definition_id,
        meta=payload,
    )
