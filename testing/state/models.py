from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SelectedCase:
    nodeid: str
    case_type: str = "default"


@dataclass
class TestPageState:
    """
    State is owned by the testing layer.

    - `selected` is ordered (execution order).
    - `selected_files` is ordered (UI selection/list order).
    - `case_parameters` stores per-case user parameters.
    - `case_parameter_options` stores per-case dynamic option lists refreshed from DUTs.
    - `case_type_configs` stores per-type special params shared by cases of that type.
    - `global_context` stores DUT/env/report metadata.
    """

    selected: list[SelectedCase] = field(default_factory=list)
    selected_files: list[str] = field(default_factory=list)
    case_parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    case_parameter_options: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    case_type_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    global_context: dict[str, Any] = field(default_factory=dict)


def to_jsonable(state: TestPageState) -> dict[str, Any]:
    return {
        "selected": [{"nodeid": c.nodeid, "case_type": c.case_type} for c in state.selected],
        "selected_files": state.selected_files,
        "case_parameters": state.case_parameters,
        "case_parameter_options": state.case_parameter_options,
        "case_type_configs": state.case_type_configs,
        "global_context": state.global_context,
    }


def from_jsonable(data: dict[str, Any]) -> TestPageState:
    selected_raw = data.get("selected", [])
    selected = []
    for item in selected_raw:
        if not isinstance(item, dict):
            continue
        nodeid = str(item.get("nodeid", "")).strip()
        if not nodeid:
            continue
        selected.append(SelectedCase(nodeid=nodeid, case_type=str(item.get("case_type", "default"))))
    return TestPageState(
        selected=selected,
        selected_files=[str(item).strip() for item in (data.get("selected_files", []) or []) if str(item).strip()],
        case_parameters={str(k): dict(v) for k, v in (data.get("case_parameters", {}) or {}).items()},
        case_parameter_options=_case_parameter_options_from_json(data.get("case_parameter_options", {}) or {}),
        case_type_configs={str(k): dict(v) for k, v in (data.get("case_type_configs", {}) or {}).items()},
        global_context=dict(data.get("global_context", {}) or {}),
    )


def _case_parameter_options_from_json(raw: Any) -> dict[str, dict[str, list[str]]]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, list[str]]] = {}
    for nodeid, fields in raw.items():
        if not isinstance(fields, dict):
            continue
        field_options: dict[str, list[str]] = {}
        for key, values in fields.items():
            if not isinstance(values, list):
                continue
            field_options[str(key)] = [str(item).strip() for item in values if str(item).strip()]
        result[str(nodeid)] = field_options
    return result
