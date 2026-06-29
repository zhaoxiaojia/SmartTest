from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from testing.cases.catalog import is_packaged_runtime, load_runtime_test_catalog
from testing.cases.discovery import PytestDiscoveryError, discover_pytest_cases
from testing.params.validation import RunValidationIssue, validate_run_request
from testing.runner.config import RunConfig, build_run_config_from_state
from testing.runner.execution import TestRunSession, start_pytest_run
from testing.state.store import load_state
from testing.test_context import smarttest_context
from tools.logging import default_log_path, log_display_fields, smart_log
from tools.report import save_run_report

try:
    from example.helper.AppPaths import app_data_dir
except ImportError:  # pragma: no cover - direct unit-test imports may use the ui.example package path
    from ui.example.helper.AppPaths import app_data_dir


class RunBridge(QObject):
    runningChanged = Signal()
    logsChanged = Signal()
    stepsChanged = Signal()
    errorOccurred = Signal(str)
    validationFailed = Signal(str)
    runFinished = Signal("QVariantMap")

    _logSignal = Signal(str)
    _eventSignal = Signal("QVariantMap")
    _finishSignal = Signal(int)
    _MIN_STEP_RUNNING_DISPLAY_SEC = 0.12

    def __init__(self, root_dir: Path):
        super().__init__(QGuiApplication.instance())
        self._root_dir = root_dir.resolve()
        self._running = False
        self._session: TestRunSession | None = None
        self._stop_requested = False

        self._logSignal.connect(self._append_log)
        self._eventSignal.connect(self._apply_event)
        self._finishSignal.connect(self._finish_run)

    def _default_state_path(self) -> Path:
        return app_data_dir() / "test_page_state.json"

    def _default_reports_dir(self) -> Path:
        return app_data_dir() / "reports"

    def _now_iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _selected_run_config(self) -> RunConfig:
        state = load_state(self._default_state_path())
        run_config, diagnostics = build_run_config_from_state(root_dir=self._root_dir, state=state)
        for line in diagnostics:
            self._append_log(line, domain="runner", source="RunConfig")
        return run_config

    def _validation_catalog(self, state) -> list[dict[str, Any]]:
        rows = load_runtime_test_catalog(root_dir=self._root_dir)
        selected_nodeids = {str(case.nodeid or "").strip() for case in state.selected if str(case.nodeid or "").strip()}
        known_nodeids = {str(row.get("nodeid", "") or "").strip() for row in rows}
        known_android_ids = {
            f"android://{str(row.get('android_case_id', '') or '').strip()}"
            for row in rows
            if str(row.get("android_case_id", "") or "").strip()
        }
        if is_packaged_runtime() or selected_nodeids <= (known_nodeids | known_android_ids):
            return rows
        try:
            cases = discover_pytest_cases(root_dir=self._root_dir, python_executable=sys.executable)
        except PytestDiscoveryError:
            return rows
        return [
            {
                "nodeid": case.nodeid,
                "file": case.file,
                "name": case.name,
                "markers": case.markers,
                "case_type": case.case_type,
                "required_params": case.required_params,
                "required_param_groups": case.required_param_groups,
                "required_equipment": case.required_equipment,
                "android_case_id": case.android_case_id,
            }
            for case in cases
        ]

    def _validate_current_run_request(self, resolved_dut_serial: str | None) -> list[RunValidationIssue]:
        state = load_state(self._default_state_path())
        return validate_run_request(
            root_dir=self._root_dir,
            state=state,
            catalog=self._validation_catalog(state),
            resolved_dut_serial=resolved_dut_serial,
        )

    def _format_run_validation_message(self, issues: list[RunValidationIssue]) -> str:
        lines: list[str] = []
        for issue in issues:
            if issue.code == "missing_dut":
                lines.append(self.tr("Select a DUT before starting the selected test cases."))
                continue
            if issue.code == "missing_required_param":
                lines.append(
                    self.tr("Missing required parameter: {param} ({case})").format(
                        param=self._param_label(issue.param_key),
                        case=issue.case_name or issue.nodeid,
                    )
                )
                continue
            lines.append(issue.param_key or issue.code)
        message = self.tr("Fix required test parameters before starting.")
        if lines:
            message += "\n\n" + "\n".join(lines)
        return message

    def _param_label(self, param_key: str) -> str:
        normalized = str(param_key or "").strip()
        if not normalized:
            return ""
        return normalized

    def _set_running(self, running: bool) -> None:
        if self._running == running:
            return
        self._running = running
        self.runningChanged.emit()

    def _reset_run_data(self) -> None:
        self.logsChanged.emit()
        self.stepsChanged.emit()

    def _append_exception_log(self, exc: BaseException, *, source: str = "RunBridge") -> None:
        smart_log(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            domain="runner",
            level="error",
            source=source,
            emit_runtime_event=False,
        )

    def _append_start_diagnostics(self, *, nodeids: list[str], adb_serial: str | None) -> None:
        diagnostics = [
            f"[run] diagnostics log: {default_log_path()}",
            f"[run] root_dir: {self._root_dir}",
            f"[run] packaged_runtime: {is_packaged_runtime()}",
            f"[run] selected cases: {len(nodeids)}",
            f"[run] adb_serial: {adb_serial or '<auto>'}",
        ]
        for line in diagnostics:
            self._append_log(line, domain="runner", source="RunBridge")

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
                        payload = json.loads(buffer.strip())
                        self._eventSignal.emit(payload)
                    except json.JSONDecodeError:
                        self._logSignal.emit(f"[event-decode-error] {buffer.strip()}")
                return
            time.sleep(0.1)

    def _wait_for_completion(self, session: TestRunSession) -> None:
        returncode = session.process.wait()
        time.sleep(0.2)
        self._finishSignal.emit(returncode)

    def _start_run_background(
        self,
        *,
        run_config: RunConfig,
    ) -> None:
        try:
            session = start_pytest_run(
                root_dir=self._root_dir,
                run_config=run_config,
            )
            self._session = session
            self._logSignal.emit(
                f"[run] runner session started pid={getattr(session.process, 'pid', '<unknown>')}"
            )
            threading.Thread(target=self._pump_stdout, args=(session,), daemon=True).start()
            threading.Thread(target=self._pump_events, args=(session,), daemon=True).start()
            threading.Thread(target=self._wait_for_completion, args=(session,), daemon=True).start()
        except Exception as exc:  # noqa: BLE001
            self._append_exception_log(exc, source="RunBridge.start_background")
            self.errorOccurred.emit(self.tr("Failed to start test run. {detail}").format(detail=str(exc)))
            self._finishSignal.emit(1)

    def _append_log(
        self,
        line: str,
        *,
        domain: str = "runner",
        level: str = "info",
        source: str = "stdout",
        extra: dict[str, Any] | None = None,
    ) -> None:
        record = smart_log(
            line,
            domain=domain,
            level=level,
            source=source,
            extra=extra,
            emit_runtime_event=False,
        )
        self._append_log_record(record)

    def _append_log_record(self, record: Any) -> None:
        if isinstance(record, dict):
            row = dict(record)
            text = str(row.get("line") or row.get("message") or "").rstrip()
        else:
            row = record.to_row()
            text = str(row.get("line") or "").rstrip()
        if not text:
            return
        row["line"] = text
        row.update(log_display_fields(domain=row.get("domain"), level=row.get("level")))
        smarttest_context().append_log(row)
        self.logsChanged.emit()

    def _apply_event(self, payload: dict[str, Any]) -> None:
        smarttest_context().apply_event(payload, min_running_display_sec=self._MIN_STEP_RUNNING_DISPLAY_SEC)
        if str(payload.get("type", "")) == "log":
            self.logsChanged.emit()
        else:
            self.stepsChanged.emit()

    def _finish_run(self, returncode: int) -> None:
        report: dict[str, Any] = {}
        if self._stop_requested:
            self._append_log("[run] stopped")
        elif returncode == 0:
            self._append_log("[run] completed successfully")
        else:
            self._append_log(f"[run] failed with exit code {returncode}")
            if self._session is not None:
                self._session.cleanup_failed_run(f"pytest failed with exit code {returncode}")
        try:
            report = smarttest_context().finish_run(
                returncode=returncode,
                stopped=self._stop_requested,
                finished_at=self._now_iso(),
            )
            try:
                save_run_report(report, reports_dir=self._default_reports_dir())
            except OSError as exc:
                self.errorOccurred.emit(self.tr("Failed to save run report. {detail}").format(detail=str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._append_exception_log(exc, source="RunBridge.finish_run")
            self.errorOccurred.emit(self.tr("Failed to finish test run. {detail}").format(detail=str(exc)))
        finally:
            if self._session is not None:
                try:
                    self._session.cleanup()
                except Exception as exc:  # noqa: BLE001
                    self._append_exception_log(exc, source="RunBridge.cleanup")
                self._session = None
            self._set_running(False)
            self.runFinished.emit(
                {
                    "returncode": int(returncode),
                    "stopped": bool(self._stop_requested),
                    "run_id": str(report.get("run_id", "") if isinstance(report, dict) else ""),
                }
            )

    @Slot(result=bool)
    def hasLogs(self) -> bool:
        return smarttest_context().has_logs()

    @Slot(result=bool)
    def hasSteps(self) -> bool:
        return smarttest_context().has_steps()

    @Slot(result="QVariantList")
    def logRows(self):
        return smarttest_context().log_rows()

    @Slot(result=str)
    def logText(self) -> str:
        return "\n".join(str(item.get("line", "")) for item in smarttest_context().log_rows())

    @Slot(result="QVariantList")
    def stepRows(self):
        return smarttest_context().step_rows()

    @Slot(result=bool)
    def startRun(self) -> bool:
        if self._running:
            return False
        try:
            run_config = self._selected_run_config()
            nodeids = list(run_config.nodeids)
            if not nodeids:
                self.errorOccurred.emit(self.tr("No selected test cases to run."))
                return False

            validation_issues = self._validate_current_run_request(run_config.dut_serial)
            if validation_issues:
                self.validationFailed.emit(self._format_run_validation_message(validation_issues))
                return False

            self._reset_run_data()
            smarttest_context().begin_run(root_dir=self._root_dir, run_config=run_config, started_at=self._now_iso())
            self._stop_requested = False
            self._append_start_diagnostics(nodeids=nodeids, adb_serial=run_config.dut_serial)
            self.stepsChanged.emit()
        except Exception as exc:  # noqa: BLE001
            self._append_exception_log(exc, source="RunBridge.startRun")
            self.errorOccurred.emit(self.tr("Failed to start pytest run. {detail}").format(detail=str(exc)))
            return False

        self._session = None
        self._set_running(True)

        threading.Thread(
            target=self._start_run_background,
            kwargs={
                "run_config": run_config,
            },
            daemon=True,
        ).start()
        return True

    @Slot()
    def stopRun(self) -> None:
        if not self._running or self._session is None:
            return
        self._stop_requested = True
        self._session.stop("UI stop button")

    @Slot(result=bool)
    def toggleRun(self) -> bool:
        if self._running:
            self.stopRun()
            return True
        return self.startRun()

    def _get_is_running(self) -> bool:
        return self._running

    isRunning = Property(bool, _get_is_running, notify=runningChanged)
