from __future__ import annotations

import pytest

from testing.runner.android_client import run_android_client_case


pytestmark = pytest.mark.case_type("system")


SMARTTEST_CASE_PLAN = {
    "case_id": "auto_reboot",
    "steps": [
        {
            "id": "auto_reboot.prepare",
            "title": "Prepare auto reboot request",
            "kind": "setup",
            "definition_id": "android_client.prepare_request",
            "expected": "",
        },
        {
            "id": "auto_reboot.trigger",
            "title": "Trigger auto reboot execution",
            "kind": "step",
            "definition_id": "android_client.trigger_case",
            "expected": "",
        },
        {
            "id": "auto_reboot.cycle.reboot",
            "title": "Cycle: reboot DUT",
            "kind": "step",
            "definition_id": "power.reboot",
            "expected": "",
        },
        {
            "id": "auto_reboot.cycle.wait_resume",
            "title": "Cycle: wait for DUT resume",
            "kind": "step",
            "definition_id": "power.wait_resume",
            "expected": "",
        },
        {
            "id": "auto_reboot.cycle.wait_interval",
            "title": "Cycle: wait interval {auto_reboot:interval_sec}s",
            "kind": "step",
            "definition_id": "power.wait_interval",
            "expected": "",
        },
        {
            "id": "auto_reboot.cycle.capture_radio_state",
            "title": "Cycle: capture radio state",
            "kind": "check",
            "definition_id": "power.capture_radio_state",
            "expected": "",
        },
        {
            "id": "auto_reboot.cycle.ping",
            "title": "Cycle: ping {auto_reboot:ping_target}",
            "kind": "check",
            "definition_id": "network.ping",
            "expected": "",
        },
        {
            "id": "auto_reboot.cycle.bluetooth",
            "title": "Cycle: verify Bluetooth target",
            "kind": "check",
            "definition_id": "bluetooth.verify_target",
            "expected": "",
        },
    ],
}


@pytest.mark.requires_params(
    "auto_reboot:cycle_count",
    "auto_reboot:interval_sec",
    "auto_reboot:ping_target",
    "auto_reboot:bt_target",
)
def test_auto_reboot_via_android_client(request):
    run_android_client_case(
        case_id="auto_reboot",
        trigger=request.node.nodeid,
    )
