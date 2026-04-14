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
    - `case_configs` stores per-case overrides.
    - `case_type_configs` stores per-type special params shared by cases of that type.
    - `global_context` stores DUT/env/report metadata.
    """

    selected: list[SelectedCase] = field(default_factory=list)
    case_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    case_type_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    global_context: dict[str, Any] = field(default_factory=dict)


def to_jsonable(state: TestPageState) -> dict[str, Any]:
    return {
        "selected": [{"nodeid": c.nodeid, "case_type": c.case_type} for c in state.selected],
        "case_configs": state.case_configs,
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
        case_configs={str(k): dict(v) for k, v in (data.get("case_configs", {}) or {}).items()},
        case_type_configs={str(k): dict(v) for k, v in (data.get("case_type_configs", {}) or {}).items()},
        global_context=dict(data.get("global_context", {}) or {}),
    )

