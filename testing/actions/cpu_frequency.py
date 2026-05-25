from __future__ import annotations

from dataclasses import dataclass
import re
import time

from testing.runtime.config import current_dut_serial
from testing.tool.adb import run_adb as _run_adb


SCALING_AVAILABLE_FREQUENCIES = "/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies"
SCALING_CUR_FREQ = "/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq"
SCALING_GOVERNOR = "/sys/devices/system/cpu/cpufreq/policy0/scaling_governor"
_GOVERNOR_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class CpuFrequencySnapshot:
    governor: str
    current_frequency: str


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


def _adb_shell(
    command: str,
    *,
    selected_serial: str | None,
    timeout: float = 15.0,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return _run_adb(
        selected_serial=selected_serial,
        args=["shell", str(command)],
        timeout=timeout,
        check=check,
    )


def list_cpu_frequency_options(selected_serial: str | None = None) -> list[str]:
    result = _adb_shell(
        f"cat {SCALING_AVAILABLE_FREQUENCIES}",
        selected_serial=selected_serial,
        timeout=10.0,
    )
    return parse_frequency_list(result.stdout)


class CpuFrequencyController:
    def __init__(self, *, selected_serial: str | None = None) -> None:
        self.selected_serial = str(selected_serial or "").strip() or None

    @classmethod
    def from_environment(cls) -> "CpuFrequencyController":
        return cls(selected_serial=current_dut_serial())

    def ensure_root(self) -> None:
        _run_adb(selected_serial=self.selected_serial, args=["root"], timeout=20.0, check=False)
        _run_adb(selected_serial=self.selected_serial, args=["wait-for-device"], timeout=45.0, check=False)

    def available_frequencies(self) -> list[str]:
        return list_cpu_frequency_options(self.selected_serial)

    def read_current_frequency(self) -> str:
        return self._read_first_frequency(SCALING_CUR_FREQ)

    def read_governor(self) -> str:
        result = _adb_shell(f"cat {SCALING_GOVERNOR}", selected_serial=self.selected_serial, timeout=10.0)
        return _safe_governor(result.stdout.strip())

    def snapshot(self) -> CpuFrequencySnapshot:
        return CpuFrequencySnapshot(
            governor=self.read_governor(),
            current_frequency=self.read_current_frequency(),
        )

    def set_frequency(self, frequency: str, *, governor: str = "performance") -> None:
        target = _safe_frequency(frequency)
        selected_governor = _safe_governor(governor)
        _adb_shell(
            f"echo {selected_governor} {target} > {SCALING_GOVERNOR}",
            selected_serial=self.selected_serial,
            timeout=10.0,
        )

    def wait_current_frequency(self, expected_frequency: str, *, timeout_s: float = 3.0) -> str:
        expected = _safe_frequency(expected_frequency)
        deadline = time.monotonic() + timeout_s
        observed = ""
        while time.monotonic() <= deadline:
            observed = self.read_current_frequency()
            if observed == expected:
                return observed
            time.sleep(0.2)
        return observed

    def restore(self, snapshot: CpuFrequencySnapshot) -> str:
        first_error: RuntimeError | None = None
        try:
            self.set_frequency(snapshot.current_frequency, governor=snapshot.governor)
            observed = self.wait_current_frequency(snapshot.current_frequency)
            if observed == snapshot.current_frequency:
                return observed
        except RuntimeError as exc:
            first_error = exc

        if snapshot.governor != "performance":
            self.set_frequency(snapshot.current_frequency, governor="performance")
            observed = self.wait_current_frequency(snapshot.current_frequency)
            if observed == snapshot.current_frequency:
                return observed

        if first_error is not None:
            raise first_error
        return observed

    def _read_first_frequency(self, path: str) -> str:
        result = _adb_shell(f"cat {path}", selected_serial=self.selected_serial, timeout=10.0)
        values = parse_frequency_list(result.stdout)
        if not values:
            raise RuntimeError(f"No CPU frequency value returned by {path}.")
        return values[0]


def _safe_frequency(value: str) -> str:
    frequency = str(value or "").strip()
    if not frequency.isdigit():
        raise ValueError(f"Invalid CPU frequency: {value}")
    return frequency


def _safe_governor(value: str) -> str:
    governor = str(value or "").strip().splitlines()[0] if str(value or "").strip() else "performance"
    return governor if _GOVERNOR_RE.fullmatch(governor) else "performance"
