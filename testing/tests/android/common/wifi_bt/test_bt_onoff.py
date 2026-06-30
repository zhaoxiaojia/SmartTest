from __future__ import annotations

import pytest

from testing.runner.apk_client import run_apk_case


pytestmark = [pytest.mark.case_type("wifi_bt"), pytest.mark.stress]


SMARTTEST_CASE_PLAN = {
    "case_id": "bt_onoff_scan",
    "steps": [
        {
            "id": "bt_onoff_scan.prepare",
            "title": "Prepare Bluetooth on/off request",
            "kind": "setup",
            "definition_id": "android_client.prepare_request",
            "expected": "",
        },
        {
            "id": "bt_onoff_scan.trigger",
            "title": "Trigger Bluetooth on/off execution",
            "kind": "step",
            "definition_id": "android_client.trigger_case",
            "expected": "",
        },
        {
            "id": "bt_onoff_scan.cycle.disable",
            "title": "Cycle: disable Bluetooth",
            "kind": "step",
            "definition_id": "radio.bluetooth.disable",
            "expected": "",
        },
        {
            "id": "bt_onoff_scan.cycle.enable",
            "title": "Cycle: enable Bluetooth",
            "kind": "step",
            "definition_id": "radio.bluetooth.enable",
            "expected": "",
        },
        {
            "id": "bt_onoff_scan.cycle.capture_radio_state",
            "title": "Cycle: capture radio state",
            "kind": "check",
            "definition_id": "power.capture_radio_state",
            "expected": "",
        },
        {
            "id": "bt_onoff_scan.cycle.bluetooth",
            "title": "Cycle: verify Bluetooth target",
            "kind": "check",
            "definition_id": "bluetooth.verify_target",
            "expected": "",
        },
    ],
}


@pytest.mark.requires_params(
    "bt_onoff_scan:cycle_count",
    "bt_onoff_scan:on_wait_sec",
    "bt_onoff_scan:off_wait_sec",
    "bt_onoff_scan:bt_target",
)
def test_bt_onoff_scan_via_android_client(request):
    run_apk_case(
        case_id="bt_onoff_scan",
        trigger=request.node.nodeid,
    )

