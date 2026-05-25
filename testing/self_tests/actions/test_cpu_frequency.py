from __future__ import annotations

from testing.actions import cpu_frequency
from testing.actions.cpu_frequency import CpuFrequencyController, parse_frequency_list
from testing.params.options import normalize_option_values
from testing.tool import adb as adb_tool
import subprocess


def _result(command: str, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["adb", "shell", command], 0, stdout, "")


def test_cpu_frequency_controller_sets_and_restores(monkeypatch) -> None:
    current_frequency = {"value": "500000"}
    commands: list[str] = []

    def fake_adb_shell(command: str, **kwargs):  # noqa: ANN001
        commands.append(command)
        if "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor" in command:
            return _result(command, "schedutil\n")
        if "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq" in command:
            return _result(command, current_frequency["value"] + "\n")
        if command.startswith("echo "):
            current_frequency["value"] = command.split()[2]
            return _result(command)
        return _result(command)

    monkeypatch.setattr(cpu_frequency, "_adb_shell", fake_adb_shell)

    controller = CpuFrequencyController(selected_serial="ABC123")
    snapshot = controller.snapshot()
    controller.set_frequency("2304000")
    observed = controller.wait_current_frequency("2304000")
    restored = controller.restore(snapshot)

    assert observed == "2304000"
    assert restored == "500000"
    assert any(command == "echo performance 2304000 > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor" for command in commands)
    assert any(command == "echo schedutil 500000 > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor" for command in commands)


def test_cpu_frequency_controller_rejects_invalid_frequency() -> None:
    controller = CpuFrequencyController(selected_serial="ABC123")

    try:
        controller.set_frequency("2304000;reboot")
    except ValueError as exc:
        assert "Invalid CPU frequency" in str(exc)
    else:
        raise AssertionError("Expected invalid CPU frequency to be rejected.")


def test_adb_shell_passes_remote_command_as_single_adb_argument(monkeypatch) -> None:
    observed: list[list[str]] = []

    def fake_run(args, **kwargs):  # noqa: ANN001
        observed.append(list(args))
        return subprocess.CompletedProcess(args, 0, b"500000\n", b"")

    monkeypatch.setattr(adb_tool.subprocess, "run", fake_run)

    result = cpu_frequency._adb_shell("cat /sys/path with spaces", selected_serial="ABC123")

    assert observed == [["adb", "-s", "ABC123", "shell", "cat /sys/path with spaces"]]
    assert result.stdout == "500000\n"


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
