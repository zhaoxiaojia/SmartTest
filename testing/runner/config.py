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
    dut_serial: str | None = None
    dut_serials: list[str] = field(default_factory=list)
    equipment: dict[str, Any] = field(default_factory=dict)
    global_context: dict[str, Any] = field(default_factory=dict)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "nodeids": list(self.nodeids),
            "dut_serial": str(self.dut_serial or ""),
            "dut_serials": list(self.dut_serials),
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


def selected_dut_serials(
    state: TestPageState,
    *,
    devices: list[str] | None = None,
    device_lister: Callable[[], list[str]] | None = None,
) -> list[str]:
    current_devices = devices if devices is not None else (device_lister or list_adb_devices)()
    online = [str(item or "").strip() for item in current_devices if str(item or "").strip()]
    online_set = set(online)
    raw_context = dict(getattr(state, "global_context", {}) or {})
    raw_selected = raw_context.get("duts", [])
    selected: list[str] = []
    if isinstance(raw_selected, list):
        for item in raw_selected:
            serial = str(item or "").strip()
            if serial and serial in online_set and serial not in selected:
                selected.append(serial)
    legacy = str(raw_context.get("dut", "") or "").strip()
    if not selected and legacy and legacy in online_set:
        selected.append(legacy)
    if not selected and len(online) == 1:
        selected.append(online[0])
    return selected


def normalize_selected_run_inputs(
    *,
    root_dir: Path,
    nodeids: list[str],
) -> tuple[list[str], list[str]]:
    catalog_by_android_id = {
        str(row.get("android_case_id", "") or ""): str(row.get("nodeid", "") or "")
        for row in load_runtime_test_catalog(root_dir=root_dir)
        if str(row.get("android_case_id", "") or "") and str(row.get("nodeid", "") or "")
    }
    normalized_nodeids: list[str] = []
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
    return normalized_nodeids, diagnostics


def build_run_config_from_state(
    *,
    root_dir: Path,
    state: TestPageState,
    device_lister: Callable[[], list[str]] | None = None,
) -> tuple[RunConfig, list[str]]:
    from testing.test_context import smarttest_context

    raw_nodeids = [case.nodeid for case in state.selected if case.nodeid]
    nodeids, diagnostics = normalize_selected_run_inputs(
        root_dir=root_dir,
        nodeids=raw_nodeids,
    )
    smarttest_context().params.bind_ui_state(state)
    global_context = smarttest_context().params.global_context_snapshot()
    dut_serials = selected_dut_serials(state, device_lister=device_lister)
    raw_equipment = smarttest_context().params.equipment_config()
    return (
        RunConfig(
            nodeids=nodeids,
            dut_serial=dut_serials[0] if dut_serials else None,
            dut_serials=dut_serials,
            equipment=dict(raw_equipment) if isinstance(raw_equipment, dict) else {},
            global_context=global_context,
        ),
        diagnostics,
    )


def run_config_to_json(run_config: RunConfig) -> str:
    return json.dumps(run_config.to_jsonable(), ensure_ascii=False)
