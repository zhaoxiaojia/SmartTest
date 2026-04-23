from __future__ import annotations

import json
import os
from pathlib import Path
import time

import pytest

from testing.params.binding import BindingTargetKind, CaseParamBinding
from testing.params.registry import default_registry
from testing.runtime.events import emit_event, reset_current_case_nodeid, set_current_case_nodeid


_REGISTRY = default_registry()
_RUN_START_TIMES: dict[str, float] = {}
_RUN_STATUSES: dict[str, str] = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "case_type(name): SmartTest case classification.")
    config.addinivalue_line("markers", "requires_params(*param_keys): SmartTest configurable parameter keys.")
    config.addinivalue_line("markers", "requires_param_groups(*group_ids): SmartTest configurable parameter groups.")
    for marker_name in ("smoke", "stress", "performance", "regression", "wifi"):
        config.addinivalue_line("markers", f"{marker_name}: SmartTest marker.")


def _infer_case_type(item) -> str:
    case_type_marker = item.get_closest_marker("case_type")
    if case_type_marker and case_type_marker.args:
        value = str(case_type_marker.args[0]).strip()
        if value:
            return value

    # Fallback: allow simple marker names as types, e.g. @pytest.mark.stress
    marker_names = {m.name for m in item.iter_markers()}
    for candidate in ("stress", "performance", "regression", "smoke"):
        if candidate in marker_names:
            return candidate

    return "default"


def _marker_args(item, marker_name: str) -> list[str]:
    values: list[str] = []
    for marker in item.iter_markers(name=marker_name):
        for value in marker.args:
            normalized = str(value).strip()
            if normalized:
                values.append(normalized)
    return values


def _build_case_param_binding(item) -> CaseParamBinding:
    return CaseParamBinding(
        target_kind=BindingTargetKind.CASE,
        target_id=item.nodeid,
        param_keys=_marker_args(item, "requires_params"),
        group_ids=_marker_args(item, "requires_param_groups"),
    )


def _required_params_for_item(item) -> tuple[CaseParamBinding, list[str]]:
    binding = _build_case_param_binding(item)
    try:
        required_params = _REGISTRY.resolve_binding(binding)
    except KeyError as exc:
        raise pytest.UsageError(f"{item.nodeid}: {exc}") from exc
    return binding, required_params


def pytest_collection_modifyitems(session, config, items):
    session._smarttest_collected_items = items  # noqa: SLF001


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    nodeid = item.nodeid
    _RUN_START_TIMES[nodeid] = time.monotonic()
    _RUN_STATUSES[nodeid] = "running"
    emit_event(
        "case_started",
        case_nodeid=nodeid,
        title=item.name,
        file=nodeid.split("::", 1)[0],
    )
    token = set_current_case_nodeid(nodeid)
    try:
        yield
    finally:
        reset_current_case_nodeid(token)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    token = set_current_case_nodeid(item.nodeid)
    try:
        yield
    finally:
        reset_current_case_nodeid(token)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item):
    token = set_current_case_nodeid(item.nodeid)
    try:
        yield
    finally:
        reset_current_case_nodeid(token)


def pytest_runtest_logreport(report):
    nodeid = report.nodeid
    if report.when == "call":
        if report.failed:
            _RUN_STATUSES[nodeid] = "failed"
        elif report.skipped:
            _RUN_STATUSES[nodeid] = "skipped"
        else:
            _RUN_STATUSES[nodeid] = "passed"
    elif report.when == "setup" and report.failed:
        _RUN_STATUSES[nodeid] = "failed"
    elif report.when == "teardown":
        status = _RUN_STATUSES.get(nodeid, "passed")
        duration_ms = int((time.monotonic() - _RUN_START_TIMES.get(nodeid, time.monotonic())) * 1000)
        emit_event(
            "case_finished",
            case_nodeid=nodeid,
            status=status,
            duration_ms=duration_ms,
        )
        _RUN_START_TIMES.pop(nodeid, None)
        _RUN_STATUSES.pop(nodeid, None)


def pytest_sessionfinish(session, exitstatus):
    """
    Export collected test items (nodeid + markers + case_type) for the SmartTest UI.

    This is enabled only when SMARTTEST_PYTEST_COLLECT_OUT is set.
    """
    out_path = os.environ.get("SMARTTEST_PYTEST_COLLECT_OUT")
    if not out_path:
        return

    items = getattr(session, "_smarttest_collected_items", [])
    payload = []
    for item in items:
        markers = sorted({m.name for m in item.iter_markers()})
        nodeid = item.nodeid
        file_part = nodeid.split("::", 1)[0]
        name = nodeid.split("::")[-1] if "::" in nodeid else nodeid
        binding, required_params = _required_params_for_item(item)
        payload.append(
            {
                "nodeid": nodeid,
                "file": file_part,
                "name": name,
                "markers": markers,
                "case_type": _infer_case_type(item),
                "required_params": required_params,
                "required_param_groups": list(binding.group_ids),
            }
        )

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
