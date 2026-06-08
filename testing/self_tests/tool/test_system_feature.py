from __future__ import annotations

from testing.params.options import normalize_option_values
from testing.tool.dut_tool.features import system
from testing.tool.dut_tool.features.system import SystemFeature, parse_frequency_list


class FakeDut:
    def __init__(self) -> None:
        self.current_frequency = "500000"
        self.commands: list[str] = []
        self.root_called = False
        self.wait_devices_called = False
        self.system = SystemFeature(self)

    def root(self) -> None:
        self.root_called = True

    def wait_devices(self) -> None:
        self.wait_devices_called = True

    def run_device_shell(self, command: str) -> str:
        self.commands.append(command)
        if "scaling_governor" in command and command.startswith("cat "):
            return "schedutil\n"
        if "scaling_cur_freq" in command and command.startswith("cat "):
            return self.current_frequency + "\n"
        if "scaling_available_frequencies" in command:
            return "500000 666666 1000000\n"
        if "scaling_min_freq" in command and command.startswith("cat "):
            return self.current_frequency + "\n"
        if "scaling_max_freq" in command and command.startswith("cat "):
            return self.current_frequency + "\n"
        if command.startswith("echo ") and "scaling_governor" not in command:
            self.current_frequency = command.split()[1]
        return ""


def test_cpu_frequency_controller_sets_and_restores_through_dut_system_feature() -> None:
    dut = FakeDut()
    snapshot = dut.system.cpu_frequency_snapshot()
    dut.system.ensure_root()
    dut.system.set_cpu_frequency("2304000")
    observed = dut.system.wait_current_cpu_frequency("2304000")
    restored = dut.system.restore_cpu_frequency(snapshot)

    assert dut.root_called is True
    assert dut.wait_devices_called is True
    assert observed == "2304000"
    assert restored == "500000"
    assert "echo 2304000 > /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq" in dut.commands
    assert "echo 2304000 > /sys/devices/system/cpu/cpufreq/policy0/scaling_min_freq" in dut.commands
    assert "echo schedutil > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor" in dut.commands


def test_list_cpu_frequency_options_uses_android_dut_system_feature(monkeypatch) -> None:
    dut = FakeDut()
    created_serials: list[str | None] = []

    def fake_android_dut(selected_serial: str | None):
        created_serials.append(selected_serial)
        return dut

    monkeypatch.setattr(system, "_android_dut", fake_android_dut)

    assert system.list_cpu_frequency_options("ABC123") == ["500000", "666666", "1000000"]
    assert created_serials == ["ABC123"]


def test_cpu_frequency_controller_rejects_invalid_frequency() -> None:
    try:
        FakeDut().system.set_cpu_frequency("2304000;reboot")
    except ValueError as exc:
        assert "Invalid CPU frequency" in str(exc)
    else:
        raise AssertionError("Expected invalid CPU frequency to be rejected.")


def test_parse_frequency_list_keeps_device_order() -> None:
    assert parse_frequency_list("500000 666666 1000000 500000\n") == [
        "500000",
        "666666",
        "1000000",
    ]


def test_normalize_option_values_accepts_list_and_text() -> None:
    assert normalize_option_values(["500000", "666666", "500000"]) == ["500000", "666666"]
    assert normalize_option_values("500000, 666666 1000000") == [
        "500000",
        "666666",
        "1000000",
    ]
