from __future__ import annotations

import pytest

from testing.actions import android_client_case_plan, run_android_client_case
from testing.runner.android_client import build_case_params
from testing.runtime import request_case_param


pytestmark = pytest.mark.case_type("system")


SMARTTEST_CASE_PLAN = android_client_case_plan(
    "emmc_rw",
    [
        "storage.emmc.copy_file",
        "storage.emmc.read_file",
        "storage.emmc.cmp_file",
    ],
    prepare_definition_id="storage.emmc.prepare_request",
    trigger_definition_id="storage.emmc.trigger_execution",
)


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

    run_android_client_case(
        case_id="emmc_rw",
        params=params,
        trigger=request.node.nodeid,
        prepare_definition_id="storage.emmc.prepare_request",
        trigger_definition_id="storage.emmc.trigger_execution",
    )
