from __future__ import annotations

from dataclasses import dataclass

import pytest

import testing.tool.dut_tool.features.iptv_middle_screen as middle_screen_feature
from testing.params.contracts import CASE_CONTRACTS
from testing.tests.android.common.iptv.middle_screen_cases import (
    MIDDLE_SCREEN_CASES,
    SELECTED_SOURCE_IDS,
    case_by_source_id,
)
from testing.tool.dut_tool.features.iptv_middle_screen import (
    MIDDLE_SCREEN_HANDLERS,
    execute_middle_screen_case,
    parse_hdmi_node_evidence,
    parse_interface_addresses,
    parse_link_speed_mbps,
    parse_thermal_millicelsius,
    parse_wm_size,
)
from testing.tool.dut_tool.features.system import verify_cpu_frequency_samples


@pytest.fixture(autouse=True)
def disable_runtime_log_writes(monkeypatch) -> None:
    monkeypatch.setattr(middle_screen_feature, "step_log", lambda *args, **kwargs: None)


@dataclass
class FakeDut:
    outputs: dict[str, str]
    adb_ready: bool = True
    size: str = "Physical size: 1920x1080"

    def __post_init__(self) -> None:
        self.commands: list[str] = []
        self.scans: list[str] = []
        self.connections: list[tuple[str, str, str]] = []
        self.wifi_enabled = False

    def run_device_shell(self, command: str) -> str:
        self.commands.append(command)
        return self.outputs.get(command, "")

    def wifi_enable(self) -> None:
        self.wifi_enabled = True

    def scan(self, ssid: str) -> bool:
        self.scans.append(ssid)
        return True

    def connect(self, ssid: str, password: str, security: str) -> bool:
        self.connections.append((ssid, password, security))
        return True

    def check_adb_status(self, waitTime: int) -> bool:
        assert waitTime == 5
        return self.adb_ready

    def wm_size(self) -> str:
        return self.size


def run_source(source_id: int, dut: FakeDut, params=None, serial="SERIAL") -> None:
    execute_middle_screen_case(case_by_source_id(source_id), dut, params or {}, serial=serial)


def test_iptv_batch_one_contracts_and_parsers() -> None:
    assert SELECTED_SOURCE_IDS == (4,5,10,18,20,21,29,31,32,33,49,52,53,54,55,57,58,59,60,61,62,63,64,65,66,67,68,69,95,96,97,98,114)
    assert len(MIDDLE_SCREEN_CASES) == 33
    assert tuple(case.source_id for case in MIDDLE_SCREEN_CASES) == SELECTED_SOURCE_IDS
    assert all(case.source_file == "中屏用例评估.xlsx" for case in MIDDLE_SCREEN_CASES)
    assert all(case.source_sheet == "SmartTest覆盖评估" for case in MIDDLE_SCREEN_CASES)
    assert {case.executor for case in MIDDLE_SCREEN_CASES} == set(MIDDLE_SCREEN_HANDLERS)
    assert all(case.source_row == case.source_rows[0] for case in MIDDLE_SCREEN_CASES)
    assert all(case.media_sources for case in MIDDLE_SCREEN_CASES if 57 <= case.source_id <= 66)
    declared = {key for case in MIDDLE_SCREEN_CASES for key in case.parameters
                if key.startswith("iptv_middle_screen:")}
    contract = next(item for item in CASE_CONTRACTS if item.case_keys == ("iptv_middle_screen",))
    assert declared == {param.key for param in contract.params}
    assert parse_link_speed_mbps("1000\n") == 1000
    assert parse_wm_size("Physical size: 1920x1080\nOverride size: 1280x720") == (1280, 720)
    assert parse_thermal_millicelsius("52875") == 52875
    assert parse_hdmi_node_evidence("connected\n1080p60hz") == (True, True)
    assert parse_interface_addresses("inet 10.1.2.3/24\ninet6 2001:db8::2/64") == {
        "ipv4": ("10.1.2.3",), "ipv6": ("2001:db8::2",),
    }


def test_usb_storage_handler() -> None:
    command = "cat /proc/mounts; ls -1 /sys/block"
    run_source(4, FakeDut({command: "/dev/sda1 /storage/usb vfat"}))


def test_hdmi_handler_asserts_nodes_only() -> None:
    command = ("cat /sys/class/drm/card0-HDMI-A-1/status 2>/dev/null; "
               "cat /sys/class/amhdmitx/amhdmitx0/hpd_state 2>/dev/null; "
               "cat /sys/class/amhdmitx/amhdmitx0/disp_mode 2>/dev/null")
    run_source(5, FakeDut({command: "connected\n1\n1080p60hz"}))


def test_ethernet_handler_requires_case_input_and_checks_speed() -> None:
    dut = FakeDut({"ip addr show eth0": "inet 192.0.2.2/24", "cat /sys/class/net/eth0/speed": "1000"})
    with pytest.raises(AssertionError, match="expected_speed_mbps"):
        run_source(10, dut)
    run_source(10, dut, {"iptv_middle_screen:expected_speed_mbps": 1000})


def test_emmc_hs400_handler() -> None:
    run_source(20, FakeDut({"dmesg | grep -i mmc": "mmc0: new HS400 device"}))


def test_wifi_handler_uses_verified_android_contract() -> None:
    dut = FakeDut({"ip link show wlan0": "3: wlan0: <UP>", "ip addr show wlan0": "inet 192.0.2.3/24"})
    params = {"iptv_middle_screen:wifi_5g_ssid": "lab-5g", "iptv_middle_screen:wifi_5g_password": "secret"}
    run_source(21, dut, params)
    assert dut.wifi_enabled
    assert dut.scans == ["lab-5g"]
    assert dut.connections == [("lab-5g", "secret", "wpa2")]


def test_thermal_handler() -> None:
    run_source(29, FakeDut({"cat /sys/class/thermal/thermal_zone0/temp": "52875"}))


@pytest.mark.parametrize(("source_id", "serial"), ((31, "USB123"), (32, "192.0.2.4:5555")))
def test_adb_transport_handler(source_id: int, serial: str) -> None:
    run_source(source_id, FakeDut({}), serial=serial)


def test_wm_size_handler() -> None:
    run_source(33, FakeDut({}, size="Physical size: 3840x2160"))


def test_media_observation_uses_configured_duration_and_timeout() -> None:
    now = [0.0]
    sleeps = []
    samples = []
    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds
    middle_screen_feature.observe_media_playback(
        object(), "4k.ts", duration_s=25, poll_interval_s=10,
        assert_state=lambda *args, **kwargs: samples.append((args, kwargs)),
        monotonic=lambda: now[0], sleep=sleep,
    )
    assert sleeps == [10, 10, 5]
    assert len(samples) == 4
    assert all(sample[1]["expected_state"] == "PLAYING" for sample in samples)


def test_cpu_frequency_checkpoint_reads_ten_matching_samples() -> None:
    assert verify_cpu_frequency_samples("500000", lambda: "500000") == ["500000"] * 10


def test_cpu_frequency_checkpoint_fails_on_first_mismatched_sample() -> None:
    values = iter(["500000", "500000", "2208000", "500000"])
    with pytest.raises(AssertionError, match="sample 3/10"):
        verify_cpu_frequency_samples("500000", lambda: next(values))
