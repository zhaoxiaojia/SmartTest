from __future__ import annotations

import pytest

from testing.actions import run_android_client_case
from testing.runner.android_client import build_case_params
from testing.runtime import request_case_param


pytestmark = pytest.mark.case_type("wifi_bt")


SMARTTEST_CASE_PLAN = {
    "case_id": "wifi_onoff_scan",
    "steps": [
        {
            "id": "wifi_onoff_scan.prepare",
            "title": "Prepare Wi-Fi on/off request",
            "kind": "setup",
            "definition_id": "android_client.prepare_request",
            "expected": "",
        },
        {
            "id": "wifi_onoff_scan.trigger",
            "title": "Trigger Wi-Fi on/off execution",
            "kind": "step",
            "definition_id": "android_client.trigger_case",
            "expected": "",
        },
        {
            "id": "wifi_onoff_scan.cycle.disable",
            "title": "Cycle: disable Wi-Fi",
            "kind": "step",
            "definition_id": "radio.wifi.disable",
            "expected": "",
        },
        {
            "id": "wifi_onoff_scan.cycle.enable",
            "title": "Cycle: enable Wi-Fi",
            "kind": "step",
            "definition_id": "radio.wifi.enable",
            "expected": "",
        },
        {
            "id": "wifi_onoff_scan.cycle.capture_radio_state",
            "title": "Cycle: capture radio state",
            "kind": "check",
            "definition_id": "power.capture_radio_state",
            "expected": "",
        },
        {
            "id": "wifi_onoff_scan.cycle.ping",
            "title": "Cycle: ping {wifi_onoff_scan:ping_target}",
            "kind": "check",
            "definition_id": "network.ping",
            "expected": "",
        },
    ],
}


@pytest.mark.wifi
@pytest.mark.requires_params(
    "wifi_onoff_scan:cycle_count",
    "wifi_onoff_scan:ping_target",
)
def test_wifi_onoff_scan_via_android_client(request):
    run_android_client_case(
        case_id="wifi_onoff_scan",
        params=build_case_params(
            "wifi_onoff_scan",
            cycle_count=request_case_param(request, "wifi_onoff_scan:cycle_count", 2, cast=int),
            ping_target=request_case_param(request, "wifi_onoff_scan:ping_target", ""),
        ),
        trigger=request.node.nodeid,
    )
