from __future__ import annotations

import pytest

from testing.actions.cpu_frequency import (
    CpuFrequencyController,
    CpuFrequencySnapshot,
)
from testing.params.options import normalize_option_values
from testing.params.registry import CPU_FREQUENCY_PARAM_KEY
from testing.runtime import case_step, request_case_param, step_log


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
            "expected": "Original governor and current frequency are captured before switching.",
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


@pytest.mark.requires_params(CPU_FREQUENCY_PARAM_KEY)
def test_cpu_frequency_switching(request):
    selected_frequencies = normalize_option_values(
        request_case_param(request, CPU_FREQUENCY_PARAM_KEY, [])
    )
    controller = CpuFrequencyController.from_environment()
    original: CpuFrequencySnapshot | None = None

    with case_step(
        "Read available CPU frequencies",
        definition_id="cpu.frequency.read_available",
        params={CPU_FREQUENCY_PARAM_KEY: selected_frequencies},
        expected="DUT returns selectable CPU frequency values.",
    ):
        available_frequencies = controller.available_frequencies()
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
        expected="Original governor and current frequency are captured before switching.",
    ):
        controller.ensure_root()
        original = controller.snapshot()
        step_log(
            "original_governor="
            f"{original.governor} original_current_frequency={original.current_frequency}"
        )

    try:
        total = len(selected_frequencies)
        for index, target_frequency in enumerate(selected_frequencies, start=1):
            with case_step(
                f"Set CPU frequency {target_frequency} ({index}/{total})",
                definition_id="cpu.frequency.set",
                params={
                    CPU_FREQUENCY_PARAM_KEY: selected_frequencies,
                    "target_frequency": target_frequency,
                    "index": index,
                    "total": total,
                },
                expected=f"scaling_cur_freq={target_frequency}",
            ):
                current_before = controller.read_current_frequency()
                step_log(
                    f"before={current_before} target={target_frequency} "
                    f"index={index}/{total}"
                )
                controller.set_frequency(target_frequency)
                observed = controller.wait_current_frequency(target_frequency)
                step_log(f"after={observed} target={target_frequency}")
                assert observed == target_frequency, (
                    f"CPU frequency switch failed: target={target_frequency}, observed={observed}"
                )
    finally:
        if original is not None:
            with case_step(
                "Restore original CPU frequency",
                definition_id="cpu.frequency.restore",
                params={"original_frequency": original.current_frequency},
                expected=f"scaling_cur_freq={original.current_frequency}",
            ):
                restored = controller.restore(original)
                step_log(
                    f"restored={restored} original={original.current_frequency} "
                    f"governor={original.governor}"
                )
                assert restored == original.current_frequency, (
                    "Failed to restore original CPU frequency: "
                    f"original={original.current_frequency}, observed={restored}"
                )
