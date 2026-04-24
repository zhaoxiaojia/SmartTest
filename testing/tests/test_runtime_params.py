from __future__ import annotations

import json

from testing.runtime.params import case_config, case_param, request_case_param


class _Request:
    class _Node:
        nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"

    node = _Node()


def test_case_param_reads_selected_case_config(monkeypatch) -> None:
    monkeypatch.setenv(
        "SMARTTEST_CASE_CONFIGS_JSON",
        json.dumps(
            {
                "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client": {
                    "emmc_rw:loop_count": "360",
                    "emmc_rw:work_dir": "/tmp/emmc",
                }
            }
        ),
    )

    assert case_param(_Request.node.nodeid, "emmc_rw:loop_count", 180, cast=int) == 360
    assert case_param(_Request.node.nodeid, "emmc_rw:work_dir", "") == "/tmp/emmc"
    assert request_case_param(_Request(), "emmc_rw:loop_count", 180, cast=int) == 360
    assert case_config(_Request.node.nodeid)["emmc_rw:work_dir"] == "/tmp/emmc"


def test_case_param_returns_default_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("SMARTTEST_CASE_CONFIGS_JSON", raising=False)

    assert case_param("missing::case", "emmc_rw:loop_count", 180, cast=int) == 180
