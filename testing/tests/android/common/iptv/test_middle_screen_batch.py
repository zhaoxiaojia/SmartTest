from __future__ import annotations

import pytest

from testing.runtime.config import current_dut_serial
from testing.runtime.steps import step, step_log
from testing.test_context import smarttest_context
from testing.tests.android.common.iptv.middle_screen_cases import MIDDLE_SCREEN_CASES
from testing.tool.dut_tool.duts.android import android
from testing.tool.dut_tool.features.iptv_middle_screen import execute_middle_screen_case


pytestmark = pytest.mark.case_type("iptv_middle_screen")

SMARTTEST_CASE_PLAN = {
    "case_id": "iptv_middle_screen",
    "steps": [item for case in MIDDLE_SCREEN_CASES for item in (
        {"id": f"iptv.source.{case.source_id:03d}",
         "title": f"Source {case.source_id}: preserve workbook identity and manual prerequisites",
         "kind": "setup", "definition_id": f"iptv.{case.source_id:03d}.source",
         "expected": f"{case.source_file} / {case.source_sheet} / row {case.source_row}; manual prerequisites: {case.pre_actions or ('none',)}"},
        *({"id": f"iptv.{case.source_id:03d}.action.{index}",
           "title": f"Source {case.source_id} action {index}: {step_title}", "kind": "action",
           "definition_id": f"iptv.{case.source_id:03d}.action.{index}", "expected": "Action completes."}
          for index, step_title in enumerate(case.steps, 1)),
        *({"id": checkpoint.definition_id, "title": f"Source {case.source_id} checkpoint {index}",
           "kind": "check", "definition_id": checkpoint.definition_id, "expected": checkpoint.expected}
          for index, checkpoint in enumerate(case.checkpoints, 1)),
    )],
}


CASE_PARAMETERS = tuple(
    pytest.param(source_case, id=source_case.pytest_id,
                 marks=pytest.mark.requires_params(*source_case.parameters))
    for source_case in MIDDLE_SCREEN_CASES
)


@pytest.mark.parametrize("source_case", CASE_PARAMETERS)
def test_iptv_middle_screen_source_case(request, source_case):
    serial = current_dut_serial()
    if not serial:
        pytest.fail("Select a DUT before running an IPTV middle-screen case.")
    params = smarttest_context().params.case_values(request.node.nodeid)
    evidence = {
        "source_file": source_case.source_file,
        "source_sheet": source_case.source_sheet,
        "source_row": source_case.source_row,
        "manual_prerequisites": source_case.pre_actions,
        "manual_boundaries": source_case.manual_boundaries,
        "source_id": source_case.source_id,
        "case_nodeid": request.node.nodeid,
    }
    step_log("iptv.middle_screen.source", extra=evidence)
    with step(
        source_case.title,
        kind="check",
        definition_id=f"iptv.{source_case.source_id:03d}.execute",
        expected="; ".join(checkpoint.expected for checkpoint in source_case.checkpoints),
        step_id=f"iptv.source.{source_case.source_id:03d}",
    ):
        execute_middle_screen_case(source_case, android(serialnumber=serial), params, serial=serial)
