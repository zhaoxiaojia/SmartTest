from __future__ import annotations

from pathlib import Path

from testing.steps import build_step_plan


def test_android_wrapped_case_plan_comes_from_pytest_declaration() -> None:
    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid="testing/tests/android/common/wifi_bt/test_wifi_onoff.py::test_wifi_onoff_scan_via_android_client",
        case_config={"wifi_onoff_scan:cycle_count": 2, "wifi_onoff_scan:ping_target": "192.168.1.1"},
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


def test_config_disabled_check_is_not_shown_in_initial_run_plan() -> None:
    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid="testing/tests/android/common/wifi_bt/test_wifi_onoff.py::test_wifi_onoff_scan_via_android_client",
        case_config={"wifi_onoff_scan:cycle_count": 2, "wifi_onoff_scan:ping_target": ""},
        prefer_catalog=False,
    )

    assert not any(step["definition_id"] == "network.ping" for step in plan)
