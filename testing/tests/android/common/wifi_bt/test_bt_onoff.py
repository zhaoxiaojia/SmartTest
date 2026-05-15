from __future__ import annotations

import pytest

from testing.runner.android_client import build_case_params, trigger_android_client_case
from testing.runtime import request_case_param


pytestmark = pytest.mark.case_type("wifi_bt")


SMARTTEST_CASE_PLAN = {
    "case_id": "bt_onoff_scan",
    "steps": [
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
            "definition_id": "bluetooth.required_verify_target",
            "expected": "",
        },
    ],
}


@pytest.mark.requires_params(
    "bt_onoff_scan:cycle_count",
    "bt_onoff_scan:bt_target",
)
def test_bt_onoff_scan_via_android_client(request):
    trigger_android_client_case(
        case_id="bt_onoff_scan",
        params=build_case_params(
            "bt_onoff_scan",
            cycle_count=request_case_param(request, "bt_onoff_scan:cycle_count", 2, cast=int),
            bt_target=request_case_param(request, "bt_onoff_scan:bt_target", ""),
        ),
        trigger=request.node.nodeid,
    )
