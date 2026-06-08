from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ui"))

from testing.params.validation import RunValidationIssue
from testing.state.models import SelectedCase, TestPageState as SmartTestPageState
from testing.state.store import save_state
from ui.example import main as example_main
from ui.example.bridge.RunBridge import RunBridge


def test_ui_runtime_root_uses_pyinstaller_meipass(monkeypatch) -> None:
    monkeypatch.setattr(example_main.sys, "_MEIPASS", "C:/Program Files/SmartTest", raising=False)

    assert example_main._runtime_root() == Path("C:/Program Files/SmartTest")


def test_run_bridge_toggle_updates_shared_running_state() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    observed: list[bool] = []
    bridge.runningChanged.connect(lambda: observed.append(bridge.isRunning))

    assert bridge.isRunning is False

    bridge._set_running(True)
    assert bridge.isRunning is True

    bridge._set_running(False)
    assert bridge.isRunning is False

    bridge._set_running(True)
    assert bridge.isRunning is True
    assert observed == [True, False, True]


def test_run_bridge_resolves_single_connected_device_when_saved_dut_is_stale(monkeypatch) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    monkeypatch.setattr("testing.runner.config.list_adb_devices", lambda: ["R58N123ABC"])

    assert bridge._resolve_adb_serial("aaaa") == "R58N123ABC"


def test_run_bridge_keeps_saved_device_when_it_exists(monkeypatch) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    monkeypatch.setattr("testing.runner.config.list_adb_devices", lambda: ["ABC123", "XYZ789"])

    assert bridge._resolve_adb_serial("XYZ789") == "XYZ789"


def test_run_bridge_stop_uses_session_stop() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())

    class _Session:
        def __init__(self) -> None:
            self.reasons: list[str] = []

        def stop(self, reason: str = "UI stop button") -> None:
            self.reasons.append(reason)

    session = _Session()
    bridge._session = session
    bridge._set_running(True)

    bridge.stopRun()

    assert session.reasons == ["UI stop button"]


def test_run_bridge_finish_clears_running_even_when_report_save_fails(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._begin_report_context(nodeids=["android://emmc_rw"], adb_serial="ABC123")
    bridge._set_running(True)
    monkeypatch.setattr(bridge._report_store, "save", lambda report: (_ for _ in ()).throw(RuntimeError("save failed")))

    bridge._finish_run(0)

    assert bridge.isRunning is False
    assert any("finish_run exit running=False" in row["line"] for row in bridge._logs)


def test_run_bridge_uses_writable_run_log_dir(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(tmp_path)

    assert bridge._stdout_log_path.name == "tmp_main_stdout.log"
    assert bridge._stderr_log_path.name == "tmp_main_stderr.log"
    assert bridge._stdout_log_path.parent.name == "run_logs"
    assert bridge._stdout_mirror_log_path == tmp_path.resolve() / "tmp_main_stdout.log"


def test_run_bridge_start_failure_writes_stderr_log(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)

    def fail_selected_targets():
        raise RuntimeError("selection failed")

    monkeypatch.setattr(bridge, "_selected_run_config", fail_selected_targets)

    bridge.startRun()

    stderr = bridge._stderr_log_path.read_text(encoding="utf-8")
    assert "selection failed" in stderr
    assert "RuntimeError" in stderr
    assert errors and "selection failed" in errors[-1]


def test_run_bridge_start_blocks_missing_required_case_parameter(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    state_path = tmp_path / "test_page_state.json"
    nodeid = "testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress"
    save_state(
        state_path,
        SmartTestPageState(
            selected=[SelectedCase(nodeid=nodeid, case_type="stress")],
            case_parameters={nodeid: {"local_playback_stress:media_files": []}},
            global_context={"dut": "ABC123"},
        ),
    )
    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    monkeypatch.setattr(bridge, "_default_state_path", lambda: state_path)
    monkeypatch.setattr("testing.params.validation.list_adb_devices", lambda: ["ABC123"])
    validation_errors: list[str] = []
    bridge.validationFailed.connect(validation_errors.append)

    started = bridge.startRun()

    assert started is False
    assert bridge.isRunning is False
    assert validation_errors
    assert "Missing required parameter" in validation_errors[-1]
    assert "Playback files" in validation_errors[-1]


def test_run_bridge_finish_emits_explicit_completion_event(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    bridge._set_running(True)
    finished: list[dict] = []
    bridge.runFinished.connect(finished.append)

    bridge._finish_run(0)

    assert bridge.isRunning is False
    assert finished == [{"returncode": 0, "stopped": False}]


def test_run_bridge_validation_message_uses_parameter_label() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    message = bridge._format_run_validation_message(
        [
            RunValidationIssue(
                code="missing_required_param",
                nodeid="testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress",
                case_name="test_local_playback_stress",
                param_key="local_playback_stress:media_dir",
            )
        ]
    )

    assert "Missing required parameter" in message
    assert "Media directory" in message
    assert "local_playback_stress:media_dir" not in message


def test_run_bridge_start_inserts_initial_plan_before_background_start(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    state_path = tmp_path / "test_page_state.json"
    nodeid = "android://auto_reboot"
    mapped_nodeid = "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"
    save_state(
        state_path,
        SmartTestPageState(
            selected=[SelectedCase(nodeid=nodeid)],
            case_parameters={
                nodeid: {
                    "auto_reboot:cycle_count": 1.0,
                    "auto_reboot:interval_sec": 30.0,
                    "auto_reboot:ping_target": "192.168.50.1",
                }
            },
            global_context={"dut": "ABC123"},
        ),
    )

    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    monkeypatch.setattr(bridge, "_default_state_path", lambda: state_path)
    monkeypatch.setattr("testing.runner.config.list_adb_devices", lambda: ["ABC123"])
    monkeypatch.setattr(
        "ui.example.bridge.RunBridge.threading.Thread",
        lambda *args, **kwargs: type("_Thread", (), {"start": lambda self: None})(),
    )

    bridge.startRun()

    rows = bridge.stepRows()

    assert bridge.isRunning is True
    assert len(rows) >= 7
    assert any(row["id"] == f"case:{mapped_nodeid}" for row in rows)
    assert any(row["title"] == "Cycle: reboot DUT" for row in rows)
    assert any(row["title"] == "Cycle: wait for DUT resume" for row in rows)
    assert any(row["definition_id"] == "network.ping" and row["kind"] == "check" for row in rows)
    assert any(row["definition_id"] == "android_client.prepare_request" and row["status"] == "planned" for row in rows)


def test_run_bridge_start_expands_android_step_templates(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    state_path = tmp_path / "test_page_state.json"
    nodeid = "android://emmc_rw"
    mapped_nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"
    save_state(
        state_path,
        SmartTestPageState(
            selected=[SelectedCase(nodeid=nodeid)],
            case_parameters={
                nodeid: {
                    "emmc_rw:loop_count": 1.0,
                    "emmc_rw:source_profile": "random1",
                }
            },
            global_context={"dut": "ABC123"},
        ),
    )

    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    monkeypatch.setattr(bridge, "_default_state_path", lambda: state_path)
    monkeypatch.setattr("testing.runner.config.list_adb_devices", lambda: ["ABC123"])
    monkeypatch.setattr(
        "ui.example.bridge.RunBridge.threading.Thread",
        lambda *args, **kwargs: type("_Thread", (), {"start": lambda self: None})(),
    )

    bridge.startRun()

    rows = bridge.stepRows()

    assert bridge.isRunning is True
    assert any(row["id"] == f"case:{mapped_nodeid}" for row in rows)
    assert not any(row["definition_id"] == "emmc_rw.execute" for row in rows)
    assert any(row["title"] == "Cycle: copy file" for row in rows)
    assert any(row["title"] == "Cycle: read back file" for row in rows)
    assert any(row["title"] == "Cycle: compare file" and row["kind"] == "check" for row in rows)
    assert any(row["definition_id"] == "storage.emmc.prepare_request" and row["status"] == "planned" for row in rows)
    assert not any(str(row["definition_id"]).startswith("android.") for row in rows)


def test_run_bridge_emmc_runtime_steps_match_initial_plan_without_additions(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"
    save_state(
        tmp_path / "test_page_state.json",
        SmartTestPageState(
            selected=[SelectedCase(nodeid=nodeid)],
            case_parameters={nodeid: {"emmc_rw:loop_count": 1.0}},
        ),
    )
    bridge = RunBridge(Path.cwd())
    bridge._MIN_STEP_RUNNING_DISPLAY_SEC = 0.0
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    bridge._append_initial_step_plan(nodeids=[nodeid])

    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "request-1:emmc_rw.cycle.1.copy_file",
            "case_nodeid": nodeid,
            "title": "Cycle 1/1: copy file",
            "kind": "step",
            "definition_id": "emmc_rw.cycle.copy_file",
        }
    )
    bridge._apply_event(
        {
            "type": "step_finished",
            "step_id": "request-1:emmc_rw.cycle.1.copy_file",
            "case_nodeid": nodeid,
            "status": "passed",
        }
    )
    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "request-1:emmc_rw.cycle.1.read_file",
            "case_nodeid": nodeid,
            "title": "Cycle 1/1: read file",
            "kind": "step",
            "definition_id": "emmc_rw.cycle.read_file",
        }
    )
    bridge._apply_event(
        {
            "type": "step_planned",
            "step_id": "step:framework",
            "case_nodeid": nodeid,
            "title": "Run android_client case: emmc_rw",
            "kind": "action",
            "definition_id": "android_client.run_case",
        }
    )
    rows = bridge.stepRows()

    assert sum(1 for row in rows if row["title"] == "Cycle 1/1: copy file") == 1
    assert sum(1 for row in rows if row["title"] == "Cycle 1/1: read back file") == 1
    assert sum(1 for row in rows if row["definition_id"] == "emmc_rw.execute") == 0


def test_run_bridge_execute_summary_step_is_hidden(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"
    save_state(
        tmp_path / "test_page_state.json",
        SmartTestPageState(
            selected=[SelectedCase(nodeid=nodeid)],
            case_parameters={nodeid: {"emmc_rw:loop_count": 1.0}},
        ),
    )
    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    bridge._append_initial_step_plan(nodeids=[nodeid])
    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "request-1:emmc_rw.execute",
            "case_nodeid": nodeid,
            "title": "Execute test_emmc_rw_via_android_client",
            "kind": "action",
            "definition_id": "emmc_rw.execute",
        }
    )

    rows = bridge.stepRows()
    assert any(row["title"] == "Cycle: copy file" for row in rows)
    assert any(row["title"] == "Cycle: read back file" for row in rows)
    assert any(row["title"] == "Cycle: compare file" for row in rows)
    assert not any(row["definition_id"] == "emmc_rw.execute" for row in rows)


def test_run_bridge_runtime_steps_update_initial_plan_without_duplicates(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    nodeid = "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"
    save_state(
        tmp_path / "test_page_state.json",
        SmartTestPageState(
            selected=[SelectedCase(nodeid=nodeid)],
            case_parameters={
                nodeid: {
                    "auto_reboot:cycle_count": 1.0,
                    "auto_reboot:interval_sec": 30.0,
                    "auto_reboot:ping_target": "192.168.50.1",
                }
            },
        ),
    )
    bridge = RunBridge(Path.cwd())
    bridge._MIN_STEP_RUNNING_DISPLAY_SEC = 0.0
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    bridge._append_initial_step_plan(nodeids=[nodeid])
    initial_count = len(bridge.stepRows())

    bridge._apply_event(
        {
            "type": "step_planned",
            "step_id": "step:framework",
            "case_nodeid": nodeid,
            "title": "Run android_client case: auto_reboot",
            "kind": "action",
            "definition_id": "android_client.run_case",
        }
    )
    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "auto_reboot-request:auto_reboot.cycle.1.reboot",
            "case_nodeid": nodeid,
            "parent_id": "step:framework",
            "title": "Cycle 1/1: reboot",
            "kind": "step",
            "definition_id": "auto_reboot.cycle.reboot",
        }
    )
    bridge._apply_event(
        {
            "type": "step_finished",
            "step_id": "auto_reboot-request:auto_reboot.cycle.1.reboot",
            "case_nodeid": nodeid,
            "status": "passed",
        }
    )
    rows = bridge.stepRows()
    reboot_rows = [row for row in rows if row["definition_id"] == "power.reboot"]
    assert len(rows) == initial_count
    assert len(reboot_rows) == 1
    assert not any(row["title"] == "Run android_client case: auto_reboot" for row in rows)


def test_run_bridge_planned_event_does_not_overwrite_existing_plan_row(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/example.py::test_case"
    bridge = RunBridge(Path.cwd())
    bridge._MIN_STEP_RUNNING_DISPLAY_SEC = 0.0
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    case_id = bridge._ensure_case_row(case_nodeid=nodeid, title="test_case")
    bridge._upsert_step_row(
        {
            "step_id": "plan:example.operation",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "Planned operation",
            "kind": "step",
            "definition_id": "example.operation",
        },
        status="planned",
    )

    bridge._apply_event(
        {
            "type": "step_planned",
            "step_id": "runtime:example.operation.detail",
            "case_nodeid": nodeid,
            "parent_id": "runtime:parent",
            "title": "Runtime planned detail",
            "kind": "step",
            "definition_id": "example.operation",
        }
    )

    rows = bridge.stepRows()

    assert sum(1 for row in rows if row["definition_id"] == "example.operation") == 1
    assert any(row["definition_id"] == "example.operation" and row["title"] == "Planned operation" for row in rows)
    assert not any(row["title"] == "Runtime planned detail" for row in rows)


def test_run_bridge_runtime_step_outside_initial_plan_does_not_add_row(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/example.py::test_case"
    bridge = RunBridge(Path.cwd())
    bridge._MIN_STEP_RUNNING_DISPLAY_SEC = 0.0
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    case_id = bridge._ensure_case_row(case_nodeid=nodeid, title="test_case")
    bridge._upsert_step_row(
        {
            "step_id": "plan:example.initial",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "Initial step",
            "kind": "step",
            "definition_id": "example.initial",
        },
        status="planned",
    )
    initial_count = len(bridge.stepRows())

    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "runtime:example.late",
            "case_nodeid": nodeid,
            "parent_id": "runtime:parent",
            "title": "Late runtime step",
            "kind": "step",
            "definition_id": "example.late",
        }
    )

    rows = bridge.stepRows()

    assert len(rows) == initial_count
    assert not any(row["definition_id"] == "example.late" for row in rows)


def test_run_bridge_loop_progress_updates_the_whole_group(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/example.py::test_case"
    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    case_id = bridge._ensure_case_row(case_nodeid=nodeid, title="test_case")
    for suffix in ("prepare", "execute", "verify"):
        bridge._upsert_step_row(
            {
                "step_id": f"plan:workflow.loop.{suffix}",
                "case_nodeid": nodeid,
                "parent_id": case_id,
                "title": f"Loop: {suffix}",
                "kind": "check" if suffix == "verify" else "step",
                "definition_id": f"workflow.{suffix}",
            },
            status="planned",
        )
    for row in bridge._steps:
        if str(row.get("id", "")).startswith("plan:workflow.loop."):
            row["status"] = "passed"

    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "runtime:workflow.loop.2.prepare",
            "case_nodeid": nodeid,
            "parent_id": "runtime:parent",
            "title": "Loop 2/4: prepare",
            "kind": "step",
            "definition_id": "workflow.prepare",
        }
    )

    rows = bridge.stepRows()

    assert any(row["definition_id"] == "workflow.prepare" and row["title"] == "Loop 2/4: prepare" for row in rows)
    assert any(row["definition_id"] == "workflow.execute" and row["title"] == "Loop 2/4: execute" for row in rows)
    assert any(row["definition_id"] == "workflow.verify" and row["title"] == "Loop 2/4: verify" for row in rows)
    assert any(row["definition_id"] == "workflow.prepare" and row["status"] == "running" for row in rows)
    assert any(row["definition_id"] == "workflow.execute" and row["status"] == "planned" for row in rows)
    assert any(row["definition_id"] == "workflow.verify" and row["status"] == "planned" for row in rows)


def test_run_bridge_dynamic_cycle_step_updates_initial_plan(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/example.py::test_case"
    bridge = RunBridge(Path.cwd())
    bridge._MIN_STEP_RUNNING_DISPLAY_SEC = 0.0
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    case_id = bridge._ensure_case_row(case_nodeid=nodeid, title="test_case")
    bridge._upsert_step_row(
        {
            "step_id": "plan:radio_case.cycle.disable",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "Cycle: disable radio",
            "kind": "step",
            "definition_id": "radio.disable",
        },
        status="planned",
    )
    bridge._upsert_step_row(
        {
            "step_id": "plan:radio_case.cycle.enable",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "Cycle: enable radio",
            "kind": "step",
            "definition_id": "radio.enable",
        },
        status="planned",
    )

    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "request-1:radio_case.cycle.3.disable",
            "case_nodeid": nodeid,
            "parent_id": "request-1:android_client",
            "title": "Cycle 3/5: disable",
            "kind": "step",
            "definition_id": "radio_case.cycle.disable",
        }
    )
    bridge._apply_event(
        {
            "type": "step_finished",
            "step_id": "request-1:radio_case.cycle.3.disable",
            "case_nodeid": nodeid,
            "status": "passed",
            "actual": "off",
        }
    )

    rows = bridge.stepRows()

    assert any(
        row["definition_id"] == "radio.disable"
        and row["title"] == "Cycle 3/5: disable radio"
        and row["status"] == "passed"
        and row["actual"] == "off"
        for row in rows
    )
    assert any(row["definition_id"] == "radio.enable" and row["title"] == "Cycle 3/5: enable radio" for row in rows)


def test_run_bridge_dynamic_cycle_steps_advance_past_first_cycle(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/example.py::test_case"
    bridge = RunBridge(Path.cwd())
    bridge._MIN_STEP_RUNNING_DISPLAY_SEC = 0.0
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    case_id = bridge._ensure_case_row(case_nodeid=nodeid, title="test_case")
    bridge._upsert_step_row(
        {
            "step_id": "plan:radio_case.cycle.disable",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "Cycle: disable radio",
            "kind": "step",
            "definition_id": "radio.disable",
        },
        status="planned",
    )

    for cycle in (1, 2, 3):
        runtime_id = f"request-1:radio_case.cycle.{cycle}.disable"
        bridge._apply_event(
            {
                "type": "step_planned",
                "step_id": runtime_id,
                "case_nodeid": nodeid,
                "parent_id": "request-1:android_client",
                "title": f"Cycle {cycle}/5: disable",
                "kind": "step",
                "definition_id": "radio_case.cycle.disable",
            }
        )
        bridge._apply_event(
            {
                "type": "step_started",
                "step_id": runtime_id,
                "case_nodeid": nodeid,
                "parent_id": "request-1:android_client",
                "title": f"Cycle {cycle}/5: disable",
                "kind": "step",
                "definition_id": "radio_case.cycle.disable",
            }
        )
        bridge._apply_event(
            {
                "type": "step_finished",
                "step_id": runtime_id,
                "case_nodeid": nodeid,
                "status": "passed",
                "actual": f"cycle-{cycle}",
            }
        )

    rows = bridge.stepRows()

    assert any(
        row["definition_id"] == "radio.disable"
        and row["title"] == "Cycle 3/5: disable radio"
        and row["status"] == "passed"
        and row["actual"] == "cycle-3"
        for row in rows
    )


def test_run_bridge_keeps_planned_steps_bypassed_by_runtime_order(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/example.py::test_case"
    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    case_id = bridge._ensure_case_row(case_nodeid=nodeid, title="test_case")
    bridge._upsert_step_row(
        {
            "step_id": "step:first",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "First planned step",
            "kind": "step",
            "definition_id": "example.first",
        },
        status="planned",
    )
    bridge._upsert_step_row(
        {
            "step_id": "step:second",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "Second planned step",
            "kind": "step",
            "definition_id": "example.second",
        },
        status="planned",
    )

    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "step:second",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "Second planned step",
            "kind": "step",
            "definition_id": "example.second",
        }
    )

    rows = bridge.stepRows()
    assert any(row["definition_id"] == "example.first" and row["status"] == "planned" for row in rows)
    assert any(row["definition_id"] == "example.second" and row["status"] == "running" for row in rows)


def test_run_bridge_keeps_unrun_planned_steps_when_case_finishes(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/example.py::test_case"
    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    case_id = bridge._ensure_case_row(case_nodeid=nodeid, title="test_case")
    bridge._upsert_step_row(
        {
            "step_id": "step:never",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "Never executed",
            "kind": "check",
            "definition_id": "example.never",
        },
        status="planned",
    )

    bridge._apply_event({"type": "case_finished", "case_nodeid": nodeid, "status": "passed"})

    rows = bridge.stepRows()
    assert any(row["definition_id"] == "example.never" and row["status"] == "planned" for row in rows)
    assert any(row["id"] == f"case:{nodeid}" and row["status"] == "passed" for row in rows)


def test_run_bridge_keeps_unreached_planned_steps_when_case_fails(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/example.py::test_case"
    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    case_id = bridge._ensure_case_row(case_nodeid=nodeid, title="test_case")
    bridge._upsert_step_row(
        {
            "step_id": "step:never",
            "case_nodeid": nodeid,
            "parent_id": case_id,
            "title": "Never executed",
            "kind": "check",
            "definition_id": "example.never",
        },
        status="planned",
    )

    bridge._apply_event({"type": "case_finished", "case_nodeid": nodeid, "status": "failed"})

    rows = bridge.stepRows()
    assert any(row["definition_id"] == "example.never" and row["status"] == "planned" for row in rows)
    assert any(row["id"] == f"case:{nodeid}" and row["status"] == "failed" for row in rows)
