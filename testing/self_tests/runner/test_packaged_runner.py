from __future__ import annotations

from testing.runner.packaged import _android_case_params


def test_packaged_runner_formats_integral_float_params_for_android_client() -> None:
    params = _android_case_params(
        android_case_id="emmc_rw",
        values={
            "emmc_rw:loop_count": 3.0,
            "emmc_rw:source_profile": "random1",
            "auto_reboot:cycle_count": 2.0,
        },
    )

    assert params == {
        "emmc_rw:loop_count": "3",
        "emmc_rw:source_profile": "random1",
    }
