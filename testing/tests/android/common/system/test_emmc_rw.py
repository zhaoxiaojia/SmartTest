from __future__ import annotations

import pytest

from testing.runner.android_client import build_case_params, trigger_android_client_case
from testing.runtime import action_step, case_step, request_case_param, step_log


pytestmark = pytest.mark.case_type("system")


@pytest.mark.requires_params(
    "emmc_rw:loop_count",
    "emmc_rw:source_profile",
    "emmc_rw:source_size_kb",
    "emmc_rw:min_free_kb",
    "emmc_rw:work_dir",
)
def test_emmc_rw_via_android_client(request):
    params = build_case_params(
        "emmc_rw",
        loop_count=request_case_param(request, "emmc_rw:loop_count", 180, cast=int),
        source_profile=request_case_param(request, "emmc_rw:source_profile", "random1"),
        source_size_kb=request_case_param(request, "emmc_rw:source_size_kb", 51200, cast=int),
        min_free_kb=request_case_param(request, "emmc_rw:min_free_kb", 307200, cast=int),
        work_dir=request_case_param(request, "emmc_rw:work_dir", "/data/local/tmp/smarttest/emmc_rw"),
    )

    with case_step(
        "Prepare eMMC read/write request",
        definition_id="storage.emmc.prepare_request",
        meta={"case_id": "emmc_rw"},
    ):
        summary = ", ".join(f"{key.split(':', 1)[-1]}={value}" for key, value in params.items())
        step_log(summary)

    with case_step(
        "Trigger eMMC read/write execution",
        definition_id="storage.emmc.trigger_execution",
        meta={"case_id": "emmc_rw"},
    ):
        with action_step(
            "Trigger android_client case: emmc_rw",
            definition_id="android_client.trigger_case",
        ):
            result = trigger_android_client_case(
                case_id="emmc_rw",
                params=params,
                trigger=request.node.nodeid,
            )
            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            if stdout:
                step_log(stdout)
            if stderr:
                step_log(stderr, level="warning")
