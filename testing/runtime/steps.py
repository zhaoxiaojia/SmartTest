from __future__ import annotations

import traceback
import uuid
from contextlib import contextmanager
import re
from typing import Any, Iterator

import pytest

from .events import current_case_nodeid, current_case_stress_tolerant, current_step, emit_event, pop_step, push_step


_DEFINITION_ID_RE = re.compile(r"^[a-z0-9]+(?:[._][a-z0-9]+)*$")


class StressCheckFailure(AssertionError):
    """Detection failure that stress cases should log and continue past."""


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


def _new_step_payload(
    title: str,
    *,
    phase: str,
    kind: str,
    definition_id: str | None,
    meta: dict[str, Any] | None,
    expected: Any = None,
    parent_id: str | None = None,
    step_id: str | None = None,
) -> dict[str, Any]:
    case_nodeid = current_case_nodeid()
    if not case_nodeid:
        raise RuntimeError("SmartTest step used outside of an active pytest test case.")

    normalized_definition_id = _normalize_definition_id(definition_id)
    payload_meta = dict(meta or {})
    if normalized_definition_id is not None:
        payload_meta.setdefault("definition_id", normalized_definition_id)

    parent = current_step()
    return {
        "id": step_id or f"step:{uuid.uuid4().hex}",
        "title": str(title),
        "phase": str(phase),
        "kind": str(kind),
        "definition_id": normalized_definition_id,
        "case_nodeid": case_nodeid,
        "parent_id": parent_id if parent_id is not None else (parent["id"] if parent else None),
        "meta": payload_meta,
        "expected": expected,
    }


def plan_step(
    title: str,
    *,
    phase: str = "call",
    kind: str = "action",
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
    expected: Any = None,
    parent_id: str | None = None,
    step_id: str | None = None,
) -> dict[str, Any]:
    payload = _new_step_payload(
        title,
        phase=phase,
        kind=kind,
        definition_id=definition_id,
        meta=meta,
        expected=expected,
        parent_id=parent_id,
        step_id=step_id,
    )
    emit_event(
        "step_planned",
        step_id=payload["id"],
        case_nodeid=payload["case_nodeid"],
        parent_id=payload["parent_id"],
        title=payload["title"],
        phase=payload["phase"],
        kind=payload["kind"],
        definition_id=payload["definition_id"],
        meta=payload["meta"],
        expected=payload["expected"],
    )
    return payload


@contextmanager
def step(
    title: str,
    *,
    phase: str = "call",
    kind: str = "action",
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
    expected: Any = None,
    actual: Any = None,
    step_id: str | None = None,
    stress_tolerant: bool | None = None,
) -> Iterator[dict[str, Any]]:
    payload = _new_step_payload(
        title,
        phase=phase,
        kind=kind,
        definition_id=definition_id,
        meta=meta,
        expected=expected,
        step_id=step_id,
    )
    token = push_step(payload)
    emit_event(
        "step_planned",
        step_id=payload["id"],
        case_nodeid=payload["case_nodeid"],
        parent_id=payload["parent_id"],
        title=payload["title"],
        phase=payload["phase"],
        kind=payload["kind"],
        definition_id=payload["definition_id"],
        meta=payload["meta"],
        expected=payload["expected"],
    )
    emit_event(
        "step_started",
        step_id=payload["id"],
        case_nodeid=payload["case_nodeid"],
        parent_id=payload["parent_id"],
        title=payload["title"],
        phase=payload["phase"],
        kind=payload["kind"],
        definition_id=payload["definition_id"],
        meta=payload["meta"],
        expected=payload["expected"],
    )
    try:
        yield payload
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:  # noqa: BLE001
        if _should_soft_fail_stress_step(exc, stress_tolerant=stress_tolerant):
            formatted_traceback = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            message = (
                "[stress.soft_failure] "
                f"step_id={payload['id']} definition_id={payload['definition_id']} "
                f"exception={type(exc).__name__}: {exc}"
            )
            soft_actual = {
                "stress_soft_failure": True,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "actual": actual,
            }
            print(message)
            step_log(
                message,
                level="warning",
                extra={
                    "step_id": payload["id"],
                    "definition_id": payload["definition_id"],
                    "exception_type": type(exc).__name__,
                },
            )
            step_evidence(
                "Stress soft failure traceback",
                formatted_traceback,
                evidence_type="traceback",
                level="warning",
                meta={
                    "step_id": payload["id"],
                    "definition_id": payload["definition_id"],
                    "exception_type": type(exc).__name__,
                },
            )
            emit_event(
                "step_finished",
                step_id=payload["id"],
                case_nodeid=payload["case_nodeid"],
                status="passed",
                actual=soft_actual,
            )
            return
        emit_event(
            "step_finished",
            step_id=payload["id"],
            case_nodeid=payload["case_nodeid"],
            status="failed",
            error=str(exc),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            actual=actual,
        )
        raise
    else:
        emit_event(
            "step_finished",
            step_id=payload["id"],
            case_nodeid=payload["case_nodeid"],
            status="passed",
            actual=actual,
        )
    finally:
        pop_step(token)


def _should_soft_fail_stress_step(exc: BaseException, *, stress_tolerant: bool | None) -> bool:
    if stress_tolerant is False:
        return False
    if stress_tolerant is not True and not current_case_stress_tolerant():
        return False
    return isinstance(exc, (AssertionError, StressCheckFailure, pytest.fail.Exception))


def step_evidence(
    title: str,
    content: Any,
    *,
    evidence_type: str = "log",
    level: str = "info",
    meta: dict[str, Any] | None = None,
) -> None:
    case_nodeid = current_case_nodeid()
    if not case_nodeid:
        return
    current = current_step()
    emit_event(
        "step_evidence",
        case_nodeid=case_nodeid,
        step_id=current["id"] if current else None,
        title=str(title),
        evidence_type=str(evidence_type),
        level=str(level),
        content=content,
        meta=dict(meta or {}),
    )


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
    step_evidence("Log", str(message), evidence_type="log", level=level, meta=extra)


def setup_step(
    title: str,
    *,
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
    stress_tolerant: bool | None = None,
):
    return step(
        title,
        phase="setup",
        kind="setup",
        definition_id=definition_id,
        meta=meta,
        stress_tolerant=stress_tolerant,
    )


def teardown_step(
    title: str,
    *,
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
    stress_tolerant: bool | None = None,
):
    return step(
        title,
        phase="teardown",
        kind="teardown",
        definition_id=definition_id,
        meta=meta,
        stress_tolerant=stress_tolerant,
    )


def case_step(
    title: str,
    *,
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
    expected: Any = None,
    stress_tolerant: bool | None = None,
):
    return step(
        title,
        phase="call",
        kind="step",
        definition_id=definition_id,
        meta=meta,
        expected=expected,
        stress_tolerant=stress_tolerant,
    )


def action_step(
    title: str,
    *,
    phase: str = "call",
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
    expected: Any = None,
    stress_tolerant: bool | None = None,
):
    return step(
        title,
        phase=phase,
        kind="action",
        definition_id=definition_id,
        meta=meta,
        expected=expected,
        stress_tolerant=stress_tolerant,
    )


def loop_step(
    title: str,
    *,
    index: int,
    total: int,
    phase: str = "call",
    definition_id: str | None = None,
    meta: dict[str, Any] | None = None,
    stress_tolerant: bool | None = None,
):
    payload = dict(meta or {})
    payload.update({"index": index, "total": total})
    return step(
        f"{title} ({index}/{total})",
        phase=phase,
        kind="loop",
        definition_id=definition_id,
        meta=payload,
        stress_tolerant=stress_tolerant,
    )
