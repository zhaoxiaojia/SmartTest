from __future__ import annotations

import ipaddress
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

from testing.runtime.steps import step_log
from support.param_conversion import to_float, to_int, to_string_list


def parse_link_speed_mbps(output: str) -> int:
    value = str(output or "").strip()
    if not re.fullmatch(r"\d+", value):
        raise ValueError(f"Invalid Ethernet speed output: {value!r}")
    return int(value)


def parse_wm_size(output: str) -> tuple[int, int]:
    matches = re.findall(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", str(output or ""), re.I)
    if not matches:
        raise ValueError("wm size output contains no dimensions")
    return tuple(map(int, matches[-1]))


def supports_resolution_at_least(output: str, minimum: tuple[int, int] = (1920, 1080)) -> bool:
    width, height = parse_wm_size(output)
    return width >= minimum[0] and height >= minimum[1]


def parse_thermal_millicelsius(output: str) -> int:
    value = str(output or "").strip()
    if not re.fullmatch(r"-?\d+", value):
        raise ValueError(f"Invalid thermal value: {value!r}")
    return int(value)


def parse_interface_addresses(output: str) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {"ipv4": [], "ipv6": []}
    for family, raw in re.findall(r"\binet(6?)\s+(?:addr:)?([^\s/]+)", str(output or "")):
        address = ipaddress.ip_address(raw)
        result["ipv6" if family else "ipv4"].append(str(address))
    return {key: tuple(value) for key, value in result.items()}


def parse_hdmi_node_evidence(output: str) -> tuple[bool, bool]:
    value = str(output or "").lower()
    connected = bool(re.search(r"(^|\s)(connected|1)(\s|$)", value))
    active_mode = bool(re.search(r"\b(?:\d{3,4}[pi]\d{2,3}(?:hz)?|enabled)\b", value))
    return connected, active_mode


def _param(params: Mapping[str, Any], key: str, default: Any = "") -> Any:
    return params.get(f"iptv_middle_screen:{key}", default)


def _shell(dut: Any, command: str, source_id: int) -> str:
    output = str(dut.run_device_shell(command) or "").strip()
    step_log("iptv.middle_screen.probe", extra={"source_id": source_id, "command": command, "output": output})
    return output


def check_usb_storage(case: Any, dut: Any, params: Mapping[str, Any], serial: str) -> None:
    output = _shell(dut, "cat /proc/mounts; ls -1 /sys/block", case.source_id)
    matcher = str(_param(params, "usb_match", "") or "").strip()
    assert matcher in output if matcher else re.search(r"(?:/storage/|/mnt/media_rw/|\bsd[a-z]\b)", output)


def check_hdmi_objective(case: Any, dut: Any, params: Mapping[str, Any], serial: str) -> None:
    command = str(_param(params, "hdmi_state_command", "") or "").strip() or (
        "cat /sys/class/drm/card0-HDMI-A-1/status 2>/dev/null; "
        "cat /sys/class/amhdmitx/amhdmitx0/hpd_state 2>/dev/null; "
        "cat /sys/class/amhdmitx/amhdmitx0/disp_mode 2>/dev/null"
    )
    connected, active_mode = parse_hdmi_node_evidence(_shell(dut, command, case.source_id))
    assert connected, "HDMI connector is not objectively connected"
    assert active_mode, "No active HDMI output-node mode evidence"
    step_log("HDMI TV visual result is a manual boundary", extra={"source_id": case.source_id, "manual": True})


def check_ethernet_speed(case: Any, dut: Any, params: Mapping[str, Any], serial: str) -> None:
    interface = str(_param(params, "interface", "eth0") or "eth0").strip()
    expected = to_int(_param(params, "expected_speed_mbps", 0), default=0)
    assert expected > 0, "Configure expected_speed_mbps for the known-speed link prerequisite"
    addresses = parse_interface_addresses(_shell(dut, f"ip addr show {interface}", case.source_id))
    assert any(not ipaddress.ip_address(value).is_loopback for values in addresses.values() for value in values)
    assert parse_link_speed_mbps(_shell(dut, f"cat /sys/class/net/{interface}/speed", case.source_id)) == expected


def check_emmc_hs400(case: Any, dut: Any, params: Mapping[str, Any], serial: str) -> None:
    assert "hs400" in _shell(dut, "dmesg | grep -i mmc", case.source_id).lower()


def check_wifi(case: Any, dut: Any, params: Mapping[str, Any], serial: str) -> None:
    dut.wifi_enable()
    interface_output = _shell(dut, "ip link show wlan0", case.source_id)
    assert re.search(r"\bwlan0\b", interface_output), "wlan0 interface evidence unavailable"
    configured = []
    for band in ("2g", "5g"):
        ssid = str(_param(params, f"wifi_{band}_ssid", "") or "").strip()
        if ssid:
            configured.append((ssid, str(_param(params, f"wifi_{band}_password", "") or "")))
    assert configured, "Configure at least one Wi-Fi SSID"
    for ssid, password in configured:
        assert dut.scan(ssid), f"SSID not found: {ssid}"
        assert dut.connect(ssid, password, "wpa2" if password else "open"), f"Connection failed: {ssid}"
        addresses = parse_interface_addresses(_shell(dut, "ip addr show wlan0", case.source_id))
        assert any(not ipaddress.ip_address(value).is_loopback for values in addresses.values() for value in values)


def check_thermal(case: Any, dut: Any, params: Mapping[str, Any], serial: str) -> None:
    parse_thermal_millicelsius(_shell(dut, "cat /sys/class/thermal/thermal_zone0/temp", case.source_id))


def check_adb_transport(case: Any, dut: Any, params: Mapping[str, Any], serial: str) -> None:
    assert dut.check_adb_status(waitTime=5)
    is_network = bool(re.match(r"^(?:\[.*\]|[^:]+):\d+$", serial))
    assert is_network == (case.source_id == 32), "Selected ADB transport does not match source prerequisite"


def check_wm_size(case: Any, dut: Any, params: Mapping[str, Any], serial: str) -> None:
    output = dut.wm_size()
    assert supports_resolution_at_least(output), f"Effective UI mode is below 1080p: {output}"


Handler = Callable[[Any, Any, Mapping[str, Any], str], None]

def check_cpu_frequency(case, dut, params, serial):
    values=to_string_list(params.get("cpu_frequency:frequencies",[])) or dut.available_cpu_frequencies(); assert values
    original=dut.cpu_frequency_snapshot()
    try:
        for value in values: dut.set_cpu_frequency(value); assert dut.wait_current_cpu_frequency(value)==value
    finally: assert dut.restore_cpu_frequency(original)==original.current_frequency

def check_network(case,dut,params,serial):
    interface=str(_param(params,"interface","") or ("wlan0" if case.source_id in (54,55) else "eth0")); addresses=parse_interface_addresses(_shell(dut,f"ip addr show {interface}",case.source_id))
    if case.source_id in (49,52,54): assert addresses["ipv4"] and dut.ping(interface=interface,hostname=str(_param(params,"ipv4_ping_target","www.baidu.com")))
    if case.source_id in (49,53,55):
        assert any(not ipaddress.ip_address(v).is_link_local for v in addresses["ipv6"])
        assert "0% packet loss" in _shell(dut,f"ping6 -c 3 {_param(params,'ipv6_ping_target','www.baidu.com')}",case.source_id)

def check_media(case,dut,params,serial):
    sources=to_string_list(_param(params,"media_source_override",[])) or list(case.media_sources)
    if not sources: import pytest; pytest.skip(f"source {case.source_id} requires configured media")
    from testing.tool.dut_tool.features.local_playback import assert_media_session_state
    timeout_s=max(to_float(_param(params,"playback_timeout_s",10),default=10),0)
    duration_s=max(to_float(_param(params,"playback_duration_s",86400),default=86400),0) if case.source_id==114 else timeout_s
    for source in sources:
        dut.start_file(source)
        observe_media_playback(dut,source,duration_s=duration_s,poll_interval_s=timeout_s,
                               assert_state=assert_media_session_state)
        dut.stop_player()

def observe_media_playback(dut,source,*,duration_s,poll_interval_s,assert_state,monotonic=time.monotonic,sleep=time.sleep):
    """Objectively sample PLAYING for the configured observation window."""
    assert_state(dut,file_path=source,expected_state="PLAYING")
    deadline=monotonic()+max(duration_s,0)
    while monotonic()<deadline:
        sleep(min(max(poll_interval_s,0.001),max(deadline-monotonic(),0)))
        assert_state(dut,file_path=source,expected_state="PLAYING")

def check_image(case,dut,params,serial):
    sources=to_string_list(_param(params,"media_source_override",[]))
    if not sources: import pytest; pytest.skip("configure workbook image paths")
    for source in sources: _shell(dut,f"am start -a android.intent.action.VIEW -d file://'{source}'",case.source_id); assert _shell(dut,"dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'",case.source_id)

MIDDLE_SCREEN_HANDLERS: dict[str, Handler] = {
    "usb_storage": check_usb_storage,
    "hdmi_objective": check_hdmi_objective,
    "ethernet_speed": check_ethernet_speed,
    "emmc_hs400": check_emmc_hs400,
    "wifi": check_wifi,
    "thermal": check_thermal,
    "adb_transport": check_adb_transport,
    "wm_size": check_wm_size,
    "cpu_frequency": check_cpu_frequency,
    "network": check_network,
    "media": check_media,
    "image": check_image,
}


def execute_middle_screen_case(case: Any, dut: Any, params: Mapping[str, Any], *, serial: str) -> None:
    MIDDLE_SCREEN_HANDLERS[case.executor](case, dut, params, serial)
