from __future__ import annotations

from pathlib import Path

from testing.steps import build_step_plan


def test_android_mirrored_plan_includes_pytest_declared_steps_not_catalog_checks() -> None:
    nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"

    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid=nodeid,
        case_config={
            "emmc_rw:loop_count": 1,
            "emmc_rw:source_profile": "random1",
        },
    )

    assert [step["id"] for step in plan] == [
        "prepare_runner",
        "storage.emmc.prepare_request",
        "storage.emmc.trigger_execution",
        "emmc_rw.cycle.copy_file",
        "emmc_rw.cycle.read_file",
        "emmc_rw.cycle.cmp_file",
    ]
    assert [step["kind"] for step in plan] == ["setup", "step", "step", "step", "step", "check"]
    assert plan[0]["definition_id"] == "smarttest.runner.prepare"
    assert plan[1]["definition_id"] == "storage.emmc.prepare_request"
    assert plan[2]["definition_id"] == "storage.emmc.trigger_execution"
    assert plan[3]["definition_id"] == "storage.emmc.copy_file"
    assert plan[4]["definition_id"] == "storage.emmc.read_file"
    assert plan[5]["definition_id"] == "storage.emmc.cmp_file"
    assert not any(step["definition_id"] == "emmc_rw.execute" for step in plan)
    assert not any(str(step["definition_id"]).startswith("emmc_rw.check.") for step in plan)


def test_declared_plan_applies_selected_config_to_optional_checks() -> None:
    nodeid = "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"

    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid=nodeid,
        case_config={
            "auto_reboot:cycle_count": 1,
            "auto_reboot:interval_sec": 30,
            "auto_reboot:ping_target": "192.168.0.1",
            "auto_reboot:bt_target": "11:22:33:44:55:66",
        },
        prefer_catalog=False,
    )

    assert [step["definition_id"] for step in plan] == [
        "smarttest.runner.prepare",
        "power.auto_reboot.prepare",
        "power.reboot",
        "power.wait_resume",
        "power.wait_interval",
        "power.capture_radio_state",
        "network.ping",
        "bluetooth.verify_target",
    ]
    assert any(step["title"] == "Cycle: wait interval 30s" for step in plan)
    assert any(step["title"] == "Cycle: ping 192.168.0.1" for step in plan)


def test_declared_plan_omits_config_disabled_optional_checks() -> None:
    nodeid = "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"

    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid=nodeid,
        case_config={
            "auto_reboot:cycle_count": 1,
            "auto_reboot:interval_sec": 30,
            "auto_reboot:ping_target": "",
            "auto_reboot:bt_target": "",
        },
        prefer_catalog=False,
    )

    definition_ids = [step["definition_id"] for step in plan]
    assert "network.ping" not in definition_ids
    assert "bluetooth.verify_target" not in definition_ids
    assert "power.capture_radio_state" in definition_ids


def test_catalog_plan_omits_config_disabled_optional_checks() -> None:
    nodeid = "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"

    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid=nodeid,
        case_config={
            "auto_reboot:cycle_count": 1,
            "auto_reboot:interval_sec": 30,
            "auto_reboot:ping_target": "",
            "auto_reboot:bt_target": "",
        },
    )

    definition_ids = [step["definition_id"] for step in plan]
    assert "network.ping" not in definition_ids
    assert "bluetooth.verify_target" not in definition_ids
    assert "power.capture_radio_state" in definition_ids


def test_declared_plan_lets_check_definition_disable_none_option() -> None:
    nodeid = "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"

    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid=nodeid,
        case_config={
            "auto_reboot:cycle_count": 1,
            "auto_reboot:interval_sec": 30,
            "auto_reboot:ping_target": "",
            "auto_reboot:bt_target": "None",
        },
        prefer_catalog=False,
    )

    definition_ids = [step["definition_id"] for step in plan]
    assert "network.ping" not in definition_ids
    assert "bluetooth.verify_target" not in definition_ids
    assert "power.capture_radio_state" in definition_ids


def test_wifi_bt_file_selects_declared_plan_by_android_case_id() -> None:
    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid="testing/tests/android/common/wifi_bt/test_wifi_onoff.py::test_wifi_onoff_scan_via_android_client",
        case_config={
            "wifi_onoff_scan:cycle_count": 2,
            "wifi_onoff_scan:ping_target": "192.168.0.1",
        },
        prefer_catalog=False,
    )

    assert [step["definition_id"] for step in plan] == [
        "smarttest.runner.prepare",
        "radio.wifi.disable",
        "radio.wifi.enable",
        "power.capture_radio_state",
        "network.required_ping",
    ]
    assert any(step["title"] == "Cycle: ping 192.168.0.1" for step in plan)


def test_bt_onoff_declared_plan_keeps_required_target_check() -> None:
    plan = build_step_plan(
        root_dir=Path.cwd(),
        nodeid="testing/tests/android/common/wifi_bt/test_bt_onoff.py::test_bt_onoff_scan_via_android_client",
        case_config={
            "bt_onoff_scan:cycle_count": 2,
            "bt_onoff_scan:bt_target": "None",
        },
        prefer_catalog=False,
    )

    definition_ids = [step["definition_id"] for step in plan]
    assert definition_ids == [
        "smarttest.runner.prepare",
        "radio.bluetooth.disable",
        "radio.bluetooth.enable",
        "power.capture_radio_state",
        "bluetooth.required_verify_target",
    ]
