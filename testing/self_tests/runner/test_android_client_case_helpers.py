from __future__ import annotations

import subprocess

from testing.runner import android_client
from ui import jsonTool


def test_android_client_case_plan_builds_steps_from_step_definitions() -> None:
    plan = android_client.android_client_case_plan(
        "emmc_rw",
        ["storage.emmc.copy_file", "storage.emmc.cmp_file"],
    )

    assert plan["case_id"] == "emmc_rw"
    assert [step["definition_id"] for step in plan["steps"]] == [
        "android_client.prepare_request",
        "android_client.trigger_case",
        "storage.emmc.copy_file",
        "storage.emmc.cmp_file",
    ]


def test_run_android_client_case_loads_params_from_json_and_triggers_runner(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"
    jsonTool.write_json(
        "test_page_state.json",
        {"case_parameters": {nodeid: {"emmc_rw:loop_count": 2}}},
    )
    calls: list[tuple[str, dict[str, object], str]] = []

    def fake_trigger_android_client_case(*, case_id, params, trigger):  # noqa: ANN001
        calls.append((case_id, dict(params), trigger))
        return subprocess.CompletedProcess(["adb"], 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(android_client, "trigger_android_client_case", fake_trigger_android_client_case)

    result = android_client.run_android_client_case(
        case_id="emmc_rw",
        trigger=nodeid,
    )

    assert result.returncode == 0
    assert calls[0][0] == "emmc_rw"
    assert calls[0][1]["emmc_rw:loop_count"] == "2"
    assert calls[0][2] == nodeid
