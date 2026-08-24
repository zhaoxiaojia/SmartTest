from __future__ import annotations

from dataclasses import dataclass

import pytest

import core.testing.tool.dut_tool.features.iptv_middle_screen as middle_screen_feature
from core.testing.params.contracts import all_param_contracts, case_param_keys
from core.testing.params.schema import ParamValueType
from core.testing.tests.android.common.iptv.middle_screen_cases import (
    MIDDLE_SCREEN_CASES,
    SELECTED_SOURCE_IDS,
    case_by_source_id,
)
from core.testing.tool.dut_tool.features.iptv_middle_screen import (
    MIDDLE_SCREEN_HANDLERS,
    execute_middle_screen_case,
    parse_hdmi_node_evidence,
    parse_interface_addresses,
    parse_link_speed_mbps,
    parse_thermal_millicelsius,
    parse_wm_size,
    parse_ping_success,
    run_middle_screen_action,
    cleanup_middle_screen_case,
    check_image,
    prepare_middle_screen_case,
    TARGET_SOURCE_IDS,
)
from core.testing.tests.android.common.iptv.middle_screen_runner import assert_middle_screen_objective
from core.testing.tool.dut_tool.features.system import verify_cpu_frequency_samples
from core.testing.steps.planner import build_step_plan


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

    def wifi_disable(self) -> None:
        self.wifi_enabled = False

    def scan(self, ssid: str) -> bool:
        self.scans.append(ssid)
        return True

    def connect(self, ssid: str, password: str, security: str, **kwargs) -> bool:
        assert kwargs == {"forget_existing": False}
        self.connections.append((ssid, password, security))
        return True

    def check_adb_status(self, waitTime: int) -> bool:
        assert waitTime == 5
        return self.adb_ready

    def wm_size(self) -> str:
        return self.size


def run_source(source_id: int, dut: FakeDut, params=None, serial="SERIAL") -> None:
    case = case_by_source_id(source_id)
    values = params or {}
    if source_id not in TARGET_SOURCE_IDS:
        execute_middle_screen_case(case, dut, values, serial=serial)
        return
    state = prepare_middle_screen_case(case, dut, values, serial=serial)
    try:
        assert_middle_screen_objective(case, run_middle_screen_action(case, dut, values, serial=serial))
    finally:
        assert cleanup_middle_screen_case(case, dut, state)["restored"]


def test_iptv_batch_one_contracts_and_parsers() -> None:
    assert SELECTED_SOURCE_IDS == (4,5,10,18,20,21,29,31,32,33,49,52,53,54,55,57,58,59,60,61,62,63,64,65,66,67,68,69,95,96,97,98,114)
    assert len(MIDDLE_SCREEN_CASES) == 33
    assert tuple(case.source_id for case in MIDDLE_SCREEN_CASES) == SELECTED_SOURCE_IDS
    assert all(case.source_file == "中屏用例评估.xlsx" for case in MIDDLE_SCREEN_CASES)
    assert all(case.source_sheet == "SmartTest覆盖评估" for case in MIDDLE_SCREEN_CASES)
    assert {case.executor for case in MIDDLE_SCREEN_CASES if case.source_id not in TARGET_SOURCE_IDS} == set(MIDDLE_SCREEN_HANDLERS)
    assert all(case.source_row == case.source_rows[0] for case in MIDDLE_SCREEN_CASES)
    assert all(case.media_sources for case in MIDDLE_SCREEN_CASES if 57 <= case.source_id <= 66)
    declared = {key for case in MIDDLE_SCREEN_CASES for key in case.parameters
                if key.startswith("iptv_middle_screen:")}
    assert declared == set()
    assert parse_link_speed_mbps("1000\n") == 1000
    assert parse_wm_size("Physical size: 1920x1080\nOverride size: 1280x720") == (1280, 720)
    assert parse_thermal_millicelsius("52875") == 52875
    assert parse_hdmi_node_evidence("connected\n1080p60hz") == (True, True)
    assert parse_interface_addresses("inet 10.1.2.3/24\ninet6 2001:db8::2/64") == {
        "ipv4": ("10.1.2.3",), "ipv6": ("2001:db8::2",),
    }


def test_usb_storage_handler() -> None:
    command = "cat /proc/mounts; ls -1 /sys/block"
    run_source(4, FakeDut({command: "/dev/sda1 /storage/usb vfat"}), {"iptv_middle_screen_004:usb_match": "sda"})


def test_hdmi_handler_asserts_nodes_only() -> None:
    command = ("cat /sys/class/drm/card0-HDMI-A-1/status 2>/dev/null; "
               "cat /sys/class/amhdmitx/amhdmitx0/hpd_state 2>/dev/null; "
               "cat /sys/class/amhdmitx/amhdmitx0/disp_mode 2>/dev/null")
    run_source(5, FakeDut({command: "connected\n1\n1080p60hz"}))


def test_ethernet_handler_requires_case_input_and_checks_speed() -> None:
    dut = FakeDut({"ip addr show eth0": "inet 192.0.2.2/24", "cat /sys/class/net/eth0/speed": "1000"})
    with pytest.raises(AssertionError, match="expected_speed_mbps"):
        run_source(10, dut)
    run_source(10, dut, {"iptv_middle_screen_010:expected_speed_mbps": 1000})


def test_emmc_hs400_handler() -> None:
    run_source(20, FakeDut({"dmesg | grep -i mmc": "mmc0: new HS400 device"}))


def test_wifi_handler_uses_verified_android_contract() -> None:
    dut = FakeDut({"ip link show wlan0": "3: wlan0: <UP>", "ip addr show wlan0": "inet 192.0.2.3/24"})
    params = {
        "iptv_middle_screen_021:wifi_2g_ssid": "lab-2g",
        "iptv_middle_screen_021:wifi_2g_password": "secret2",
        "iptv_middle_screen_021:wifi_5g_ssid": "lab-5g",
        "iptv_middle_screen_021:wifi_5g_password": "secret5",
    }
    run_source(21, dut, params)
    assert not dut.wifi_enabled
    assert dut.scans == ["lab-2g", "lab-5g"]
    assert dut.connections == [("lab-2g", "secret2", "wpa2"), ("lab-5g", "secret5", "wpa2")]


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


def test_ping_parser_does_not_accept_one_hundred_percent_packet_loss() -> None:
    assert parse_ping_success("3 packets transmitted, 3 received, 0% packet loss")
    assert not parse_ping_success("3 packets transmitted, 0 received, 100% packet loss")


def test_middle_screen_case_contracts_have_approved_coverage_boundaries() -> None:
    target_ids = {4, 10, 18, 20, 21, 29, 31, 32, 33, 49, 52, 53, 54, 55,
                  57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 95, 96, 97, 98, 114}
    cases = [case for case in MIDDLE_SCREEN_CASES if case.source_id in target_ids]
    assert len(cases) == 29
    assert all(case.coverage_level == "full" for case in cases[:14])
    assert all(case.coverage_level == "software_partial" for case in cases[14:])
    assert all(case.unverified_items for case in cases[14:])
    assert all(len(case.steps) == 7 for case in cases)


def test_media_player_is_stopped_when_playback_check_fails(monkeypatch) -> None:
    class MediaDut:
        def __init__(self):
            self.stopped = 0
        def start_file(self, source):
            pass
        def stop_player(self):
            self.stopped += 1

    dut = MediaDut()
    monkeypatch.setattr(middle_screen_feature, "observe_media_playback", lambda *a, **k: (_ for _ in ()).throw(AssertionError("stopped")))
    with pytest.raises(AssertionError, match="stopped"):
        run_source(95, dut, {"iptv_middle_screen_095:media_url": "http://example/test.ts"})
    assert dut.stopped == 1


def test_independent_middle_screen_nodeid_loads_its_case_plan() -> None:
    nodeid = "testing/tests/android/common/iptv/test_middle_screen_004_usb_storage.py::test_middle_screen_004_usb_storage"
    plan = build_step_plan(root_dir=__import__("pathlib").Path.cwd(), nodeid=nodeid, prefer_catalog=False)
    assert len(plan) == 7
    assert {item["definition_id"].split(".")[1] for item in plan} == {"004"}


def test_feature_returns_ethernet_facts_and_pytest_owns_checkpoint() -> None:
    dut = FakeDut({"ip addr show eth0": "inet 192.0.2.2/24", "cat /sys/class/net/eth0/speed": "100"})
    facts = run_middle_screen_action(
        case_by_source_id(10),
        dut,
        {"iptv_middle_screen_010:interface": "eth0", "iptv_middle_screen_010:expected_speed_mbps": 1000},
        serial="SERIAL",
    )
    assert facts["actual_speed_mbps"] == 100
    with pytest.raises(AssertionError):
        assert_middle_screen_objective(case_by_source_id(10), facts)


def test_media_facts_capture_checkpoint_failure_without_skipping_cleanup(monkeypatch) -> None:
    class MediaDut:
        def __init__(self):
            self.stopped = 0
        def start_file(self, source):
            pass
        def stop_player(self):
            self.stopped += 1

    dut = MediaDut()
    monkeypatch.setattr(middle_screen_feature, "observe_media_playback", lambda *a, **k: (_ for _ in ()).throw(AssertionError("not playing")))
    facts = run_middle_screen_action(
        case_by_source_id(95),
        dut,
        {"iptv_middle_screen_095:media_url": "http://example/test.ts"},
        serial="SERIAL",
    )
    assert facts["results"][0]["playing"] is False
    with pytest.raises(AssertionError):
        assert_middle_screen_objective(case_by_source_id(95), facts)
    result = cleanup_middle_screen_case(case_by_source_id(95), dut, {})
    assert result["player_stopped"] is True
    assert dut.stopped == 1


def test_middle_screen_catalog_is_split_into_exactly_33_test_modules() -> None:
    root = __import__("pathlib").Path("core/testing/tests/android/common/iptv")
    modules = sorted(root.glob("test_middle_screen_*.py"))
    assert len(modules) == 33
    assert not (root / "test_middle_screen_batch.py").exists()


def test_each_middle_screen_case_exposes_only_its_declared_parameters() -> None:
    for case in MIDDLE_SCREEN_CASES:
        row = {
            "nodeid": f"testing/tests/android/common/iptv/test_middle_screen_{case.source_id:03d}.py::test_middle_screen_{case.source_id:03d}",
            "required_params": list(case.parameters),
        }
        assert case_param_keys(row) == list(case.parameters), f"source {case.source_id} parameter mapping"


def test_selecting_usb_and_hdmi_exposes_one_parameter_for_each_case() -> None:
    rows = []
    for source_id in (4, 5):
        case = case_by_source_id(source_id)
        row = {"nodeid": f"case::{source_id}", "required_params": list(case.parameters)}
        rows.append(case_param_keys(row))
    assert [len(keys) for keys in rows] == [1, 1]


def test_source_067_image_paths_use_required_multiline_input() -> None:
    contract = all_param_contracts()["iptv_middle_screen_067:media_files"]
    assert contract.value_type == ParamValueType.MULTILINE
    assert contract.required_at_start is True


def test_source_067_preserves_spaces_inside_each_image_path(monkeypatch) -> None:
    commands = []
    monkeypatch.setattr(
        middle_screen_feature,
        "_shell",
        lambda dut, command, source_id: commands.append(command) or "mCurrentFocus=ImageViewer",
    )
    check_image(
        case_by_source_id(67),
        object(),
        {"iptv_middle_screen_067:media_files": "/storage/My Photos/a one.jpg\n/storage/My Photos/b two.png\n\n"},
        "SERIAL",
    )
    launch_commands = [command for command in commands if command.startswith("am start")]
    assert launch_commands == [
        "am start -a android.intent.action.VIEW -d file://'/storage/My Photos/a one.jpg'",
        "am start -a android.intent.action.VIEW -d file://'/storage/My Photos/b two.png'",
    ]


def test_all_exposed_middle_screen_parameter_texts_are_translated(tmp_path) -> None:
    from xml.etree import ElementTree
    from subprocess import run
    from PySide6.QtCore import QTranslator
    from support.scripts import env

    exposed = {key for case in MIDDLE_SCREEN_CASES for key in case.parameters}
    for locale in ("zh_CN", "en_US"):
        path = __import__("pathlib").Path(f"client/app/ui/example/example_{locale}.ts")
        root = ElementTree.parse(path).getroot()
        context = next(item for item in root.findall("context") if item.findtext("name") == "TestPageBridge")
        translations = {str(message.findtext("source") or ""): str(message.findtext("translation") or "") for message in context.findall("message")}
        qm_path = tmp_path / f"middle_screen_{locale}.qm"
        run([env.pyside6_lrelease(), str(path), "-qm", str(qm_path)], check=True)
        translator = QTranslator()
        assert translator.load(str(qm_path))
        for key in exposed:
            normalized = key.replace(":", ".")
            for part in ("label", "description"):
                text_key = f"test.param.{normalized}.{part}"
                assert translations.get(text_key) and translations[text_key] != text_key, f"{locale}: {text_key}"
                assert translator.translate("TestPageBridge", text_key) == translations[text_key]
