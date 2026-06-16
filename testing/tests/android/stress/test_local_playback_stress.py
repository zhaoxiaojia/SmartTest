from __future__ import annotations

import pytest

from testing.runtime.config import current_dut_serial
from testing.runtime.steps import step
from testing.tool.dut_tool.duts.android import android
from testing.tool.dut_tool.features.local_playback import run_local_playback_stress


pytestmark = pytest.mark.case_type("stress")

CASE_ID = "local_playback_stress"

SMARTTEST_CASE_PLAN = {
    "case_id": CASE_ID,
    "steps": [
        {
            "id": "local_playback_stress.prepare",
            "title": "Prepare local playback stress configuration",
            "kind": "setup",
            "definition_id": "local_playback.prepare",
            "expected": "DUT, playback files, actions, and loop settings are available.",
        },
        {
            "id": "local_playback_stress.stop_player",
            "title": "Stop existing ExoPlayer session",
            "kind": "setup",
            "definition_id": "local_playback.stop_player",
            "expected": "Any existing ExoPlayer playback page is closed before starting the stress loop.",
        },
        {
            "id": "local_playback_stress.loop",
            "title": "Run local playback stress loop",
            "kind": "step",
            "definition_id": "local_playback.loop",
            "expected": "ExoPlayer starts each selected local file and receives the selected stress actions.",
        },
    ],
}


@pytest.mark.requires_params(
    "local_playback_stress:media_dir",
    "local_playback_stress:media_files",
    "local_playback_stress:actions",
    "local_playback_stress:loop_count",
    "local_playback_stress:random_playback",
    "local_playback_stress:action_interval_sec",
    "local_playback_stress:start_wait_sec",
)
def test_local_playback_stress(request):
    selected_serial = current_dut_serial()
    if not selected_serial:
        pytest.fail("Select a DUT before running local playback stress.")

    with step(
        "Prepare local playback stress configuration",
        phase="setup",
        kind="setup",
        definition_id="local_playback.prepare",
        expected="DUT, playback files, actions, and loop settings are available.",
        step_id="local_playback_stress.prepare",
    ):
        pass

    with step(
        "Stop existing ExoPlayer session",
        phase="setup",
        kind="setup",
        definition_id="local_playback.stop_player",
        expected="Any existing ExoPlayer playback page is closed before starting the stress loop.",
        step_id="local_playback_stress.stop_player",
    ):
        android(serialnumber=selected_serial).stop_player()

    with step(
        "Run local playback stress loop",
        kind="step",
        definition_id="local_playback.loop",
        expected="ExoPlayer starts each selected local file and receives the selected stress actions.",
        step_id="local_playback_stress.loop",
    ):
        run_local_playback_stress(
            nodeid=request.node.nodeid,
            selected_serial=selected_serial,
            trigger=request.node.nodeid,
        )
