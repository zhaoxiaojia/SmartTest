from __future__ import annotations

from testing.test_context import ParameterStore
from testing.params.registry import default_registry
from ui import jsonTool


def test_radio_onoff_wait_parameters_are_registered_for_frontend() -> None:
    registry = default_registry()

    for key in (
        "wifi_onoff_scan:on_wait_sec",
        "wifi_onoff_scan:off_wait_sec",
        "bt_onoff_scan:on_wait_sec",
        "bt_onoff_scan:off_wait_sec",
    ):
        field = registry.get_param(key)
        assert field is not None
        assert field.default == 5


def test_wifi_onoff_wait_parameters_are_sent_to_apk(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    nodeid = "testing/tests/android/common/wifi_bt/test_wifi_onoff.py::test_wifi_onoff_scan_via_android_client"
    jsonTool.write_json(
        "test_page_state.json",
        {
            "case_parameters": {
                nodeid: {
                    "wifi_onoff_scan:cycle_count": 2,
                    "wifi_onoff_scan:ping_target": "192.168.1.1",
                    "wifi_onoff_scan:on_wait_sec": 20,
                    "wifi_onoff_scan:off_wait_sec": 7,
                }
            }
        },
    )

    params = ParameterStore().apk_params("wifi_onoff_scan", nodeid)

    assert params["wifi_onoff_scan:on_wait_sec"] == "20"
    assert params["wifi_onoff_scan:off_wait_sec"] == "7"


def test_bt_onoff_wait_parameters_are_sent_to_apk(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    nodeid = "testing/tests/android/common/wifi_bt/test_bt_onoff.py::test_bt_onoff_scan_via_android_client"
    jsonTool.write_json(
        "test_page_state.json",
        {
            "case_parameters": {
                nodeid: {
                    "bt_onoff_scan:cycle_count": 2,
                    "bt_onoff_scan:bt_target": "AA:BB:CC:DD:EE:FF",
                    "bt_onoff_scan:on_wait_sec": 20,
                    "bt_onoff_scan:off_wait_sec": 7,
                }
            }
        },
    )

    params = ParameterStore().apk_params("bt_onoff_scan", nodeid)

    assert params["bt_onoff_scan:on_wait_sec"] == "20"
    assert params["bt_onoff_scan:off_wait_sec"] == "7"
