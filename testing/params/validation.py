from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from testing.cases.catalog import load_runtime_test_catalog
from testing.params.adb_devices import list_adb_devices
from testing.params.options import normalize_option_values
from testing.params.registry import SchemaRegistry, default_registry
from testing.params.contracts import required_param_keys
from testing.params.schema import ParamField, ParamValueType
from testing.runner.config import resolve_dut_serial
from testing.state.models import SelectedCase, TestPageState
from testing.test_context import smarttest_context


DeviceLister = Callable[[], list[str]]
_UNSET = object()


@dataclass(frozen=True)
class RunValidationIssue:
    code: str
    nodeid: str = ""
    case_name: str = ""
    param_key: str = ""


def validate_run_request(
    *,
    root_dir: Path,
    state: TestPageState,
    catalog: list[dict[str, Any]] | None = None,
    registry: SchemaRegistry | None = None,
    device_lister: DeviceLister | None = None,
    resolved_dut_serial: str | None | object = _UNSET,
) -> list[RunValidationIssue]:
    active_registry = registry or default_registry()
    cases = catalog if catalog is not None else load_runtime_test_catalog(root_dir=root_dir)
    selected_cases = _selected_case_rows(state.selected, cases)
    issues: list[RunValidationIssue] = []

    if any(_case_requires_dut(case, active_registry) for _, case in selected_cases):
        if resolved_dut_serial is _UNSET:
            smarttest_context().params.bind_ui_state(state)
            selected_dut = smarttest_context().params.selected_dut()
            resolved_dut = resolve_dut_serial(selected_dut, device_lister=device_lister or list_adb_devices)
        else:
            resolved_dut = str(resolved_dut_serial or "").strip()
        if not resolved_dut:
            issues.append(
                RunValidationIssue(
                    code="missing_dut",
                    param_key="dut",
                )
            )

    for selected, case in selected_cases:
        case_param_keys = {str(param_key) for param_key in list(case.get("required_params", []))}
        for param_key in required_param_keys(case):
            if param_key not in case_param_keys:
                continue
            field = active_registry.get_param(str(param_key))
            if field is None:
                continue
            smarttest_context().params.bind_ui_state(state)
            value = smarttest_context().params.case_display_value(case, field.key)
            if _is_missing_required_value(field, value) or _is_invalid_required_dynamic_value(
                state=state,
                selected=selected,
                case=case,
                field=field,
                value=value,
            ):
                issues.append(
                    RunValidationIssue(
                        code="missing_required_param",
                        nodeid=selected.nodeid,
                        case_name=str(case.get("name", "") or selected.nodeid),
                        param_key=field.key,
                    )
                )
    return issues


def _selected_case_rows(
    selected: list[SelectedCase],
    catalog: list[dict[str, Any]],
) -> list[tuple[SelectedCase, dict[str, Any]]]:
    by_nodeid = {str(case.get("nodeid", "") or ""): dict(case) for case in catalog}
    by_android_id = {
        str(case.get("android_case_id", "") or ""): dict(case)
        for case in catalog
        if str(case.get("android_case_id", "") or "")
    }
    rows: list[tuple[SelectedCase, dict[str, Any]]] = []
    for item in selected:
        nodeid = str(item.nodeid or "").strip()
        case = by_nodeid.get(nodeid)
        if case is None and nodeid.startswith("android://"):
            case = by_android_id.get(nodeid[len("android://") :].strip())
        if case is None:
            case = {
                "nodeid": nodeid,
                "file": nodeid.split("::", 1)[0],
                "name": nodeid.rsplit("::", 1)[-1] if "::" in nodeid else nodeid,
                "case_type": item.case_type,
                "required_params": [],
                "required_equipment": [],
                "android_case_id": "",
            }
        rows.append((item, case))
    return rows


def _case_requires_dut(case: Mapping[str, Any], registry: SchemaRegistry) -> bool:
    file_path = str(case.get("file", "") or "").replace("\\", "/")
    if file_path.startswith("testing/tests/android/"):
        return True
    if str(case.get("android_case_id", "") or "").strip():
        return True
    for param_key in list(case.get("required_params", [])):
        field = registry.get_param(str(param_key))
        if field is not None and str(field.options_source or "").strip():
            return True
    return False


def _is_multi_enum_field(field: ParamField) -> bool:
    field_type = field.type.value if hasattr(field.type, "value") else field.type
    return field_type == ParamValueType.MULTI_ENUM.value


def _is_missing_required_value(field: ParamField, value: Any) -> bool:
    if _is_multi_enum_field(field):
        return len(normalize_option_values(value)) == 0
    if value is None:
        return True
    if isinstance(value, str):
        normalized = value.strip()
        return not normalized or normalized.lower() == "none"
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _is_invalid_required_dynamic_value(
    *,
    state: TestPageState,
    selected: SelectedCase,
    case: Mapping[str, Any],
    field: ParamField,
    value: Any,
) -> bool:
    if not str(field.options_source or "").strip():
        return False
    smarttest_context().params.bind_ui_state(state)
    options = normalize_option_values(
        smarttest_context().params.dynamic_options(
            selected_nodeid=selected.nodeid,
            case_nodeid=str(case.get("nodeid", "") or ""),
            key=field.key,
        )
    )
    if not options:
        return True
    if _is_multi_enum_field(field):
        return any(item not in options for item in normalize_option_values(value))
    return str(value or "").strip() not in options
