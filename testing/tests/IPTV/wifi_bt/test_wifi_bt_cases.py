from __future__ import annotations

import os

import pytest

from testing.runner.android_client import build_case_params, trigger_android_client_case


pytestmark = pytest.mark.case_type("wifi_bt")


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


@pytest.mark.wifi
def test_wifi_power_reconnect_via_android_client(request):
    trigger_android_client_case(case_id="wifi_power_reconnect", trigger=request.node.nodeid)


@pytest.mark.wifi
def test_wifi_reboot_reconnect_via_android_client(request):
    trigger_android_client_case(case_id="wifi_reboot_reconnect", trigger=request.node.nodeid)


@pytest.mark.wifi
@pytest.mark.requires_params("wifi_onoff_scan:cycle_count")
def test_wifi_onoff_scan_via_android_client(request):
    trigger_android_client_case(
        case_id="wifi_onoff_scan",
        params=build_case_params(
            "wifi_onoff_scan",
            cycle_count=_env_int("SMARTTEST_WIFI_ONOFF_CYCLE_COUNT", 2),
        ),
        trigger=request.node.nodeid,
    )


def test_bt_power_reconnect_via_android_client(request):
    trigger_android_client_case(case_id="bt_power_reconnect", trigger=request.node.nodeid)


def test_bt_reboot_via_android_client(request):
    trigger_android_client_case(case_id="bt_reboot", trigger=request.node.nodeid)


@pytest.mark.requires_params("bt_onoff_scan:cycle_count")
def test_bt_onoff_scan_via_android_client(request):
    trigger_android_client_case(
        case_id="bt_onoff_scan",
        params=build_case_params(
            "bt_onoff_scan",
            cycle_count=_env_int("SMARTTEST_BT_ONOFF_CYCLE_COUNT", 2),
        ),
        trigger=request.node.nodeid,
    )
