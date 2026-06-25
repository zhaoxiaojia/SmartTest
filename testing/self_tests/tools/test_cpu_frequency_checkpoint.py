from __future__ import annotations

import pytest

from testing.tool.dut_tool.features.system import verify_cpu_frequency_samples


def test_cpu_frequency_checkpoint_reads_ten_matching_samples() -> None:
    samples = verify_cpu_frequency_samples("500000", lambda: "500000")

    assert samples == ["500000"] * 10


def test_cpu_frequency_checkpoint_fails_on_first_mismatched_sample() -> None:
    values = iter(["500000", "500000", "2208000", "500000"])

    with pytest.raises(AssertionError, match="sample 3/10"):
        verify_cpu_frequency_samples("500000", lambda: next(values))
