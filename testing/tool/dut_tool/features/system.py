from __future__ import annotations

from dataclasses import dataclass
import re
import os
import time

from tools.logging import smart_log


_SCALING_AVAILABLE_FREQUENCIES = "/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies"
_GOVERNOR_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class CpuFrequencySnapshot:
    current_frequency: str


def list_cpu_frequency_options(selected_serial: str | None = None, dut=None) -> list[str]:
    resolved_dut = dut if dut is not None else _default_dut(selected_serial)
    return resolved_dut.available_cpu_frequencies()


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


def verify_cpu_frequency_samples(
    expected_frequency: str,
    read_current_frequency,
    *,
    sample_count: int = 10,
    on_sample=None,
) -> list[str]:
    expected = safe_frequency(expected_frequency)
    samples: list[str] = []
    for index in range(1, sample_count + 1):
        observed = safe_frequency(read_current_frequency())
        samples.append(observed)
        if on_sample is not None:
            on_sample(index, sample_count, observed)
        if observed != expected:
            raise AssertionError(
                "CPU frequency checkpoint failed: "
                f"sample {index}/{sample_count}, target={expected}, observed={observed}"
            )
    return samples


def clear_app_data(dut, app_name: str):
    return dut.adb_call("shell", "pm", "clear", app_name)


def package_exists(dut, package_name: str) -> bool:
    return package_name in dut.run_device_shell("pm list packages")


def install_apk(dut, apk_path: str):
    resolved_path = os.path.join(os.getcwd(), "res\\" + apk_path)
    return dut.checkoutput_shell(f"install -r -t {resolved_path}")


def uninstall_apk(dut, package_name: str) -> bool:
    output = dut.checkoutput_shell(f"uninstall {package_name}")
    time.sleep(5)
    if "Success" in output:
        smart_log("APK uninstall successful", level="info")
        return True
    smart_log("APK uninstall failed", level="info")
    return False


def getprop(dut, key: str):
    return dut.run_device_shell("getprop %s" % key)


def _default_dut(selected_serial: str | None):
    from testing.tool.dut_tool.duts.android import android

    return android(serialnumber=str(selected_serial or "").strip())
