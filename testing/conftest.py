from __future__ import annotations

import json
import os
from pathlib import Path
import faulthandler
import sys
import threading
import time

import pytest

from testing.cases.metadata import build_case_metadata
from testing.params.registry import default_registry
from testing.runtime.events import emit_event, reset_current_case_nodeid, set_current_case_nodeid


_REGISTRY = default_registry()
_RUN_START_TIMES: dict[str, float] = {}
_RUN_STATUSES: dict[str, str] = {}


def _trace(message: str) -> None:
    print(f"[pytest.trace] {message}", flush=True)


def _trace_threads(stage: str) -> None:
    threads = threading.enumerate()
    _trace(
        f"{stage} threads="
        + ",".join(f"{thread.name}:daemon={thread.daemon}:alive={thread.is_alive()}" for thread in threads)
    )


def pytest_configure(config):
    _trace("pytest_configure enter")
    config.addinivalue_line("markers", "case_type(name): SmartTest case classification.")
    config.addinivalue_line("markers", "requires_params(*param_keys): SmartTest configurable parameter keys.")
    config.addinivalue_line("markers", "requires_param_groups(*group_ids): SmartTest configurable parameter groups.")
    for marker_name in ("smoke", "stress", "performance", "regression", "wifi"):
        config.addinivalue_line("markers", f"{marker_name}: SmartTest marker.")
    _trace("pytest_configure exit")


def pytest_collection_modifyitems(session, config, items):
    _trace(f"pytest_collection_modifyitems count={len(items)}")
    session._smarttest_collected_items = items  # noqa: SLF001


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    _trace(f"runtest_protocol enter nodeid={item.nodeid} next={getattr(nextitem, 'nodeid', '<none>')}")
    try:
        outcome = yield
        _trace(f"runtest_protocol yielded nodeid={item.nodeid} result={outcome.get_result()}")
    finally:
        _trace_threads(f"runtest_protocol finally nodeid={item.nodeid}")
        _trace(f"runtest_protocol exit nodeid={item.nodeid}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    nodeid = item.nodeid
    _trace(f"runtest_setup enter nodeid={nodeid}")
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
        _trace(f"runtest_setup finally nodeid={nodeid}")
        reset_current_case_nodeid(token)
        _trace(f"runtest_setup exit nodeid={nodeid}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    _trace(f"runtest_call enter nodeid={item.nodeid}")
    token = set_current_case_nodeid(item.nodeid)
    try:
        yield
    finally:
        _trace(f"runtest_call finally nodeid={item.nodeid}")
        reset_current_case_nodeid(token)
        _trace(f"runtest_call exit nodeid={item.nodeid}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item):
    _trace(f"runtest_teardown enter nodeid={item.nodeid}")
    token = set_current_case_nodeid(item.nodeid)
    try:
        yield
    finally:
        _trace(f"runtest_teardown finally nodeid={item.nodeid}")
        reset_current_case_nodeid(token)
        _trace(f"runtest_teardown exit nodeid={item.nodeid}")


def pytest_runtest_logreport(report):
    nodeid = report.nodeid
    _trace(
        "runtest_logreport enter "
        f"nodeid={nodeid} when={report.when} outcome={report.outcome} "
        f"failed={report.failed} skipped={report.skipped}"
    )
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
    _trace(
        "runtest_logreport exit "
        f"nodeid={nodeid} when={report.when} status={_RUN_STATUSES.get(nodeid, '<cleared>')}"
    )
    if report.when == "teardown":
        _trace_threads(f"runtest_logreport teardown-complete nodeid={nodeid}")
        faulthandler.dump_traceback_later(10, repeat=True, file=sys.stdout)
        _trace(f"runtest_logreport scheduled traceback watchdog nodeid={nodeid} seconds=10")


def pytest_sessionfinish(session, exitstatus):
    """
    Export collected test items (nodeid + markers + case_type) for the SmartTest UI.

    This is enabled only when SMARTTEST_PYTEST_COLLECT_OUT is set.
    """
    out_path = os.environ.get("SMARTTEST_PYTEST_COLLECT_OUT")
    _trace(
        "pytest_sessionfinish enter "
        f"exitstatus={exitstatus} collect_out={out_path or '<empty>'}"
    )
    faulthandler.cancel_dump_traceback_later()
    _trace_threads("pytest_sessionfinish")
    if not out_path:
        _trace("pytest_sessionfinish exit no collect_out")
        return

    items = getattr(session, "_smarttest_collected_items", [])
    _trace(f"pytest_sessionfinish collected_items={len(items)}")
    payload = []
    for item in items:
        try:
            payload.append(build_case_metadata(item, _REGISTRY))
        except KeyError as exc:
            _trace(f"pytest_sessionfinish metadata_error nodeid={item.nodeid} error={exc}")
            raise pytest.UsageError(f"{item.nodeid}: {exc}") from exc

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _trace(f"pytest_sessionfinish exit wrote={out_path}")


def pytest_unconfigure(config):
    _trace("pytest_unconfigure enter")
    faulthandler.cancel_dump_traceback_later()
    _trace_threads("pytest_unconfigure")
    _trace("pytest_unconfigure exit")
