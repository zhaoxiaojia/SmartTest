from __future__ import annotations

from typing import Any

from testing.params.binding import BindingTargetKind, CaseParamBinding
from testing.params.registry import SchemaRegistry


def infer_case_type(item: Any) -> str:
    case_type_marker = item.get_closest_marker("case_type")
    if case_type_marker and case_type_marker.args:
        value = str(case_type_marker.args[0]).strip()
        if value:
            return value

    marker_names = {m.name for m in item.iter_markers()}
    for candidate in ("stress", "performance", "regression", "smoke"):
        if candidate in marker_names:
            return candidate

    return "default"


def marker_args(item: Any, marker_name: str) -> list[str]:
    values: list[str] = []
    for marker in item.iter_markers(name=marker_name):
        for value in marker.args:
            normalized = str(value).strip()
            if normalized:
                values.append(normalized)
    return values


def build_case_param_binding(item: Any) -> CaseParamBinding:
    return CaseParamBinding(
        target_kind=BindingTargetKind.CASE,
        target_id=item.nodeid,
        param_keys=marker_args(item, "requires_params"),
        group_ids=marker_args(item, "requires_param_groups"),
    )


def build_case_metadata(item: Any, registry: SchemaRegistry) -> dict[str, object]:
    nodeid = item.nodeid
    binding = build_case_param_binding(item)
    required_params = registry.resolve_binding(binding)
    return {
        "nodeid": nodeid,
        "file": nodeid.split("::", 1)[0],
        "name": nodeid.split("::")[-1] if "::" in nodeid else nodeid,
        "markers": sorted({m.name for m in item.iter_markers()}),
        "case_type": infer_case_type(item),
        "required_params": required_params,
        "required_param_groups": list(binding.group_ids),
    }
