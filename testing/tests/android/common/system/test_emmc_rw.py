from __future__ import annotations

import pytest

from testing.runner.apk_client import apk_case_plan, run_apk_case


pytestmark = pytest.mark.case_type("system")


SMARTTEST_CASE_PLAN = apk_case_plan(
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
    run_apk_case(
        case_id="emmc_rw",
        trigger=request.node.nodeid,
        prepare_definition_id="storage.emmc.prepare_request",
        trigger_definition_id="storage.emmc.trigger_execution",
    )

