from __future__ import annotations

from pathlib import Path

from testing.params.validation import validate_run_request
from testing.state.models import SelectedCase, TestPageState


LOCAL_PLAYBACK_NODEID = "testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress"
AC_ONOFF_NODEID = "testing/tests/android/stress/test_ac_onoff.py::test_ac_onoff_via_relay"


def _case(nodeid: str, required_params: list[str]) -> dict[str, object]:
    return {
        "nodeid": nodeid,
        "file": nodeid.split("::", 1)[0],
        "name": nodeid.rsplit("::", 1)[-1],
        "case_type": "stress",
        "required_params": required_params,
        "required_param_groups": [],
        "required_equipment": [],
        "android_case_id": "",
    }


def _android_case(nodeid: str, android_case_id: str, required_params: list[str]) -> dict[str, object]:
    row = _case(nodeid, required_params)
    row["android_case_id"] = android_case_id
    return row


def test_validate_run_request_blocks_android_case_without_selected_dut() -> None:
    state = TestPageState(
        selected=[SelectedCase(nodeid=LOCAL_PLAYBACK_NODEID, case_type="stress")],
        case_parameters={
            LOCAL_PLAYBACK_NODEID: {
                "local_playback_stress:media_files": ["/storage/emulated/0/Movies/movie.mp4"],
            }
        },
        global_context={"dut": ""},
    )

    issues = validate_run_request(
        root_dir=Path.cwd(),
        state=state,
        catalog=[
            _case(
                LOCAL_PLAYBACK_NODEID,
                ["local_playback_stress:media_files"],
            )
        ],
        device_lister=lambda: [],
    )

    assert [(issue.code, issue.param_key) for issue in issues] == [("missing_dut", "dut")]


def test_validate_run_request_blocks_empty_required_case_parameter() -> None:
    state = TestPageState(
        selected=[SelectedCase(nodeid=LOCAL_PLAYBACK_NODEID, case_type="stress")],
        case_parameters={LOCAL_PLAYBACK_NODEID: {"local_playback_stress:media_files": []}},
        global_context={"dut": "ABC123"},
    )

    issues = validate_run_request(
        root_dir=Path.cwd(),
        state=state,
        catalog=[
            _case(
                LOCAL_PLAYBACK_NODEID,
                ["local_playback_stress:media_files"],
            )
        ],
        device_lister=lambda: ["ABC123"],
    )

    assert [(issue.code, issue.param_key) for issue in issues] == [
        ("missing_required_param", "local_playback_stress:media_files")
    ]


def test_validate_run_request_blocks_empty_required_text_parameter() -> None:
    state = TestPageState(
        selected=[SelectedCase(nodeid=LOCAL_PLAYBACK_NODEID, case_type="stress")],
        case_parameters={
            LOCAL_PLAYBACK_NODEID: {
                "local_playback_stress:media_dir": "",
                "local_playback_stress:media_files": ["/storage/emulated/0/Movies/movie.mp4"],
                "local_playback_stress:action_interval_sec": 3,
                "local_playback_stress:start_wait_sec": 10,
            }
        },
        global_context={"dut": "ABC123"},
    )

    issues = validate_run_request(
        root_dir=Path.cwd(),
        state=state,
        catalog=[
            _case(
                LOCAL_PLAYBACK_NODEID,
                [
                    "local_playback_stress:media_dir",
                    "local_playback_stress:media_files",
                    "local_playback_stress:action_interval_sec",
                    "local_playback_stress:start_wait_sec",
                ],
            )
        ],
        device_lister=lambda: ["ABC123"],
    )

    assert [(issue.code, issue.param_key) for issue in issues] == [
        ("missing_required_param", "local_playback_stress:media_dir")
    ]


def test_validate_run_request_uses_yaml_required_case_parameters(tmp_path, monkeypatch) -> None:
    from testing.params import requirements

    required_path = tmp_path / "required_params.yaml"
    required_path.write_text(
        "\n".join(
            [
                "cases:",
                "  test_ac_onoff_via_relay:",
                "    required:",
                "      - ac_onoff:ping_target",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(requirements, "REQUIRED_PARAMS_PATH", required_path)
    requirements.load_required_case_params.cache_clear()

    state = TestPageState(
        selected=[SelectedCase(nodeid=AC_ONOFF_NODEID, case_type="stress")],
        case_parameters={AC_ONOFF_NODEID: {"ac_onoff:ping_target": "", "ac_onoff:bt_target": ""}},
        global_context={"dut": "ABC123"},
    )

    issues = validate_run_request(
        root_dir=Path.cwd(),
        state=state,
        catalog=[
            _case(
                AC_ONOFF_NODEID,
                ["ac_onoff:ping_target", "ac_onoff:bt_target"],
            )
        ],
        device_lister=lambda: ["ABC123"],
    )

    requirements.load_required_case_params.cache_clear()

    assert [(issue.code, issue.param_key) for issue in issues] == [
        ("missing_required_param", "ac_onoff:ping_target")
    ]


def test_validate_run_request_accepts_legacy_android_selected_case_parameter_key() -> None:
    nodeid = "testing/tests/android/common/system/test_cpu_frequency.py::test_cpu_frequency_switching"
    state = TestPageState(
        selected=[SelectedCase(nodeid="android://cpu_frequency", case_type="common")],
        case_parameters={"android://cpu_frequency": {"cpu_frequency:frequencies": ["1000000"]}},
        global_context={"dut": "ABC123"},
    )

    issues = validate_run_request(
        root_dir=Path.cwd(),
        state=state,
        catalog=[_android_case(nodeid, "cpu_frequency", ["cpu_frequency:frequencies"])],
        device_lister=lambda: ["ABC123"],
    )

    assert issues == []


def test_validate_run_request_allows_empty_optional_case_parameter() -> None:
    state = TestPageState(
        selected=[SelectedCase(nodeid=AC_ONOFF_NODEID, case_type="stress")],
        case_parameters={AC_ONOFF_NODEID: {"ac_onoff:ping_target": "", "ac_onoff:bt_target": ""}},
        global_context={"dut": "ABC123"},
    )

    issues = validate_run_request(
        root_dir=Path.cwd(),
        state=state,
        catalog=[
            _case(
                AC_ONOFF_NODEID,
                ["ac_onoff:ping_target", "ac_onoff:bt_target"],
            )
        ],
        device_lister=lambda: ["ABC123"],
    )

    assert issues == []
