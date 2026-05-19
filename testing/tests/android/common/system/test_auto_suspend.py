from __future__ import annotations

import pytest

from testing.actions import run_android_client_case
from testing.runner.android_client import build_case_params
from testing.runtime import request_case_param


pytestmark = pytest.mark.case_type("system")


SMARTTEST_CASE_PLAN = {
    "case_id": "auto_suspend",
    "steps": [
        {
            "id": "auto_suspend.prepare",
            "title": "Prepare auto suspend request",
            "kind": "setup",
            "definition_id": "android_client.prepare_request",
            "expected": "",
        },
        {
            "id": "auto_suspend.trigger",
            "title": "Trigger auto suspend execution",
            "kind": "step",
            "definition_id": "android_client.trigger_case",
            "expected": "",
        },
        {
            "id": "auto_suspend.cycle.suspend",
            "title": "Cycle: suspend DUT",
            "kind": "step",
            "definition_id": "power.suspend",
            "expected": "",
        },
        {
            "id": "auto_suspend.cycle.resume",
            "title": "Cycle: resume DUT",
            "kind": "step",
            "definition_id": "power.resume",
            "expected": "",
        },
        {
            "id": "auto_suspend.cycle.wait_interval",
            "title": "Cycle: wait interval {auto_suspend:interval_sec}s",
            "kind": "step",
            "definition_id": "power.wait_interval",
            "expected": "",
        },
        {
            "id": "auto_suspend.cycle.capture_radio_state",
            "title": "Cycle: capture radio state",
            "kind": "check",
            "definition_id": "power.capture_radio_state",
            "expected": "",
        },
        {
            "id": "auto_suspend.cycle.ping",
            "title": "Cycle: ping {auto_suspend:ping_target}",
            "kind": "check",
            "definition_id": "network.ping",
            "expected": "",
        },
        {
            "id": "auto_suspend.cycle.bluetooth",
            "title": "Cycle: verify Bluetooth target",
            "kind": "check",
            "definition_id": "bluetooth.verify_target",
            "expected": "",
        },
    ],
}


@pytest.mark.requires_params(
    "auto_suspend:cycle_count",
    "auto_suspend:interval_sec",
    "auto_suspend:ping_target",
    "auto_suspend:bt_target",
)
def test_auto_suspend_via_android_client(request):
    params = build_case_params(
        "auto_suspend",
        cycle_count=request_case_param(request, "auto_suspend:cycle_count", 20, cast=int),
        interval_sec=request_case_param(request, "auto_suspend:interval_sec", 100, cast=int),
        ping_target=request_case_param(request, "auto_suspend:ping_target", ""),
        bt_target=request_case_param(request, "auto_suspend:bt_target", ""),
    )

    run_android_client_case(
        case_id="auto_suspend",
        params=params,
        trigger=request.node.nodeid,
    )
