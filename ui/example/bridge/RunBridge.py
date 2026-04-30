from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QStandardPaths, Signal, Slot
from PySide6.QtGui import QGuiApplication

from testing.params.adb_devices import list_adb_devices
from testing.reporting import ReportStore, build_run_report
from testing.runner.execution import TestRunSession, start_pytest_run
from testing.state.store import load_state, save_state


class RunBridge(QObject):
    runningChanged = Signal()
    logsChanged = Signal()
    stepsChanged = Signal()
    errorOccurred = Signal(str)

    _logSignal = Signal(str)
    _eventSignal = Signal("QVariantMap")
    _finishSignal = Signal(int)

    def __init__(self, root_dir: Path):
        super().__init__(QGuiApplication.instance())
        self._root_dir = root_dir.resolve()
        self._stdout_log_path = self._root_dir / "tmp_main_stdout.log"
        self._stderr_log_path = self._root_dir / "tmp_main_stderr.log"
        self._running = False
        self._logs: list[dict[str, Any]] = []
        self._steps: list[dict[str, Any]] = []
        self._step_index: dict[str, int] = {}
        self._session: TestRunSession | None = None
        self._stop_requested = False
        self._run_id = ""
        self._run_started_at = ""
        self._run_started_monotonic = 0.0
        self._run_selected_nodeids: list[str] = []
        self._run_adb_serial: str | None = None
        self._report_store = ReportStore(self._default_reports_dir())

        self._logSignal.connect(self._append_log)
        self._eventSignal.connect(self._apply_event)
        self._finishSignal.connect(self._finish_run)

    def _default_state_path(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "test_page_state.json"

    def _default_reports_dir(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "reports"

    def _now_iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _trace_timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def _resolve_adb_serial(self, saved_dut: str) -> str | None:
        devices = list_adb_devices()
        normalized_saved = str(saved_dut or "").strip()
        print(f"{self._trace_timestamp()} [RunBridge] discovered adb devices: {devices}")
        print(f"{self._trace_timestamp()} [RunBridge] saved dut: {normalized_saved or '<empty>'}")
        raw_saved = str(saved_dut or "").strip()
        if raw_saved and raw_saved in devices:
            return raw_saved
        if len(devices) == 1:
            return devices[0]
        return None

    def _selected_run_targets(self) -> tuple[list[str], str | None, dict[str, dict[str, Any]]]:
        state_path = self._default_state_path()
        state = load_state(state_path)
        nodeids = [case.nodeid for case in state.selected if case.nodeid]
        saved_dut = str(state.global_context.get("dut", "") or "").strip()
        adb_serial = self._resolve_adb_serial(saved_dut)
        if adb_serial and adb_serial != saved_dut:
            state.global_context["dut"] = adb_serial
            save_state(state_path, state)
        case_configs = {
            nodeid: dict(state.case_configs.get(nodeid, {}))
            for nodeid in nodeids
            if isinstance(state.case_configs.get(nodeid, {}), dict)
        }
        return nodeids, adb_serial, case_configs

    def _set_running(self, running: bool) -> None:
        if self._running == running:
            return
        self._running = running
        self.runningChanged.emit()

    def _reset_run_data(self) -> None:
        self._logs = []
        self._steps = []
        self._step_index = {}
        self._stdout_log_path.write_text("", encoding="utf-8")
        self._stderr_log_path.write_text("", encoding="utf-8")
        self.logsChanged.emit()
        self.stepsChanged.emit()

    def _begin_report_context(self, *, nodeids: list[str], adb_serial: str | None) -> None:
        self._run_id = uuid4().hex
        self._run_started_at = self._now_iso()
        self._run_started_monotonic = time.monotonic()
        self._run_selected_nodeids = list(nodeids)
        self._run_adb_serial = adb_serial

    def _append_local_log(self, path: Path, text: str) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)
            fh.write("\n")

    def _start_run_session(
        self,
        nodeids: list[str],
        adb_serial: str | None,
        case_configs: dict[str, dict[str, Any]],
    ) -> TestRunSession:
        return start_pytest_run(
            root_dir=self._root_dir,
            nodeids=nodeids,
            adb_serial=adb_serial,
            case_configs=case_configs,
        )

    def _pump_stdout(self, session: TestRunSession) -> None:
        if session.process.stdout is None:
            return
        for line in session.process.stdout:
            self._logSignal.emit(line.rstrip())

    def _pump_events(self, session: TestRunSession) -> None:
        event_path = session.event_file
        offset = 0
        buffer = ""
        while True:
            process_done = session.process.poll() is not None
            if event_path.exists():
                with event_path.open("r", encoding="utf-8") as fh:
                    fh.seek(offset)
                    chunk = fh.read()
                    offset = fh.tell()
                if chunk:
                    buffer += chunk
                    lines = buffer.splitlines(keepends=True)
                    buffer = ""
                    for raw_line in lines:
                        if not raw_line.endswith("\n"):
                            buffer = raw_line
                            continue
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            self._logSignal.emit(f"[event-decode-error] {line}")
                            continue
                        self._eventSignal.emit(payload)
            if process_done:
                if buffer.strip():
                    try:
                        self._eventSignal.emit(json.loads(buffer.strip()))
                    except json.JSONDecodeError:
                        self._logSignal.emit(f"[event-decode-error] {buffer.strip()}")
                return
            time.sleep(0.1)

    def _wait_for_completion(self, session: TestRunSession) -> None:
        returncode = session.process.wait()
        time.sleep(0.2)
        self._finishSignal.emit(returncode)

    def _append_log(self, line: str) -> None:
        text = str(line or "").rstrip()
        if not text:
            return
        self._logs.append({"line": text})
        self._append_local_log(self._stdout_log_path, text)
        self.logsChanged.emit()

    def _ensure_case_row(self, *, case_nodeid: str, title: str) -> str:
        row_id = f"case:{case_nodeid}"
        if row_id in self._step_index:
            return row_id
        self._step_index[row_id] = len(self._steps)
        self._steps.append(
            {
                "id": row_id,
                "title": title,
                    "status": "running",
                    "depth": 0,
                    "phase": "call",
                    "kind": "case",
                    "definition_id": "",
                    "case_nodeid": case_nodeid,
                }
            )
        self.stepsChanged.emit()
        return row_id

    def _apply_event(self, payload: dict[str, Any]) -> None:
        event_type = str(payload.get("type", ""))
        if event_type == "case_started":
            self._ensure_case_row(
                case_nodeid=str(payload.get("case_nodeid", "")),
                title=str(payload.get("title", "")),
            )
            return

        if event_type == "case_finished":
            row_id = f"case:{payload.get('case_nodeid', '')}"
            index = self._step_index.get(row_id)
            if index is not None:
                self._steps[index]["status"] = str(payload.get("status", "passed"))
                self.stepsChanged.emit()
            return

        if event_type == "step_started":
            case_nodeid = str(payload.get("case_nodeid", ""))
            parent_id = str(payload.get("parent_id") or self._ensure_case_row(case_nodeid=case_nodeid, title=case_nodeid))
            parent_row = self._steps[self._step_index[parent_id]]
            step_id = str(payload.get("step_id", ""))
            if step_id in self._step_index:
                return
            self._step_index[step_id] = len(self._steps)
            self._steps.append(
                {
                    "id": step_id,
                    "title": str(payload.get("title", "")),
                    "status": "running",
                    "depth": int(parent_row.get("depth", 0)) + 1,
                    "phase": str(payload.get("phase", "call")),
                    "kind": str(payload.get("kind", "case")),
                    "definition_id": str(payload.get("definition_id", "") or ""),
                    "case_nodeid": case_nodeid,
                }
            )
            self.stepsChanged.emit()
            return

        if event_type == "step_finished":
            step_id = str(payload.get("step_id", ""))
            index = self._step_index.get(step_id)
            if index is not None:
                self._steps[index]["status"] = str(payload.get("status", "passed"))
                self.stepsChanged.emit()
            error = str(payload.get("error", "") or "").strip()
            if error:
                self._append_log(f"[step-error] {error}")
            return

        if event_type == "log":
            message = str(payload.get("message", "")).strip()
            if message:
                self._append_log(message)

    def _finish_run(self, returncode: int) -> None:
        if self._stop_requested:
            self._append_log("[run] stopped")
        elif returncode == 0:
            self._append_log("[run] completed successfully")
        else:
            self._append_log(f"[run] failed with exit code {returncode}")
        duration_ms = int((time.monotonic() - self._run_started_monotonic) * 1000) if self._run_started_monotonic else 0
        report = build_run_report(
            run_id=self._run_id,
            started_at=self._run_started_at or self._now_iso(),
            finished_at=self._now_iso(),
            duration_ms=duration_ms,
            returncode=returncode,
            stopped=self._stop_requested,
            adb_serial=self._run_adb_serial,
            selected_nodeids=self._run_selected_nodeids,
            steps=self._steps,
            logs=self._logs,
        )
        try:
            self._report_store.save(report)
        except OSError as exc:
            self.errorOccurred.emit(self.tr("Failed to save run report. {detail}").format(detail=str(exc)))
        if self._session is not None:
            self._session.cleanup()
            self._session = None
        self._set_running(False)

    @Slot(result=bool)
    def hasLogs(self) -> bool:
        return bool(self._logs)

    @Slot(result=bool)
    def hasSteps(self) -> bool:
        return bool(self._steps)

    @Slot(result="QVariantList")
    def logRows(self):
        return list(self._logs)

    @Slot(result=str)
    def logText(self) -> str:
        return "\n".join(str(item.get("line", "")) for item in self._logs)

    @Slot(result="QVariantList")
    def stepRows(self):
        return list(self._steps)

    @Slot()
    def startRun(self) -> None:
        if self._running:
            return
        nodeids, adb_serial, case_configs = self._selected_run_targets()
        if not nodeids:
            self.errorOccurred.emit(self.tr("No selected test cases to run."))
            return

        self._reset_run_data()
        self._begin_report_context(nodeids=nodeids, adb_serial=adb_serial)
        self._stop_requested = False
        try:
            session = self._start_run_session(nodeids, adb_serial, case_configs)
        except Exception as exc:  # noqa: BLE001
            self._append_local_log(self._stderr_log_path, str(exc))
            self.errorOccurred.emit(self.tr("Failed to start pytest run. {detail}").format(detail=str(exc)))
            return

        self._session = session
        self._set_running(True)
        self._append_log(f"[run] selected cases: {len(nodeids)}")

        threading.Thread(target=self._pump_stdout, args=(session,), daemon=True).start()
        threading.Thread(target=self._pump_events, args=(session,), daemon=True).start()
        threading.Thread(target=self._wait_for_completion, args=(session,), daemon=True).start()

    @Slot()
    def stopRun(self) -> None:
        if not self._running or self._session is None:
            return
        self._stop_requested = True
        self._session.stop("UI stop button")

    @Slot()
    def toggleRun(self) -> None:
        if self._running:
            self.stopRun()
            return
        self.startRun()

    def _get_is_running(self) -> bool:
        return self._running

    isRunning = Property(bool, _get_is_running, notify=runningChanged)
