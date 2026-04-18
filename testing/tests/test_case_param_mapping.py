from __future__ import annotations

import sys
from pathlib import Path

from testing.cases.discovery import discover_pytest_cases
from testing.params.registry import default_registry


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_default_registry_resolves_group_members():
    registry = default_registry()

    assert registry.resolve_param_keys(group_ids=["dut_identity"]) == [
        "dut_model",
        "dut_sn",
        "fw_version",
    ]
    assert registry.resolve_param_keys(group_ids=["stress_runtime"]) == [
        "duration_s",
        "concurrency",
        "warmup_s",
    ]


def test_default_registry_rejects_unknown_group():
    registry = default_registry()

    try:
        registry.resolve_param_keys(group_ids=["missing_group"])
    except KeyError as exc:
        assert "missing_group" in str(exc)
    else:
        raise AssertionError("Expected resolve_param_keys() to reject an unknown group.")


def test_discovery_exports_required_params_and_empty_cases():
    cases = discover_pytest_cases(
        root_dir=ROOT_DIR,
        test_paths=[
            ROOT_DIR / "testing" / "tests" / "IPTV" / "system" / "test_system_cases.py",
            ROOT_DIR / "testing" / "tests" / "IPTV" / "wifi_bt" / "test_wifi_bt_cases.py",
        ],
        python_executable=sys.executable,
    )

    cases_by_nodeid = {case.nodeid: case for case in cases}

    emmc_case = cases_by_nodeid["testing/tests/IPTV/system/test_system_cases.py::test_emmc_rw_via_mobile_android"]
    assert emmc_case.required_param_groups == []
    assert emmc_case.required_params == [
        "emmc_rw:loop_count",
        "emmc_rw:source_profile",
        "emmc_rw:source_size_kb",
        "emmc_rw:min_free_kb",
        "emmc_rw:work_dir",
    ]

    reboot_case = cases_by_nodeid["testing/tests/IPTV/system/test_system_cases.py::test_auto_reboot_via_mobile_android"]
    assert reboot_case.required_param_groups == []
    assert reboot_case.required_params == [
        "auto_reboot:cycle_count",
        "auto_reboot:interval_sec",
    ]

    wifi_onoff_case = cases_by_nodeid["testing/tests/IPTV/wifi_bt/test_wifi_bt_cases.py::test_wifi_onoff_scan_via_mobile_android"]
    assert wifi_onoff_case.required_param_groups == []
    assert wifi_onoff_case.required_params == ["wifi_onoff_scan:cycle_count"]

    paramless_case = cases_by_nodeid["testing/tests/IPTV/system/test_system_cases.py::test_ddr_stress_via_mobile_android"]
    assert paramless_case.required_param_groups == []
    assert paramless_case.required_params == []
