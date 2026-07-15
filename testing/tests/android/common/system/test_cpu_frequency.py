from __future__ import annotations

import pytest

from testing.tool.dut_tool.features.system import (
    CpuFrequencySnapshot,
    verify_cpu_frequency_samples,
)
from testing.params.registry import CPU_FREQUENCY_LOOP_COUNT_KEY, CPU_FREQUENCY_PARAM_KEY
from testing.test_context import smarttest_context
from testing.runtime.config import current_dut_serial
from testing.runtime.steps import case_step, step_log


pytestmark = pytest.mark.case_type("system")

SMARTTEST_CASE_PLAN = {
    "case_id": "cpu_frequency",
    "steps": [
        {
            "id": "cpu_frequency.read_available",
            "title": "Read available CPU frequencies",
            "kind": "setup",
            "definition_id": "cpu.frequency.read_available",
            "expected": "DUT returns selectable CPU frequency values.",
        },
        {
            "id": "cpu_frequency.read_original",
            "title": "Read original CPU frequency",
            "kind": "setup",
            "definition_id": "cpu.frequency.read_original",
            "expected": "Original current frequency is captured before switching.",
        },
        {
            "id": "cpu_frequency.set",
            "title": "Set selected CPU frequencies",
            "kind": "step",
            "definition_id": "cpu.frequency.set",
            "expected": "scaling_cur_freq matches each selected value after setting.",
        },
        {
            "id": "cpu_frequency.restore",
            "title": "Restore original CPU frequency",
            "kind": "teardown",
            "definition_id": "cpu.frequency.restore",
            "expected": "DUT returns to the original current frequency.",
        },
    ],
}


@pytest.mark.requires_params(CPU_FREQUENCY_LOOP_COUNT_KEY, CPU_FREQUENCY_PARAM_KEY)
def test_cpu_frequency_switching(request):
    selected_frequencies = smarttest_context().params.get_list(request.node.nodeid, CPU_FREQUENCY_PARAM_KEY, [])
    loop_count = max(smarttest_context().params.get_int(request.node.nodeid, CPU_FREQUENCY_LOOP_COUNT_KEY, 1), 1)
    from testing.tool.dut_tool.duts.android import android

    dut = android(serialnumber=current_dut_serial())
    original: CpuFrequencySnapshot | None = None

    with case_step(
        "Read available CPU frequencies",
        definition_id="cpu.frequency.read_available",
        expected="DUT returns selectable CPU frequency values.",
    ):
        available_frequencies = dut.available_cpu_frequencies()
        step_log(f"available_frequencies={available_frequencies}")
        if not available_frequencies:
            pytest.fail("No CPU frequencies were returned by scaling_available_frequencies.")
        if not selected_frequencies:
            pytest.fail("Select at least one CPU frequency before running this case.")
        unsupported = [value for value in selected_frequencies if value not in available_frequencies]
        if unsupported:
            pytest.fail(
                "Selected CPU frequencies are not available on this DUT: "
                + ", ".join(unsupported)
            )

    with case_step(
        "Read original CPU frequency",
        definition_id="cpu.frequency.read_original",
        expected="Original current frequency is captured before switching.",
    ):
        dut.ensure_root()
        original = dut.cpu_frequency_snapshot()
        step_log(
            "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq "
            f"-> {original.current_frequency} (original)"
        )

    try:
        total = len(selected_frequencies) * loop_count
        current_index = 0
        for cycle_index in range(1, loop_count + 1):
            for target_frequency in selected_frequencies:
                current_index += 1
                with case_step(
                    f"Cycle {cycle_index}/{loop_count}: Set CPU frequency {target_frequency} ({current_index}/{total})",
                    definition_id="cpu.frequency.set",
                    expected=f"scaling_cur_freq={target_frequency}",
                ):
                    current_before = dut.read_current_cpu_frequency()
                    step_log(
                        "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq "
                        f"-> {current_before} (before set target={target_frequency}) "
                        f"cycle={cycle_index}/{loop_count} step={current_index}/{total}"
                    )
                    dut.set_cpu_frequency(target_frequency)
                    def log_frequency_sample(sample_index, sample_count, observed):
                        step_log(
                            "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq "
                            f"-> {observed} (after set target={target_frequency}, "
                            f"sample={sample_index}/{sample_count}) "
                            f"cycle={cycle_index}/{loop_count} step={current_index}/{total}"
                        )

                    verify_cpu_frequency_samples(
                        target_frequency,
                        dut.read_current_cpu_frequency,
                        on_sample=log_frequency_sample,
                    )
    finally:
        if original is not None:
            with case_step(
                "Restore original CPU frequency",
                definition_id="cpu.frequency.restore",
                expected=f"scaling_cur_freq={original.current_frequency}",
            ):
                restored = dut.restore_cpu_frequency(original)
                step_log(
                    "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq "
                    f"-> {restored} (after restore original={original.current_frequency})"
                )
                assert restored == original.current_frequency, (
                    "Failed to restore original CPU frequency: "
                    f"original={original.current_frequency}, observed={restored}"
                )
