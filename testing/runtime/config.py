from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from testing.runner.config import RUN_CONFIG_ENV


@dataclass(frozen=True)
class RuntimeConfig:
    nodeids: list[str] = field(default_factory=list)
    case_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    dut_serial: str = ""
    equipment: dict[str, Any] = field(default_factory=dict)
    global_context: dict[str, Any] = field(default_factory=dict)


def runtime_config() -> RuntimeConfig:
    payload = _json_env(RUN_CONFIG_ENV)
    if not isinstance(payload, dict):
        return RuntimeConfig()
    return RuntimeConfig(
        nodeids=[str(item) for item in list(payload.get("nodeids") or [])],
        case_configs={
            str(nodeid): dict(values)
            for nodeid, values in dict(payload.get("case_configs") or {}).items()
            if isinstance(values, dict)
        },
        dut_serial=str(payload.get("dut_serial", "") or "").strip(),
        equipment=dict(payload.get("equipment") or {}) if isinstance(payload.get("equipment"), dict) else {},
        global_context=dict(payload.get("global_context") or {})
        if isinstance(payload.get("global_context"), dict)
        else {},
    )


def current_dut_serial() -> str:
    value = runtime_config().dut_serial
    if value:
        return value
    return str(os.environ.get("SMARTTEST_ADB_SERIAL", "") or "").strip()


def equipment_config() -> dict[str, Any]:
    return dict(runtime_config().equipment)


def _json_env(name: str) -> Any:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
