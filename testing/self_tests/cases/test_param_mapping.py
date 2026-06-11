from __future__ import annotations

from testing.params.android_catalog import load_android_catalog_cases
from testing.params.registry import default_registry
from testing.params.schema import ParamValueType

CPU_FREQUENCY_PARAM_KEY = "cpu_frequency:frequencies"
BT_TARGET_OPTIONS_SOURCE = "testing.tool.dut_tool.features.bluetooth:list_connected_bluetooth_targets"


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

    assert [f"{param.case_id}:{param.param_id}" for param in cases_by_id["emmc_rw"].params] == [
        "emmc_rw:loop_count",
        "emmc_rw:source_profile",
        "emmc_rw:source_size_kb",
        "emmc_rw:min_free_kb",
        "emmc_rw:work_dir",
    ]
    assert [f"{param.case_id}:{param.param_id}" for param in cases_by_id["auto_reboot"].params] == [
        "auto_reboot:cycle_count",
        "auto_reboot:interval_sec",
        "auto_reboot:ping_target",
        "auto_reboot:bt_target",
    ]
    assert [f"{param.case_id}:{param.param_id}" for param in cases_by_id["auto_suspend"].params] == [
        "auto_suspend:cycle_count",
        "auto_suspend:interval_sec",
        "auto_suspend:ping_target",
        "auto_suspend:bt_target",
    ]
    assert [f"{param.case_id}:{param.param_id}" for param in cases_by_id["wifi_onoff_scan"].params] == [
        "wifi_onoff_scan:cycle_count",
        "wifi_onoff_scan:ping_target",
    ]
    assert [f"{param.case_id}:{param.param_id}" for param in cases_by_id["bt_onoff_scan"].params] == [
        "bt_onoff_scan:cycle_count",
        "bt_onoff_scan:bt_target",
    ]


def test_default_registry_includes_android_client_emmc_params():
    registry = default_registry()

    for key in [
        "emmc_rw:loop_count",
        "emmc_rw:source_profile",
        "emmc_rw:source_size_kb",
        "emmc_rw:min_free_kb",
        "emmc_rw:work_dir",
        "auto_reboot:cycle_count",
        "auto_reboot:interval_sec",
        "auto_reboot:ping_target",
        "auto_reboot:bt_target",
        "auto_suspend:cycle_count",
        "auto_suspend:interval_sec",
        "auto_suspend:ping_target",
        "auto_suspend:bt_target",
        "wifi_onoff_scan:cycle_count",
        "wifi_onoff_scan:ping_target",
        "bt_onoff_scan:cycle_count",
        "bt_onoff_scan:bt_target",
        "ac_onoff:cycle_count",
        "ac_onoff:power_off_sec",
        "ac_onoff:power_off_step_sec",
        "ac_onoff:power_on_wait_sec",
        "ac_onoff:power_on_wait_step_sec",
        "ac_onoff:ping_target",
        "ac_onoff:bt_target",
        "local_playback_stress:media_dir",
        "local_playback_stress:media_files",
        "local_playback_stress:actions",
        "local_playback_stress:loop_count",
        "local_playback_stress:random_playback",
        "local_playback_stress:action_interval_sec",
        "local_playback_stress:start_wait_sec",
    ]:
        assert registry.get_param(key) is not None

    assert registry.get_param("ac_onoff:power_off_step_sec").type == ParamValueType.FLOAT
    assert registry.get_param("ac_onoff:power_on_wait_step_sec").type == ParamValueType.FLOAT

    cpu_frequency_param = registry.get_param(CPU_FREQUENCY_PARAM_KEY)
    assert cpu_frequency_param is not None
    assert cpu_frequency_param.type == ParamValueType.MULTI_ENUM
    assert cpu_frequency_param.options_source == "testing.tool.dut_tool.features.system:list_cpu_frequency_options"

    media_files_param = registry.get_param("local_playback_stress:media_files")
    assert media_files_param is not None
    assert media_files_param.type == ParamValueType.MULTI_ENUM
    assert media_files_param.options_source == "testing.tool.dut_tool.features.local_playback:list_media_files"

    actions_param = registry.get_param("local_playback_stress:actions")
    assert actions_param is not None
    assert "play" not in actions_param.enum_values


def test_default_registry_uses_connected_bluetooth_target_source():
    registry = default_registry()

    for key in [
        "auto_reboot:bt_target",
        "auto_suspend:bt_target",
        "bt_onoff_scan:bt_target",
        "ac_onoff:bt_target",
    ]:
        field = registry.get_param(key)
        assert field is not None
        assert field.enum_values == []
        assert field.options_source == BT_TARGET_OPTIONS_SOURCE
