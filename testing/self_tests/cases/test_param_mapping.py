from __future__ import annotations

import sys
from pathlib import Path

from testing.cases.discovery import discover_pytest_cases
from testing.params.registry import default_registry


ROOT_DIR = Path(__file__).resolve().parents[3]


def test_default_registry_resolves_group_members():
    registry = default_registry()

    assert registry.resolve_param_keys(group_ids=["dut_identity"]) == [
        "dut",
    ]


def test_default_registry_rejects_unknown_group():
    registry = default_registry()

    try:
        registry.resolve_param_keys(group_ids=["missing_group"])
    except KeyError as exc:
        assert "missing_group" in str(exc)
    else:
        raise AssertionError("Expected resolve_param_keys() to reject an unknown group.")


def test_discovery_exports_only_implemented_android_entries():
    cases = discover_pytest_cases(
        root_dir=ROOT_DIR,
        test_paths=[
            ROOT_DIR / "testing" / "tests" / "android" / "common" / "system",
            ROOT_DIR / "testing" / "tests" / "android" / "common" / "wifi_bt",
        ],
        python_executable=sys.executable,
    )

    cases_by_nodeid = {case.nodeid: case for case in cases}
    assert sorted(cases_by_nodeid) == [
        "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client",
        "testing/tests/android/common/system/test_auto_suspend.py::test_auto_suspend_via_android_client",
        "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client",
        "testing/tests/android/common/wifi_bt/test_bt_onoff.py::test_bt_onoff_scan_via_android_client",
        "testing/tests/android/common/wifi_bt/test_wifi_onoff.py::test_wifi_onoff_scan_via_android_client",
    ]

    emmc_case = cases_by_nodeid["testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"]
    assert emmc_case.required_param_groups == []
    assert emmc_case.required_params == [
        "emmc_rw:loop_count",
        "emmc_rw:source_profile",
        "emmc_rw:source_size_kb",
        "emmc_rw:min_free_kb",
        "emmc_rw:work_dir",
    ]

    reboot_case = cases_by_nodeid["testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"]
    assert reboot_case.required_param_groups == []
    assert reboot_case.required_params == [
        "auto_reboot:cycle_count",
        "auto_reboot:interval_sec",
        "auto_reboot:ping_target",
        "auto_reboot:bt_target",
    ]

    suspend_case = cases_by_nodeid["testing/tests/android/common/system/test_auto_suspend.py::test_auto_suspend_via_android_client"]
    assert suspend_case.required_param_groups == []
    assert suspend_case.required_params == [
        "auto_suspend:cycle_count",
        "auto_suspend:interval_sec",
        "auto_suspend:ping_target",
        "auto_suspend:bt_target",
    ]

    wifi_onoff_case = cases_by_nodeid["testing/tests/android/common/wifi_bt/test_wifi_onoff.py::test_wifi_onoff_scan_via_android_client"]
    assert wifi_onoff_case.required_param_groups == []
    assert wifi_onoff_case.required_params == [
        "wifi_onoff_scan:cycle_count",
        "wifi_onoff_scan:ping_target",
    ]

    bt_onoff_case = cases_by_nodeid["testing/tests/android/common/wifi_bt/test_bt_onoff.py::test_bt_onoff_scan_via_android_client"]
    assert bt_onoff_case.required_param_groups == []
    assert bt_onoff_case.required_params == [
        "bt_onoff_scan:cycle_count",
        "bt_onoff_scan:bt_target",
    ]


def test_default_registry_includes_android_client_emmc_params():
    registry = default_registry()

    assert registry.get_param("emmc_rw:loop_count") is not None
    assert registry.get_param("emmc_rw:source_profile") is not None
    assert registry.get_param("emmc_rw:source_size_kb") is not None
    assert registry.get_param("emmc_rw:min_free_kb") is not None
    assert registry.get_param("emmc_rw:work_dir") is not None
    assert registry.get_param("auto_reboot:cycle_count") is not None
    assert registry.get_param("auto_reboot:interval_sec") is not None
    assert registry.get_param("auto_reboot:ping_target") is not None
    assert registry.get_param("auto_reboot:bt_target") is not None
    assert registry.get_param("auto_suspend:cycle_count") is not None
    assert registry.get_param("auto_suspend:interval_sec") is not None
    assert registry.get_param("auto_suspend:ping_target") is not None
    assert registry.get_param("auto_suspend:bt_target") is not None
    assert registry.get_param("wifi_onoff_scan:cycle_count") is not None
    assert registry.get_param("wifi_onoff_scan:ping_target") is not None
    assert registry.get_param("bt_onoff_scan:cycle_count") is not None
    assert registry.get_param("bt_onoff_scan:bt_target") is not None


def test_default_registry_uses_fixed_bluetooth_target_list():
    registry = default_registry()

    reboot_param = registry.get_param("auto_reboot:bt_target")
    suspend_param = registry.get_param("auto_suspend:bt_target")
    bt_onoff_param = registry.get_param("bt_onoff_scan:bt_target")

    assert reboot_param is not None
    assert suspend_param is not None
    assert bt_onoff_param is not None
    assert reboot_param.enum_values == [
        "None",
        "小米小钢炮蓝牙音箱 [74:A3:4A:13:3E:DA]",
        "HUAWEI Sound Joy-09524 [78:04:E3:54:3E:91]",
        "EDIFIER M380 [F4:4E:FD:44:A5:89]",
        "SRS-XB10 [F8:DF:15:22:4A:CC]",
        "iChocolate Mini [A0:E9:DB:23:17:58]",
        "JBL Charge 3 [04:21:44:AB:D6:63]",
    ]
    assert suspend_param.enum_values == reboot_param.enum_values
    assert bt_onoff_param.enum_values == reboot_param.enum_values
