from __future__ import annotations

from testing.params.android_catalog import load_android_catalog_cases
from testing.params.registry import default_registry
from testing.params.schema import ParamValueType

CPU_FREQUENCY_PARAM_KEY = "cpu_frequency:frequencies"


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


def test_android_catalog_exports_frontend_case_contracts():
    cases_by_id = {case.case_id: case for case in load_android_catalog_cases()}
    assert sorted(cases_by_id) == [
        "auto_reboot",
        "auto_suspend",
        "bt_onoff_scan",
        "emmc_rw",
        "wifi_onoff_scan",
    ]

    emmc_case = cases_by_id["emmc_rw"]
    assert [f"{param.case_id}:{param.param_id}" for param in emmc_case.params] == [
        "emmc_rw:loop_count",
        "emmc_rw:source_profile",
        "emmc_rw:source_size_kb",
        "emmc_rw:min_free_kb",
        "emmc_rw:work_dir",
    ]

    reboot_case = cases_by_id["auto_reboot"]
    assert [f"{param.case_id}:{param.param_id}" for param in reboot_case.params] == [
        "auto_reboot:cycle_count",
        "auto_reboot:interval_sec",
        "auto_reboot:ping_target",
        "auto_reboot:bt_target",
    ]

    suspend_case = cases_by_id["auto_suspend"]
    assert [f"{param.case_id}:{param.param_id}" for param in suspend_case.params] == [
        "auto_suspend:cycle_count",
        "auto_suspend:interval_sec",
        "auto_suspend:ping_target",
        "auto_suspend:bt_target",
    ]

    wifi_onoff_case = cases_by_id["wifi_onoff_scan"]
    assert [f"{param.case_id}:{param.param_id}" for param in wifi_onoff_case.params] == [
        "wifi_onoff_scan:cycle_count",
        "wifi_onoff_scan:ping_target",
    ]

    bt_onoff_case = cases_by_id["bt_onoff_scan"]
    assert [f"{param.case_id}:{param.param_id}" for param in bt_onoff_case.params] == [
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
    assert registry.get_param("ac_onoff:cycle_count") is not None
    assert registry.get_param("ac_onoff:power_off_sec") is not None
    assert registry.get_param("ac_onoff:power_off_step_sec") is not None
    assert registry.get_param("ac_onoff:power_on_wait_sec") is not None
    assert registry.get_param("ac_onoff:power_on_wait_step_sec") is not None
    assert registry.get_param("ac_onoff:ping_target") is not None
    assert registry.get_param("ac_onoff:bt_target") is not None
    assert registry.get_param("local_playback_stress:media_dir") is not None
    assert registry.get_param("local_playback_stress:media_files") is not None
    assert registry.get_param("local_playback_stress:actions") is not None
    assert registry.get_param("local_playback_stress:loop_count") is not None
    assert registry.get_param("local_playback_stress:random_playback") is not None
    assert registry.get_param("local_playback_stress:action_interval_sec") is not None
    assert registry.get_param("local_playback_stress:start_wait_sec") is not None
    assert registry.get_param("ac_onoff:power_off_step_sec").type == ParamValueType.FLOAT
    assert registry.get_param("ac_onoff:power_on_wait_step_sec").type == ParamValueType.FLOAT
    cpu_frequency_param = registry.get_param(CPU_FREQUENCY_PARAM_KEY)
    assert cpu_frequency_param is not None
    assert cpu_frequency_param.type == ParamValueType.MULTI_ENUM
    assert cpu_frequency_param.options_source == "testing.actions.cpu_frequency:list_cpu_frequency_options"
    media_files_param = registry.get_param("local_playback_stress:media_files")
    assert media_files_param is not None
    assert media_files_param.type == ParamValueType.MULTI_ENUM
    assert media_files_param.options_source == "testing.actions.local_playback:list_media_files"


def test_default_registry_uses_fixed_bluetooth_target_list():
    registry = default_registry()

    reboot_param = registry.get_param("auto_reboot:bt_target")
    suspend_param = registry.get_param("auto_suspend:bt_target")
    bt_onoff_param = registry.get_param("bt_onoff_scan:bt_target")
    ac_onoff_param = registry.get_param("ac_onoff:bt_target")

    assert reboot_param is not None
    assert suspend_param is not None
    assert bt_onoff_param is not None
    assert ac_onoff_param is not None
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
    assert ac_onoff_param.enum_values == reboot_param.enum_values
