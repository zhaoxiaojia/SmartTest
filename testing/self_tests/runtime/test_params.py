from __future__ import annotations

from testing.params.runtime import runtime_params
from ui import jsonTool


def test_case_parameters_are_plain_json_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"
    jsonTool.write_json(
        "test_page_state.json",
        {
            "case_parameters": {
                nodeid: {
                    "emmc_rw:loop_count": "360",
                    "emmc_rw:work_dir": "/tmp/emmc",
                }
            }
        },
    )

    params = runtime_params()

    assert params.get_int(nodeid, "emmc_rw:loop_count", 180) == 360
    assert params.get_str(nodeid, "emmc_rw:work_dir", "") == "/tmp/emmc"
