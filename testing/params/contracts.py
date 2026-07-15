from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from testing.params.schema import ParamCategory, ParamScope, ParamValueType


LOCAL_PLAYBACK_DIR_OPTIONS_SOURCE = "testing.tool.dut_tool.features.local_playback:list_media_dirs"
LOCAL_PLAYBACK_OPTIONS_SOURCE = "testing.tool.dut_tool.features.local_playback:list_media_files"
CONNECTED_BLUETOOTH_TARGETS_OPTIONS_SOURCE = "testing.tool.dut_tool.features.bluetooth:list_connected_bluetooth_targets"
CPU_FREQUENCY_OPTIONS_SOURCE = "testing.tool.dut_tool.features.system:list_cpu_frequency_options"
ENV_USB_RELAY_PORTS_SOURCE = "testing.tool.relay_tool.usb_relay_controller:list_usb_relay_port_entries"
ENV_SERIAL_PORTS_SOURCE = "testing.tool.pc_tool.serial_tool:list_serial_port_entries"


@dataclass(frozen=True)
class ParamContract:
    key: str
    value_type: ParamValueType
    category: ParamCategory
    scope: ParamScope = ParamScope.CASE
    default: Any = ""
    enum_values: tuple[str, ...] = ()
    required_at_start: bool = False
    source_kind: str = "user_input"
    options_source: str = ""
    refreshes_options_sources: tuple[str, ...] = ()
    refresh_on_dut_refresh: bool = False


@dataclass(frozen=True)
class EnvFieldContract:
    key: str
    value_type: str
    default: Any = ""
    source_kind: str = "user_input"
    options_source: str = ""
    refresh_on_dut_refresh: bool = False
    enum_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnvEquipmentContract:
    kind: str
    fields_by_type: Mapping[str, tuple[EnvFieldContract, ...]]


@dataclass(frozen=True)
class CaseContract:
    case_keys: tuple[str, ...]
    params: tuple[ParamContract, ...] = ()
    env_kinds: tuple[str, ...] = ()


CASE_CONTRACTS: tuple[CaseContract, ...] = (
    CaseContract(
        case_keys=("iptv_middle_screen",),
        params=(
            ParamContract("iptv_middle_screen:interface", ParamValueType.STRING, ParamCategory.NETWORK, default=""),
            ParamContract("iptv_middle_screen:expected_speed_mbps", ParamValueType.INT, ParamCategory.NETWORK, default=0),
            ParamContract("iptv_middle_screen:usb_match", ParamValueType.STRING, ParamCategory.DEVICE, default=""),
            ParamContract("iptv_middle_screen:hdmi_state_command", ParamValueType.STRING, ParamCategory.DEVICE, default=""),
            ParamContract("iptv_middle_screen:wifi_2g_ssid", ParamValueType.STRING, ParamCategory.NETWORK, default=""),
            ParamContract("iptv_middle_screen:wifi_2g_password", ParamValueType.STRING, ParamCategory.NETWORK, default=""),
            ParamContract("iptv_middle_screen:wifi_5g_ssid", ParamValueType.STRING, ParamCategory.NETWORK, default=""),
            ParamContract("iptv_middle_screen:wifi_5g_password", ParamValueType.STRING, ParamCategory.NETWORK, default=""),
            ParamContract("iptv_middle_screen:ipv4_ping_target", ParamValueType.STRING, ParamCategory.NETWORK, default="www.baidu.com"),
            ParamContract("iptv_middle_screen:ipv6_ping_target", ParamValueType.STRING, ParamCategory.NETWORK, default="www.baidu.com"),
            ParamContract("iptv_middle_screen:media_source_override", ParamValueType.MULTI_ENUM, ParamCategory.EXECUTION, default=[]),
            ParamContract("iptv_middle_screen:playback_timeout_s", ParamValueType.FLOAT, ParamCategory.EXECUTION, default=10),
            ParamContract("iptv_middle_screen:playback_duration_s", ParamValueType.FLOAT, ParamCategory.EXECUTION, default=86400),
        ),
    ),
    CaseContract(
        case_keys=("local_playback_stress",),
        params=(
            ParamContract(
                key="local_playback_stress:media_dir",
                value_type=ParamValueType.PATH,
                category=ParamCategory.EXECUTION,
                default="/storage/*/Movies /storage/*/Video",
                required_at_start=True,
                source_kind="dut_dynamic",
                options_source=LOCAL_PLAYBACK_DIR_OPTIONS_SOURCE,
                refreshes_options_sources=(LOCAL_PLAYBACK_OPTIONS_SOURCE,),
                refresh_on_dut_refresh=True,
            ),
            ParamContract(
                key="local_playback_stress:media_files",
                value_type=ParamValueType.MULTI_ENUM,
                category=ParamCategory.EXECUTION,
                default=[],
                required_at_start=True,
                source_kind="dut_dynamic",
                options_source=LOCAL_PLAYBACK_OPTIONS_SOURCE,
                refresh_on_dut_refresh=True,
            ),
            ParamContract(
                key="local_playback_stress:actions",
                value_type=ParamValueType.MULTI_ENUM,
                category=ParamCategory.EXECUTION,
                default=["pause", "seek_forward", "seek_backward"],
                enum_values=("pause", "seek_forward", "seek_backward", "back_to_start", "seek_to_end"),
            ),
            ParamContract(
                key="local_playback_stress:loop_count",
                value_type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                default=20,
            ),
            ParamContract(
                key="local_playback_stress:random_playback",
                value_type=ParamValueType.BOOL,
                category=ParamCategory.EXECUTION,
                default=False,
            ),
            ParamContract(
                key="local_playback_stress:action_interval_sec",
                value_type=ParamValueType.FLOAT,
                category=ParamCategory.EXECUTION,
                default=3,
                required_at_start=True,
            ),
            ParamContract(
                key="local_playback_stress:start_wait_sec",
                value_type=ParamValueType.FLOAT,
                category=ParamCategory.EXECUTION,
                default=10,
                required_at_start=True,
            ),
        ),
    ),
    CaseContract(
        case_keys=("ac_onoff",),
        params=(
            ParamContract("ac_onoff:cycle_count", ParamValueType.INT, ParamCategory.EXECUTION, default=20),
            ParamContract("ac_onoff:power_off_sec", ParamValueType.INT, ParamCategory.EXECUTION, default=5, required_at_start=True),
            ParamContract("ac_onoff:power_off_step_sec", ParamValueType.FLOAT, ParamCategory.EXECUTION, default=0),
            ParamContract("ac_onoff:power_on_wait_sec", ParamValueType.INT, ParamCategory.EXECUTION, default=60, required_at_start=True),
            ParamContract("ac_onoff:power_on_wait_step_sec", ParamValueType.FLOAT, ParamCategory.EXECUTION, default=0),
            ParamContract("ac_onoff:ping_target", ParamValueType.STRING, ParamCategory.NETWORK, default=""),
            ParamContract(
                "ac_onoff:bt_target",
                ParamValueType.ENUM,
                ParamCategory.NETWORK,
                default="",
                source_kind="dut_dynamic",
                options_source=CONNECTED_BLUETOOTH_TARGETS_OPTIONS_SOURCE,
                refresh_on_dut_refresh=True,
            ),
        ),
        env_kinds=("relay",),
    ),
    CaseContract(
        case_keys=("cpu_frequency",),
        params=(
            ParamContract(
                "cpu_frequency:loop_count",
                ParamValueType.INT,
                ParamCategory.EXECUTION,
                default=1,
            ),
            ParamContract(
                "cpu_frequency:frequencies",
                ParamValueType.MULTI_ENUM,
                ParamCategory.EXECUTION,
                default=[],
                required_at_start=True,
                source_kind="dut_dynamic",
                options_source=CPU_FREQUENCY_OPTIONS_SOURCE,
                refresh_on_dut_refresh=True,
            ),
        ),
    ),
    CaseContract(
        case_keys=("emmc_rw",),
        params=(
            ParamContract("emmc_rw:loop_count", ParamValueType.INT, ParamCategory.EXECUTION, default=180),
            ParamContract("emmc_rw:source_profile", ParamValueType.STRING, ParamCategory.EXECUTION, default="random1", required_at_start=True),
            ParamContract("emmc_rw:source_size_kb", ParamValueType.INT, ParamCategory.EXECUTION, default=51200, required_at_start=True),
            ParamContract("emmc_rw:min_free_kb", ParamValueType.INT, ParamCategory.EXECUTION, default=307200, required_at_start=True),
            ParamContract("emmc_rw:work_dir", ParamValueType.PATH, ParamCategory.EXECUTION, default="/data/local/tmp/smarttest/emmc_rw", required_at_start=True),
        ),
    ),
    CaseContract(
        case_keys=("auto_reboot",),
        params=(
            ParamContract("auto_reboot:cycle_count", ParamValueType.INT, ParamCategory.EXECUTION, default=20, required_at_start=True),
            ParamContract("auto_reboot:interval_sec", ParamValueType.INT, ParamCategory.EXECUTION, default=100, required_at_start=True),
            ParamContract("auto_reboot:ping_target", ParamValueType.STRING, ParamCategory.NETWORK, default=""),
            ParamContract(
                "auto_reboot:bt_target",
                ParamValueType.ENUM,
                ParamCategory.NETWORK,
                default="",
                source_kind="dut_dynamic",
                options_source=CONNECTED_BLUETOOTH_TARGETS_OPTIONS_SOURCE,
                refresh_on_dut_refresh=True,
            ),
        ),
    ),
    CaseContract(
        case_keys=("auto_suspend",),
        params=(
            ParamContract("auto_suspend:cycle_count", ParamValueType.INT, ParamCategory.EXECUTION, default=20, required_at_start=True),
            ParamContract("auto_suspend:interval_sec", ParamValueType.INT, ParamCategory.EXECUTION, default=100, required_at_start=True),
            ParamContract("auto_suspend:ping_target", ParamValueType.STRING, ParamCategory.NETWORK, default=""),
            ParamContract(
                "auto_suspend:bt_target",
                ParamValueType.ENUM,
                ParamCategory.NETWORK,
                default="",
                source_kind="dut_dynamic",
                options_source=CONNECTED_BLUETOOTH_TARGETS_OPTIONS_SOURCE,
                refresh_on_dut_refresh=True,
            ),
        ),
    ),
    CaseContract(
        case_keys=("wifi_onoff_scan",),
        params=(
            ParamContract("wifi_onoff_scan:cycle_count", ParamValueType.INT, ParamCategory.EXECUTION, default=2),
            ParamContract("wifi_onoff_scan:on_wait_sec", ParamValueType.INT, ParamCategory.EXECUTION, default=5),
            ParamContract("wifi_onoff_scan:off_wait_sec", ParamValueType.INT, ParamCategory.EXECUTION, default=5),
            ParamContract("wifi_onoff_scan:ping_target", ParamValueType.STRING, ParamCategory.NETWORK, default="", required_at_start=True),
        ),
    ),
    CaseContract(
        case_keys=("bt_onoff_scan",),
        params=(
            ParamContract("bt_onoff_scan:cycle_count", ParamValueType.INT, ParamCategory.EXECUTION, default=2),
            ParamContract("bt_onoff_scan:on_wait_sec", ParamValueType.INT, ParamCategory.EXECUTION, default=5),
            ParamContract("bt_onoff_scan:off_wait_sec", ParamValueType.INT, ParamCategory.EXECUTION, default=5),
            ParamContract(
                "bt_onoff_scan:bt_target",
                ParamValueType.ENUM,
                ParamCategory.NETWORK,
                default="",
                required_at_start=True,
                source_kind="dut_dynamic",
                options_source=CONNECTED_BLUETOOTH_TARGETS_OPTIONS_SOURCE,
                refresh_on_dut_refresh=True,
            ),
        ),
    ),
)


ENVIRONMENT_CONTRACTS: dict[str, EnvEquipmentContract] = {
    "relay": EnvEquipmentContract(
        kind="relay",
        fields_by_type={
            "usb_relay": (
                EnvFieldContract(
                    key="port",
                    value_type="enum",
                    default="",
                    source_kind="env_dynamic",
                    options_source=ENV_USB_RELAY_PORTS_SOURCE,
                    refresh_on_dut_refresh=True,
                ),
                EnvFieldContract(key="terminals", value_type="terminal_list", default=()),
            ),
            "snmp_pdu": (
                EnvFieldContract(key="ip", value_type="string", default=""),
                EnvFieldContract(key="port", value_type="int", default=1),
            ),
        },
    ),
    "serial": EnvEquipmentContract(
        kind="serial",
        fields_by_type={
            "uart": (
                EnvFieldContract(
                    key="port",
                    value_type="enum",
                    default="",
                    source_kind="env_dynamic",
                    options_source=ENV_SERIAL_PORTS_SOURCE,
                    refresh_on_dut_refresh=True,
                ),
                EnvFieldContract(key="baud", value_type="int", default=115200),
            ),
        },
    ),
}


def all_param_contracts() -> dict[str, ParamContract]:
    contracts: dict[str, ParamContract] = {}
    for case_contract in CASE_CONTRACTS:
        for param in case_contract.params:
            existing = contracts.get(param.key)
            if existing is not None and existing != param:
                raise ValueError(f"Conflicting parameter contract for {param.key}")
            contracts[param.key] = param
    return contracts


def case_contract(case: Mapping[str, Any]) -> CaseContract | None:
    keys = _case_lookup_keys(case)
    for candidate in CASE_CONTRACTS:
        if any(key in candidate.case_keys for key in keys):
            return candidate
    return None


def case_param_keys(case: Mapping[str, Any]) -> list[str]:
    contract = case_contract(case)
    if contract is None:
        return []
    return [param.key for param in contract.params]


def required_param_keys(case: Mapping[str, Any]) -> list[str]:
    contract = case_contract(case)
    if contract is None:
        return []
    return [param.key for param in contract.params if param.required_at_start]


def env_kinds_for_case(case: Mapping[str, Any]) -> list[str]:
    contract = case_contract(case)
    if contract is None:
        return []
    return list(contract.env_kinds)


def dynamic_param_sources_for_case(case: Mapping[str, Any]) -> list[tuple[str, str]]:
    contract = case_contract(case)
    if contract is None:
        return []
    sources: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for param in contract.params:
        source = str(param.options_source or "").strip()
        if not source:
            continue
        item = (param.key, source)
        if item not in seen:
            seen.add(item)
            sources.append(item)
    return sources


def env_field_contract(kind: str, device_type: str, key: str) -> EnvFieldContract | None:
    equipment = env_equipment_contract(kind)
    if equipment is None:
        return None
    fields = equipment.fields_by_type.get(str(device_type or "").strip(), ())
    for field in fields:
        if field.key == str(key or "").strip():
            return field
    return None


def env_dynamic_sources(kind: str, device_type: str) -> list[tuple[str, str]]:
    equipment = env_equipment_contract(kind)
    if equipment is None:
        return []
    fields = equipment.fields_by_type.get(str(device_type or "").strip(), ())
    return [
        (field.key, field.options_source)
        for field in fields
        if str(field.options_source or "").strip()
    ]


def env_equipment_contract(kind: str) -> EnvEquipmentContract | None:
    return ENVIRONMENT_CONTRACTS.get(str(kind or "").strip().lower())


def env_device_types(kind: str) -> list[str]:
    equipment = env_equipment_contract(kind)
    if equipment is None:
        return []
    return list(equipment.fields_by_type.keys())


def default_env_device_type(kind: str) -> str:
    for device_type in env_device_types(kind):
        return str(device_type)
    return ""


def _case_lookup_keys(case: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    android_case_id = str(case.get("android_case_id", "") or "").strip()
    if android_case_id:
        keys.append(android_case_id)
    nodeid = str(case.get("nodeid", "") or "").strip()
    if nodeid:
        if "::" in nodeid:
            keys.append(nodeid.rsplit("::", 1)[-1])
        keys.append(nodeid)
    for param_key in list(case.get("required_params", [])):
        prefix = str(param_key).split(":", 1)[0].strip()
        if prefix:
            keys.append(prefix)
    deduped: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if key and key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped
