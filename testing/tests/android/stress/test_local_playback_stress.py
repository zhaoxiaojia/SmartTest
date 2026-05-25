from __future__ import annotations

from typing import Any

import pytest

from testing.actions.local_playback import DEFAULT_MEDIA_DIR, run_local_playback_stress
from testing.runtime import request_case_param, step
from testing.runtime.config import current_dut_serial


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

    params = _case_params(request)
    with step(
        "Prepare local playback stress configuration",
        phase="setup",
        kind="setup",
        definition_id="local_playback.prepare",
        params=params,
        expected="DUT, playback files, actions, and loop settings are available.",
        step_id="local_playback_stress.prepare",
    ):
        if not params["local_playback_stress:actions"]:
            pytest.fail("Select at least one local playback stress action.")

    with step(
        "Run local playback stress loop",
        kind="step",
        definition_id="local_playback.loop",
        params=params,
        expected="ExoPlayer starts each selected local file and receives the selected stress actions.",
        step_id="local_playback_stress.loop",
    ):
        run_local_playback_stress(
            params=params,
            selected_serial=selected_serial,
            trigger=request.node.nodeid,
        )


def _case_params(request) -> dict[str, Any]:
    return {
        "local_playback_stress:media_dir": request_case_param(
            request,
            "local_playback_stress:media_dir",
            DEFAULT_MEDIA_DIR,
        ),
        "local_playback_stress:media_files": request_case_param(
            request,
            "local_playback_stress:media_files",
            [],
        ),
        "local_playback_stress:actions": request_case_param(
            request,
            "local_playback_stress:actions",
            ["pause", "play", "seek_forward", "seek_backward"],
        ),
        "local_playback_stress:loop_count": max(
            request_case_param(request, "local_playback_stress:loop_count", 20, cast=int),
            1,
        ),
        "local_playback_stress:random_playback": bool(
            request_case_param(request, "local_playback_stress:random_playback", False),
        ),
        "local_playback_stress:action_interval_sec": max(
            request_case_param(request, "local_playback_stress:action_interval_sec", 3, cast=float),
            0,
        ),
        "local_playback_stress:start_wait_sec": max(
            request_case_param(request, "local_playback_stress:start_wait_sec", 10, cast=float),
            0,
        ),
    }
