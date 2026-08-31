from __future__ import annotations

import ipaddress
import re

import pytest

from core.testing.runtime.config import current_dut_serial
from core.testing.runtime.steps import step, step_log
from core.testing.test_context import smarttest_context
from core.testing.tool.dut_tool.duts.android import android
from core.testing.tool.dut_tool.features.iptv_middle_screen import (
    TARGET_SOURCE_IDS,
    cleanup_middle_screen_case,
    execute_middle_screen_case,
    prepare_middle_screen_case,
    run_middle_screen_action,
)


def build_middle_screen_plan(source_case):
    return {
        "case_id": f"iptv_middle_screen_{source_case.source_id:03d}",
        "steps": [
            {
                "id": f"iptv.{source_case.source_id:03d}.step.{index}",
                "title": title,
                "kind": "check" if index == 5 else ("setup" if index < 3 else ("cleanup" if index == 6 else "action")),
                "definition_id": f"iptv.{source_case.source_id:03d}.step.{index}",
                "expected": source_case.checkpoints[0].expected if index == 5 else "步骤完成并记录结构化证据。",
            }
            for index, title in enumerate(source_case.steps, 1)
        ],
    }


def run_middle_screen_case(request, source_case) -> None:
    serial = current_dut_serial()
    if not serial:
        pytest.fail("Select a DUT before running an IPTV middle-screen case.")
    params = smarttest_context().params.case_values(request.node.nodeid)
    source_evidence = {
        "source_file": source_case.source_file,
        "source_sheet": source_case.source_sheet,
        "source_row": source_case.source_row,
        "manual_prerequisites": source_case.pre_actions,
        "manual_boundaries": source_case.manual_boundaries,
        "source_id": source_case.source_id,
        "case_nodeid": request.node.nodeid,
        "coverage_level": source_case.coverage_level,
        "unverified_items": source_case.unverified_items,
    }
    summary = {
        "headline": source_case.title,
        "source_id": source_case.source_id,
        "source": f"{source_case.source_file} / {source_case.source_sheet} / row {source_case.source_row}",
        "dut_serial": serial,
        "parameters": dict(params),
        "coverage_level": source_case.coverage_level,
        "unverified_items": list(source_case.unverified_items),
        "checkpoint_id": source_case.checkpoints[0].definition_id,
        "checkpoint_expected": source_case.checkpoints[0].expected,
        "checkpoint_rule": source_case.checkpoints[0].pass_rule,
        "manual_prerequisites": list(source_case.equipment_boundaries),
    }
    if source_case.coverage_level == "software_partial":
        summary["coverage_notice"] = "本结果仅代表软件播放状态检查通过，不代表原始用例完整通过。"
    smarttest_context().set_case_summary(request.node.nodeid, summary)
    dut = android(serialnumber=serial)
    if source_case.source_id not in TARGET_SOURCE_IDS:
        with _runtime_step(source_case, 1, actual={}):
            execute_middle_screen_case(source_case, dut, params, serial=serial)
        return
    with _runtime_step(source_case, 1, actual={"parameters": dict(params)}):
        step_log("iptv.middle_screen.source", extra=source_evidence)
    with _runtime_step(source_case, 2, actual={}) as preparation_actual:
        state = prepare_middle_screen_case(source_case, dut, params, serial=serial)
        preparation_actual.update(_reportable_state(state))
    facts: dict = {}
    cleanup_result: dict = {}
    try:
        with _runtime_step(source_case, 3, actual=facts):
            facts.update(run_middle_screen_action(source_case, dut, params, serial=serial))
        with _runtime_step(source_case, 4, actual=facts):
            step_log("iptv.middle_screen.facts", extra={"source_id": source_case.source_id, "facts": facts})
        with _runtime_step(source_case, 5, actual=facts):
            assert_middle_screen_objective(source_case, facts)
    finally:
        with _runtime_step(source_case, 6, actual=cleanup_result):
            cleanup_result.update(cleanup_middle_screen_case(source_case, dut, state))
            assert cleanup_result.get("restored") is True, f"Cleanup failed: {cleanup_result}"
    with _runtime_step(source_case, 7, actual={"coverage_level": source_case.coverage_level}):
        step_log("iptv.middle_screen.coverage", extra={
            "coverage_level": source_case.coverage_level,
            "unverified_items": source_case.unverified_items,
        })


def _runtime_step(source_case, index: int, *, actual: dict):
    kind = "check" if index == 5 else ("setup" if index < 3 else ("cleanup" if index == 6 else "action"))
    return step(
        source_case.steps[index - 1],
        kind=kind,
        definition_id=f"iptv.{source_case.source_id:03d}.step.{index}",
        expected=source_case.checkpoints[0].expected if index == 5 else "步骤完成并记录结构化证据。",
        actual=actual,
        step_id=f"iptv.{source_case.source_id:03d}.step.{index}",
    )


def _reportable_state(state: dict) -> dict:
    return {key: (str(value) if key == "cpu_snapshot" else value) for key, value in state.items()}


def assert_middle_screen_objective(case, facts: dict) -> None:
    source_id = case.source_id
    if source_id == 4:
        matcher = facts["matcher"]
        assert matcher and matcher in facts["output"], f"USB matcher not found: {matcher!r}"
    elif source_id == 10:
        addresses = facts["addresses"]
        assert any(not ipaddress.ip_address(value).is_loopback for values in addresses.values() for value in values)
        assert facts["expected_speed_mbps"] > 0, "expected_speed_mbps must be configured"
        assert facts["actual_speed_mbps"] == facts["expected_speed_mbps"]
    elif source_id == 18:
        assert facts["frequencies"]
        assert all(sample["actual"] == sample["expected"] for sample in facts["samples"])
    elif source_id == 20:
        assert re.search(r"\bhs400\b", facts["mmc_output"], re.I)
    elif source_id == 21:
        assert re.search(r"\bwlan0\b", facts["interface_output"])
        assert len(facts["bands"]) == 2
        assert all(item["ssid"] and item["scanned"] and item["connected"] for item in facts["bands"])
        assert all(any(item["addresses"].values()) for item in facts["bands"])
    elif source_id == 29:
        assert facts["temperature_millicelsius"] is not None
    elif source_id in (31, 32):
        assert facts["adb_ready"]
        assert facts["network_serial"] == (source_id == 32)
    elif source_id == 33:
        assert facts["dimensions"] is not None
        width, height = facts["dimensions"]
        assert width >= 1920 and height >= 1080
    elif source_id in (49, 52, 53, 54, 55):
        addresses = facts["addresses"]
        if source_id in (49, 52, 54):
            assert any(not ipaddress.ip_address(value).is_loopback and not ipaddress.ip_address(value).is_link_local for value in addresses["ipv4"])
            assert facts["ipv4_reachable"]
        if source_id in (49, 53, 55):
            assert any(ipaddress.ip_address(value).is_global for value in addresses["ipv6"])
            assert facts["ipv6_reachable"]
    else:
        assert facts["sources"], "No media source configured"
        assert len(facts["results"]) == len(facts["sources"])
        failures = [result for result in facts["results"] if not result["playing"]]
        assert not failures, f"Media playback checkpoint failed: {failures}"
