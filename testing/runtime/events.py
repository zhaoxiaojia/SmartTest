from __future__ import annotations

import json
import os
import threading
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Any


_EVENT_PATH_ENV = "SMARTTEST_STEP_EVENTS_OUT"
_WRITE_LOCK = threading.Lock()

_CURRENT_CASE_NODEID: ContextVar[str | None] = ContextVar("smarttest_current_case_nodeid", default=None)
_STEP_STACK: ContextVar[list[dict[str, Any]]] = ContextVar("smarttest_step_stack", default=[])


def current_case_nodeid() -> str | None:
    return _CURRENT_CASE_NODEID.get()


def current_step() -> dict[str, Any] | None:
    stack = _STEP_STACK.get()
    return stack[-1] if stack else None


def set_current_case_nodeid(nodeid: str | None):
    return _CURRENT_CASE_NODEID.set(nodeid)


def reset_current_case_nodeid(token) -> None:
    _CURRENT_CASE_NODEID.reset(token)


def push_step(step_payload: dict[str, Any]):
    stack = list(_STEP_STACK.get())
    stack.append(dict(step_payload))
    return _STEP_STACK.set(stack)


def pop_step(token) -> None:
    _STEP_STACK.reset(token)


def emit_event(event_type: str, **payload: Any) -> None:
    raw_path = os.environ.get(_EVENT_PATH_ENV, "").strip()
    if not raw_path:
        return

    event = {
        "type": event_type,
        "timestamp": time.time(),
        **payload,
    }
    event_path = Path(raw_path)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(event, ensure_ascii=False) + "\n"
    with _WRITE_LOCK:
        with event_path.open("a", encoding="utf-8") as fh:
            fh.write(encoded)
