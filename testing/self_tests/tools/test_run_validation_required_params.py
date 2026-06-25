from __future__ import annotations

from pathlib import Path

from testing.params.validation import validate_run_request
from testing.state import models


BT_NODEID = "testing/tests/android/common/wifi_bt/test_bt_onoff.py::test_bt_onoff_scan_via_android_client"
WIFI_NODEID = "testing/tests/android/common/wifi_bt/test_wifi_onoff.py::test_wifi_onoff_scan_via_android_client"


def _issue_keys(state: models.TestPageState) -> list[str]:
    issues = validate_run_request(
        root_dir=Path.cwd(),
        state=state,
        resolved_dut_serial="192.168.1.220:5555",
    )
    return [issue.param_key for issue in issues if issue.code == "missing_required_param"]


def test_bt_onoff_target_none_is_missing_required_param():
    state = models.TestPageState(
        selected=[models.SelectedCase(nodeid=BT_NODEID, case_type="wifi_bt")],
        case_parameters={
            BT_NODEID: {
                "bt_onoff_scan:bt_target": "None",
            }
        },
    )

    assert "bt_onoff_scan:bt_target" in _issue_keys(state)


def test_bt_onoff_target_not_in_current_options_is_missing_required_param():
    state = models.TestPageState(
        selected=[models.SelectedCase(nodeid=BT_NODEID, case_type="wifi_bt")],
        case_parameters={
            BT_NODEID: {
                "bt_onoff_scan:bt_target": "Old Speaker [00:11:22:33:44:55]",
            }
        },
        case_parameter_options={
            BT_NODEID: {
                "bt_onoff_scan:bt_target": ["Current Speaker [AA:BB:CC:DD:EE:FF]"],
            }
        },
    )

    assert "bt_onoff_scan:bt_target" in _issue_keys(state)


def test_bt_onoff_target_in_current_options_is_valid():
    target = "Current Speaker [AA:BB:CC:DD:EE:FF]"
    state = models.TestPageState(
        selected=[models.SelectedCase(nodeid=BT_NODEID, case_type="wifi_bt")],
        case_parameters={
            BT_NODEID: {
                "bt_onoff_scan:bt_target": target,
            }
        },
        case_parameter_options={
            BT_NODEID: {
                "bt_onoff_scan:bt_target": [target],
            }
        },
    )

    assert "bt_onoff_scan:bt_target" not in _issue_keys(state)


def test_wifi_onoff_ping_target_empty_is_missing_required_param():
    state = models.TestPageState(
        selected=[models.SelectedCase(nodeid=WIFI_NODEID, case_type="wifi_bt")],
        case_parameters={
            WIFI_NODEID: {
                "wifi_onoff_scan:ping_target": "",
            }
        },
    )

    assert "wifi_onoff_scan:ping_target" in _issue_keys(state)
