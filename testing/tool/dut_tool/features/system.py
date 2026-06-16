from __future__ import annotations

from dataclasses import dataclass
import re


_SCALING_AVAILABLE_FREQUENCIES = "/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies"
_GOVERNOR_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class CpuFrequencySnapshot:
    governor: str
    current_frequency: str
    min_frequency: str
    max_frequency: str


def list_cpu_frequency_options(selected_serial: str | None = None) -> list[str]:
    return _android_dut(selected_serial).available_cpu_frequencies()


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


def safe_frequency(value: str) -> str:
    frequency = str(value or "").strip()
    if not frequency.isdigit():
        raise ValueError(f"Invalid CPU frequency: {value}")
    return frequency


def safe_governor(value: str) -> str:
    governor = str(value or "").strip().splitlines()[0] if str(value or "").strip() else "performance"
    return governor if _GOVERNOR_RE.fullmatch(governor) else "performance"


def _android_dut(selected_serial: str | None):
    from testing.tool.dut_tool.duts.android import android

    return android(serialnumber=str(selected_serial or "").strip())
