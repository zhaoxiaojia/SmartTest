from __future__ import annotations

from dataclasses import dataclass
import re
import time

from testing.tool.dut_tool.features.base import FeatureBase


SCALING_AVAILABLE_FREQUENCIES = "/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies"
SCALING_CUR_FREQ = "/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq"
SCALING_GOVERNOR = "/sys/devices/system/cpu/cpufreq/policy0/scaling_governor"
SCALING_MIN_FREQ = "/sys/devices/system/cpu/cpufreq/policy0/scaling_min_freq"
SCALING_MAX_FREQ = "/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq"
_GOVERNOR_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class CpuFrequencySnapshot:
    governor: str
    current_frequency: str
    min_frequency: str
    max_frequency: str


class SystemFeature(FeatureBase):
    def ensure_root(self) -> None:
        if hasattr(self.dut, "root"):
            self.dut.root()
        if hasattr(self.dut, "wait_devices"):
            self.dut.wait_devices()

    def available_cpu_frequencies(self) -> list[str]:
        return parse_frequency_list(self.dut.run_device_shell(f"cat {SCALING_AVAILABLE_FREQUENCIES}"))

    def read_current_cpu_frequency(self) -> str:
        return self._read_first_frequency(SCALING_CUR_FREQ)

    def read_cpu_governor(self) -> str:
        return _safe_governor(self.dut.run_device_shell(f"cat {SCALING_GOVERNOR}"))

    def cpu_frequency_snapshot(self) -> CpuFrequencySnapshot:
        return CpuFrequencySnapshot(
            governor=self.read_cpu_governor(),
            current_frequency=self.read_current_cpu_frequency(),
            min_frequency=self._read_first_frequency(SCALING_MIN_FREQ),
            max_frequency=self._read_first_frequency(SCALING_MAX_FREQ),
        )

    def set_cpu_frequency(self, frequency: str, *, governor: str = "performance") -> None:
        target = _safe_frequency(frequency)
        _safe_governor(governor)
        self._set_frequency_bounds(target, target)

    def wait_current_cpu_frequency(self, expected_frequency: str, *, timeout_s: float = 3.0) -> str:
        expected = _safe_frequency(expected_frequency)
        deadline = time.monotonic() + timeout_s
        observed = ""
        while time.monotonic() <= deadline:
            observed = self.read_current_cpu_frequency()
            if observed == expected:
                return observed
            time.sleep(0.2)
        return observed

    def restore_cpu_frequency(self, snapshot: CpuFrequencySnapshot) -> str:
        first_error: RuntimeError | None = None
        try:
            self.set_cpu_frequency(snapshot.current_frequency, governor=snapshot.governor)
            observed = self.wait_current_cpu_frequency(snapshot.current_frequency)
        except RuntimeError as exc:
            first_error = exc

        self._set_frequency_bounds(snapshot.min_frequency, snapshot.max_frequency)
        self.dut.run_device_shell(f"echo {snapshot.governor} > {SCALING_GOVERNOR}")
        observed = self.wait_current_cpu_frequency(snapshot.current_frequency)
        if observed == snapshot.current_frequency:
            return observed

        if first_error is not None:
            raise first_error
        return observed

    def _set_frequency_bounds(self, min_frequency: str, max_frequency: str) -> None:
        minimum = _safe_frequency(min_frequency)
        maximum = _safe_frequency(max_frequency)
        if int(minimum) > int(maximum):
            raise ValueError(f"Invalid CPU frequency bounds: min={minimum}, max={maximum}")
        current_max = self._read_first_frequency(SCALING_MAX_FREQ)
        if int(minimum) > int(current_max):
            self.dut.run_device_shell(f"echo {maximum} > {SCALING_MAX_FREQ}")
            self.dut.run_device_shell(f"echo {minimum} > {SCALING_MIN_FREQ}")
            return
        self.dut.run_device_shell(f"echo {minimum} > {SCALING_MIN_FREQ}")
        self.dut.run_device_shell(f"echo {maximum} > {SCALING_MAX_FREQ}")

    def _read_first_frequency(self, path: str) -> str:
        values = parse_frequency_list(self.dut.run_device_shell(f"cat {path}"))
        if not values:
            raise RuntimeError(f"No CPU frequency value returned by {path}.")
        return values[0]


def list_cpu_frequency_options(selected_serial: str | None = None) -> list[str]:
    return _android_dut(selected_serial).system.available_cpu_frequencies()


def parse_frequency_list(output: str) -> list[str]:
    frequencies: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\b\d+\b", str(output or "")):
        value = match.group(0)
        if value in seen:
            continue
        seen.add(value)
        frequencies.append(value)
    return frequencies


def _android_dut(selected_serial: str | None):
    from testing.tool.dut_tool.duts.android import android

    return android(serialnumber=str(selected_serial or "").strip())


def _safe_frequency(value: str) -> str:
    frequency = str(value or "").strip()
    if not frequency.isdigit():
        raise ValueError(f"Invalid CPU frequency: {value}")
    return frequency


def _safe_governor(value: str) -> str:
    governor = str(value or "").strip().splitlines()[0] if str(value or "").strip() else "performance"
    return governor if _GOVERNOR_RE.fullmatch(governor) else "performance"
