from __future__ import annotations

import json
import os
from pathlib import Path
import pytest

from testing.cases.metadata import build_case_metadata
from testing.params.registry import default_registry
from testing.test_context import smarttest_context


_REGISTRY = default_registry()


def pytest_configure(config):
    config.addinivalue_line("markers", "case_type(name): SmartTest case classification.")
    config.addinivalue_line("markers", "requires_params(*param_keys): SmartTest configurable parameter keys.")
    config.addinivalue_line("markers", "requires_param_groups(*group_ids): SmartTest configurable parameter groups.")
    config.addinivalue_line("markers", "requires_equipment(*equipment_kinds): SmartTest environment equipment requirements.")
    for marker_name in ("smoke", "stress", "performance", "regression", "wifi"):
        config.addinivalue_line("markers", f"{marker_name}: SmartTest marker.")


def pytest_collection_modifyitems(session, config, items):
    session._smarttest_collected_items = items  # noqa: SLF001


def _is_stress_item(item) -> bool:
    case_type = item.get_closest_marker("case_type")
    if case_type and any(str(arg).strip().lower() == "stress" for arg in case_type.args):
        return True
    return item.get_closest_marker("stress") is not None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    nodeid = item.nodeid
    smarttest_context().start_case_execution(nodeid=nodeid, title=item.name, file=nodeid.split("::", 1)[0])
    token = smarttest_context().cases.set_current_nodeid(nodeid)
    stress_token = smarttest_context().cases.set_current_stress_tolerant(_is_stress_item(item))
    try:
        yield
    finally:
        smarttest_context().cases.reset_current_stress_tolerant(stress_token)
        smarttest_context().cases.reset_current_nodeid(token)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    token = smarttest_context().cases.set_current_nodeid(item.nodeid)
    stress_token = smarttest_context().cases.set_current_stress_tolerant(_is_stress_item(item))
    try:
        yield
    finally:
        smarttest_context().cases.reset_current_stress_tolerant(stress_token)
        smarttest_context().cases.reset_current_nodeid(token)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item):
    token = smarttest_context().cases.set_current_nodeid(item.nodeid)
    stress_token = smarttest_context().cases.set_current_stress_tolerant(_is_stress_item(item))
    try:
        yield
    finally:
        smarttest_context().cases.reset_current_stress_tolerant(stress_token)
        smarttest_context().cases.reset_current_nodeid(token)


def pytest_runtest_logreport(report):
    nodeid = report.nodeid
    smarttest_context().update_case_execution(
        nodeid=nodeid,
        when=str(report.when),
        failed=bool(report.failed),
        skipped=bool(report.skipped),
    )
    if report.when == "teardown":
        smarttest_context().finish_case_execution(nodeid=nodeid)


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
        try:
            payload.append(build_case_metadata(item, _REGISTRY))
        except KeyError as exc:
            raise pytest.UsageError(f"{item.nodeid}: {exc}") from exc

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
