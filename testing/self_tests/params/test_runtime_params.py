from __future__ import annotations

from testing.params.runtime import runtime_params
from ui import jsonTool


def test_runtime_params_reads_case_values_with_schema_types(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    nodeid = "testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress"
    jsonTool.write_json(
        "test_page_state.json",
        {
            "case_parameters": {
                nodeid: {
                    "local_playback_stress:loop_count": "3.0",
                    "local_playback_stress:action_interval_sec": "1.5",
                    "local_playback_stress:random_playback": "true",
                    "local_playback_stress:media_files": "a.mp4, b.mp4",
                }
            }
        },
    )

    params = runtime_params().case_values(nodeid)

    assert params["local_playback_stress:loop_count"] == 3
    assert params["local_playback_stress:action_interval_sec"] == 1.5
    assert params["local_playback_stress:random_playback"] is True
    assert params["local_playback_stress:media_files"] == ["a.mp4", "b.mp4"]


def test_apk_params_serializes_int_values_without_decimal_suffix(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    nodeid = "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"
    jsonTool.write_json(
        "test_page_state.json",
        {
            "case_parameters": {
                nodeid: {
                    "auto_reboot:cycle_count": 3.0,
                    "auto_reboot:interval_sec": "20.0",
                    "auto_reboot:ping_target": "192.168.1.1",
                }
            }
        },
    )

    params = runtime_params().apk_params("auto_reboot", nodeid)

    assert params["auto_reboot:cycle_count"] == "3"
    assert params["auto_reboot:interval_sec"] == "20"
    assert params["auto_reboot:ping_target"] == "192.168.1.1"


def test_normalize_for_key_uses_registry_field_type() -> None:
    assert runtime_params().normalize_for_key("auto_reboot:cycle_count", 3.0) == 3
    assert runtime_params().normalize_for_key("local_playback_stress:media_files", "a.mp4 b.mp4") == [
        "a.mp4",
        "b.mp4",
    ]
