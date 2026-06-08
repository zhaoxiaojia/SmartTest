from __future__ import annotations

from pathlib import Path

import pytest

from ui import jsonTool

from testing.steps.planner import build_step_plan
from testing.tests.android.stress.test_ac_onoff import _cycle_seconds, _relay_power


def _write_case_parameters(monkeypatch, tmp_path, nodeid: str, parameters: dict[str, object]) -> None:
    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    jsonTool.write_json("test_page_state.json", {"case_parameters": {nodeid: dict(parameters)}})


def test_android_wrapped_case_plan_comes_from_pytest_declaration(monkeypatch, tmp_path) -> None:
    nodeid = "testing/tests/android/common/wifi_bt/test_wifi_onoff.py::test_wifi_onoff_scan_via_android_client"
    _write_case_parameters(
        monkeypatch,
        tmp_path,
        nodeid,
        {"wifi_onoff_scan:cycle_count": 2, "wifi_onoff_scan:ping_target": "192.168.1.1"},
    )
    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid=nodeid,
        prefer_catalog=False,
    )

    assert [step["id"] for step in plan] == [
        "wifi_onoff_scan.prepare",
        "wifi_onoff_scan.trigger",
        "wifi_onoff_scan.cycle.disable",
        "wifi_onoff_scan.cycle.enable",
        "wifi_onoff_scan.cycle.capture_radio_state",
        "wifi_onoff_scan.cycle.ping",
    ]
    assert [step["kind"] for step in plan] == ["setup", "step", "step", "step", "check", "check"]
    assert all(not str(step["definition_id"]).startswith("android.") for step in plan)


def test_config_disabled_check_is_not_shown_in_initial_run_plan(monkeypatch, tmp_path) -> None:
    nodeid = "testing/tests/android/common/wifi_bt/test_wifi_onoff.py::test_wifi_onoff_scan_via_android_client"
    _write_case_parameters(
        monkeypatch,
        tmp_path,
        nodeid,
        {"wifi_onoff_scan:cycle_count": 2, "wifi_onoff_scan:ping_target": ""},
    )
    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid=nodeid,
        prefer_catalog=False,
    )

    assert not any(step["definition_id"] == "network.ping" for step in plan)


def test_relay_ac_onoff_plan_uses_relay_steps_and_dut_checkpoints(monkeypatch, tmp_path) -> None:
    nodeid = "testing/tests/android/stress/test_ac_onoff.py::test_ac_onoff_via_relay"
    _write_case_parameters(
        monkeypatch,
        tmp_path,
        nodeid,
        {
            "ac_onoff:cycle_count": 2,
            "ac_onoff:power_off_sec": 5,
            "ac_onoff:power_off_step_sec": 1,
            "ac_onoff:power_on_wait_sec": 60,
            "ac_onoff:power_on_wait_step_sec": 2,
            "ac_onoff:ping_target": "192.168.50.1",
            "ac_onoff:bt_target": "",
        },
    )
    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid=nodeid,
        prefer_catalog=False,
    )

    assert [step["definition_id"] for step in plan] == [
        "relay.prepare",
        "relay.power_off",
        "relay.power_on",
        "power.wait_resume",
        "network.ping",
    ]
    assert [step["kind"] for step in plan] == ["setup", "step", "step", "step", "check"]


def test_relay_ac_onoff_cycle_seconds_apply_step_and_floor_at_zero() -> None:
    assert [_cycle_seconds(5, 2, index) for index in [1, 2, 3]] == [5, 7, 9]
    assert [_cycle_seconds(5, -3, index) for index in [1, 2, 3]] == [5, 2, 0]
    assert [_cycle_seconds(5, 0.1, index) for index in [1, 2, 3]] == pytest.approx([5, 5.1, 5.2])


def test_relay_ac_onoff_uses_snmp_switch_status_values() -> None:
    class Relay:
        port = ("192.0.2.10", 4)

        def __init__(self) -> None:
            self.calls: list[tuple[str, int, int]] = []

        def switch(self, ip: str, port: int, status: int) -> None:
            self.calls.append((ip, port, status))

    relay = Relay()

    _relay_power(relay, "power_off")
    _relay_power(relay, "power_on")

    assert relay.calls == [
        ("192.0.2.10", 4, 2),
        ("192.0.2.10", 4, 1),
    ]
