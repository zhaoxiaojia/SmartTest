from __future__ import annotations

import json
import os
from typing import Any, Callable


_CASE_CONFIGS_ENV = "SMARTTEST_CASE_CONFIGS_JSON"


def _case_configs() -> dict[str, dict[str, Any]]:
    raw = os.environ.get(_CASE_CONFIGS_ENV, "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(nodeid): dict(values)
        for nodeid, values in payload.items()
        if isinstance(nodeid, str) and isinstance(values, dict)
    }


def case_config(nodeid: str) -> dict[str, Any]:
    return dict(_case_configs().get(str(nodeid), {}))


def case_param(
    nodeid: str,
    key: str,
    default: Any = None,
    *,
    cast: Callable[[Any], Any] | None = None,
) -> Any:
    value = _case_configs().get(str(nodeid), {}).get(str(key), default)
    if cast is None or value is None:
        return value
    return cast(value)


def request_case_param(
    request,
    key: str,
    default: Any = None,
    *,
    cast: Callable[[Any], Any] | None = None,
) -> Any:
    return case_param(request.node.nodeid, key, default, cast=cast)
