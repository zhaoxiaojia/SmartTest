from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from testing.cases.catalog import load_runtime_test_catalog
from testing.params.adb_devices import list_adb_devices
from testing.state.models import TestPageState


RUN_CONFIG_ENV = "SMARTTEST_RUN_CONFIG_JSON"


@dataclass(frozen=True)
class RunConfig:
    nodeids: list[str] = field(default_factory=list)
    case_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    dut_serial: str | None = None
    equipment: dict[str, Any] = field(default_factory=dict)
    global_context: dict[str, Any] = field(default_factory=dict)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "nodeids": list(self.nodeids),
            "case_configs": {str(key): dict(value) for key, value in self.case_configs.items()},
            "dut_serial": str(self.dut_serial or ""),
            "equipment": dict(self.equipment),
            "global_context": dict(self.global_context),
        }


def resolve_dut_serial(
    selected_serial: str | None,
    *,
    devices: list[str] | None = None,
    device_lister: Callable[[], list[str]] | None = None,
) -> str | None:
    current_devices = devices if devices is not None else (device_lister or list_adb_devices)()
    selected = str(selected_serial or "").strip()
    if selected and selected in current_devices:
        return selected
    if len(current_devices) == 1:
        return current_devices[0]
    return None


def normalize_selected_run_inputs(
    *,
    root_dir: Path,
    nodeids: list[str],
    case_configs: dict[str, dict[str, Any]],
) -> tuple[list[str], dict[str, dict[str, Any]], list[str]]:
    catalog_by_android_id = {
        str(row.get("android_case_id", "") or ""): str(row.get("nodeid", "") or "")
        for row in load_runtime_test_catalog(root_dir=root_dir)
        if str(row.get("android_case_id", "") or "") and str(row.get("nodeid", "") or "")
    }
    normalized_nodeids: list[str] = []
    normalized_configs: dict[str, dict[str, Any]] = {}
    diagnostics: list[str] = []
    for nodeid in nodeids:
        raw_nodeid = str(nodeid or "").strip()
        mapped_nodeid = raw_nodeid
        if raw_nodeid.startswith("android://"):
            case_id = raw_nodeid[len("android://") :].strip()
            mapped_nodeid = catalog_by_android_id.get(case_id, "")
            diagnostics.append(
                "[steps.trace] legacy_android_nodeid "
                f"from={raw_nodeid or '<empty>'} to={mapped_nodeid or '<unmapped>'} "
                f"case_id={case_id or '<empty>'}"
            )
            if not mapped_nodeid:
                mapped_nodeid = raw_nodeid
        if mapped_nodeid not in normalized_nodeids:
            normalized_nodeids.append(mapped_nodeid)
        normalized_configs[mapped_nodeid] = dict(case_configs.get(raw_nodeid, case_configs.get(mapped_nodeid, {})))
    return normalized_nodeids, normalized_configs, diagnostics


def build_run_config_from_state(
    *,
    root_dir: Path,
    state: TestPageState,
    device_lister: Callable[[], list[str]] | None = None,
) -> tuple[RunConfig, list[str]]:
    raw_nodeids = [case.nodeid for case in state.selected if case.nodeid]
    raw_case_configs = {
        nodeid: dict(state.case_configs.get(nodeid, {}))
        for nodeid in raw_nodeids
        if isinstance(state.case_configs.get(nodeid, {}), dict)
    }
    nodeids, case_configs, diagnostics = normalize_selected_run_inputs(
        root_dir=root_dir,
        nodeids=raw_nodeids,
        case_configs=raw_case_configs,
    )
    global_context = dict(state.global_context)
    dut_serial = resolve_dut_serial(str(global_context.get("dut", "") or ""), device_lister=device_lister)
    equipment = _equipment_config(global_context)
    return (
        RunConfig(
            nodeids=nodeids,
            case_configs=case_configs,
            dut_serial=dut_serial,
            equipment=equipment,
            global_context=global_context,
        ),
        diagnostics,
    )


def run_config_to_json(run_config: RunConfig) -> str:
    return json.dumps(run_config.to_jsonable(), ensure_ascii=False)


def _equipment_config(global_context: dict[str, Any]) -> dict[str, Any]:
    raw = global_context.get("equipment", global_context.get("test_equipment", {}))
    return dict(raw) if isinstance(raw, dict) else {}
