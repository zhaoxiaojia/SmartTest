from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ui"))

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
    monkeypatch.setattr("ui.example.bridge.RunBridge.list_adb_devices", lambda: ["R58N123ABC"])

    assert bridge._resolve_adb_serial("aaaa") == "R58N123ABC"


def test_run_bridge_keeps_saved_device_when_it_exists(monkeypatch) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    monkeypatch.setattr("ui.example.bridge.RunBridge.list_adb_devices", lambda: ["ABC123", "XYZ789"])

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

    monkeypatch.setattr(bridge, "_selected_run_inputs", fail_selected_targets)

    bridge.startRun()

    stderr = bridge._stderr_log_path.read_text(encoding="utf-8")
    assert "selection failed" in stderr
    assert "RuntimeError" in stderr
    assert errors and "selection failed" in errors[-1]


def test_run_bridge_start_inserts_initial_plan_before_background_start(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    state_path = tmp_path / "state.json"
    nodeid = "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"
    save_state(
        state_path,
        SmartTestPageState(
            selected=[SelectedCase(nodeid=nodeid)],
            case_configs={
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
    monkeypatch.setattr(
        "ui.example.bridge.RunBridge.threading.Thread",
        lambda *args, **kwargs: type("_Thread", (), {"start": lambda self: None})(),
    )

    bridge.startRun()

    rows = bridge.stepRows()

    assert bridge.isRunning is True
    assert len(rows) >= 6
    assert any(row["id"] == f"case:{nodeid}" for row in rows)
    assert any("ping 192.168.50.1" in row["title"] for row in rows)
    assert any("Cycle: wait interval 30s" in row["title"] for row in rows)
    assert any(row["definition_id"] == "power.reboot" and row["kind"] == "step" for row in rows)
    assert any(row["definition_id"] == "network.ping" and row["kind"] == "check" for row in rows)
    assert not any("wait interval 100s" in row["title"] for row in rows)


def test_run_bridge_start_expands_android_step_templates(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    state_path = tmp_path / "state.json"
    nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"
    save_state(
        state_path,
        SmartTestPageState(
            selected=[SelectedCase(nodeid=nodeid)],
            case_configs={
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
    monkeypatch.setattr(
        "ui.example.bridge.RunBridge.threading.Thread",
        lambda *args, **kwargs: type("_Thread", (), {"start": lambda self: None})(),
    )

    bridge.startRun()

    rows = bridge.stepRows()

    assert bridge.isRunning is True
    assert any(row["id"] == f"case:{nodeid}" for row in rows)
    assert not any(row["definition_id"] == "emmc_rw.execute" for row in rows)
    assert any(row["id"].endswith("emmc_rw.cycle.copy_file") for row in rows)
    assert any(row["id"].endswith("emmc_rw.cycle.read_file") for row in rows)
    assert any(row["definition_id"] == "storage.emmc.cmp_file" and row["kind"] == "check" for row in rows)
    assert any(row["definition_id"] == "smarttest.runner.prepare" and row["status"] == "passed" for row in rows)
    assert not any(str(row["definition_id"]).startswith("emmc_rw.check.") for row in rows)
    assert not any(row["kind"] == "check" and row["title"] == "Read back each file" for row in rows)


def test_run_bridge_emmc_runtime_steps_match_initial_plan_without_additions(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"
    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    bridge._append_initial_step_plan(
        nodeids=[nodeid],
        case_configs={nodeid: {"emmc_rw:loop_count": 1.0}},
    )

    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "runtime:prepare",
            "case_nodeid": nodeid,
            "title": "Prepare eMMC read/write request",
            "kind": "step",
            "definition_id": "storage.emmc.prepare_request",
        }
    )
    bridge._apply_event(
        {
            "type": "step_finished",
            "step_id": "runtime:prepare",
            "case_nodeid": nodeid,
            "status": "passed",
        }
    )
    bridge._apply_event(
        {
            "type": "step_started",
            "step_id": "runtime:trigger",
            "case_nodeid": nodeid,
            "title": "Trigger eMMC read/write execution",
            "kind": "step",
            "definition_id": "storage.emmc.trigger_execution",
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

    assert sum(1 for row in rows if row["definition_id"] == "storage.emmc.prepare_request") == 1
    assert sum(1 for row in rows if row["definition_id"] == "storage.emmc.trigger_execution") == 1
    assert sum(1 for row in rows if row["definition_id"] == "emmc_rw.execute") == 0


def test_run_bridge_execute_summary_step_is_hidden(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client"
    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    bridge._append_initial_step_plan(
        nodeids=[nodeid],
        case_configs={nodeid: {"emmc_rw:loop_count": 1.0}},
    )
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
    assert any(row["definition_id"] == "storage.emmc.copy_file" for row in rows)
    assert any(row["definition_id"] == "storage.emmc.read_file" for row in rows)
    assert any(row["definition_id"] == "storage.emmc.cmp_file" for row in rows)
    assert not any(row["definition_id"] == "emmc_rw.execute" for row in rows)


def test_run_bridge_runtime_steps_update_initial_plan_without_duplicates(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    nodeid = "testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client"
    bridge = RunBridge(Path.cwd())
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    bridge._reset_run_data()
    bridge._append_initial_step_plan(
        nodeids=[nodeid],
        case_configs={
            nodeid: {
                "auto_reboot:cycle_count": 1.0,
                "auto_reboot:interval_sec": 30.0,
                "auto_reboot:ping_target": "192.168.50.1",
            }
        },
    )
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
            "step_id": "auto_reboot-request:auto_reboot.prepare",
            "case_nodeid": nodeid,
            "parent_id": "step:framework",
            "title": "Prepare auto reboot request",
            "kind": "setup",
            "definition_id": "power.auto_reboot.prepare",
        }
    )
    bridge._apply_event(
        {
            "type": "step_finished",
            "step_id": "auto_reboot-request:auto_reboot.prepare",
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


def test_run_bridge_removes_planned_steps_skipped_by_runtime_order(tmp_path) -> None:
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
    assert not any(row["definition_id"] == "example.first" for row in rows)
    assert any(row["definition_id"] == "example.second" and row["status"] == "running" for row in rows)


def test_run_bridge_removes_unrun_planned_steps_when_case_finishes(tmp_path) -> None:
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
    assert not any(row["definition_id"] == "example.never" for row in rows)
    assert any(row["id"] == f"case:{nodeid}" and row["status"] == "passed" for row in rows)


def test_run_bridge_marks_unreached_planned_steps_skipped_when_case_fails(tmp_path) -> None:
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
    assert any(row["definition_id"] == "example.never" and row["status"] == "skipped" for row in rows)
    assert any(row["id"] == f"case:{nodeid}" and row["status"] == "failed" for row in rows)
