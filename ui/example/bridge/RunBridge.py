from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

from testing.reporting.store import ReportStore, build_run_report
from testing.cases.catalog import is_packaged_runtime, load_runtime_test_catalog
from testing.cases.discovery import PytestDiscoveryError, discover_pytest_cases
from testing.params.validation import RunValidationIssue, validate_run_request
from testing.runner.config import RunConfig, build_run_config_from_state
from testing.runner.execution import TestRunSession, start_pytest_run
from testing.steps.planner import build_step_plan
from testing.state.store import load_state
from tools.logging import default_log_path, log_display_fields, smart_log
from ui.example.bridge.StepStore import StepStore

try:
    from example.helper.AppPaths import app_data_dir
    from example.helper.TranslateHelper import TranslateHelper
    from example.helper.TsTextCatalog import TsTextCatalog
except ImportError:  # pragma: no cover - direct unit-test imports may use the ui.example package path
    from ui.example.helper.AppPaths import app_data_dir
    from ui.example.helper.TranslateHelper import TranslateHelper
    from ui.example.helper.TsTextCatalog import TsTextCatalog


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
        self._logs: list[dict[str, Any]] = []
        self._step_store = StepStore(log=self._append_log, on_change=self.stepsChanged.emit)
        self._session: TestRunSession | None = None
        self._stop_requested = False
        self._run_id = ""
        self._run_started_at = ""
        self._run_started_monotonic = 0.0
        self._run_selected_nodeids: list[str] = []
        self._run_adb_serial: str | None = None
        self._report_store = ReportStore(self._default_reports_dir())
        self._text_catalog = TsTextCatalog(self._root_dir)

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
        text_key = f"test.param.{normalized.replace(':', '.')}.label"
        label = self._text_catalog.text(
            locale=TranslateHelper().current,
            context="TestPageBridge",
            source=text_key,
        )
        return label or normalized

    def _set_running(self, running: bool) -> None:
        if self._running == running:
            return
        self._running = running
        self.runningChanged.emit()

    def _reset_run_data(self) -> None:
        self._logs = []
        self._step_store.reset()
        self.logsChanged.emit()
        self.stepsChanged.emit()

    def _begin_report_context(self, *, nodeids: list[str], adb_serial: str | None) -> None:
        self._run_id = uuid4().hex
        self._run_started_at = self._now_iso()
        self._run_started_monotonic = time.monotonic()
        self._run_selected_nodeids = list(nodeids)
        self._run_adb_serial = adb_serial

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

    def _append_initial_step_plan(self, *, nodeids: list[str]) -> None:
        self._step_store.begin_initial_plan()
        try:
            for nodeid in nodeids:
                case_title = nodeid.rsplit("::", 1)[-1] if "::" in nodeid else nodeid
                case_row_id = self._step_store.ensure_case_row(case_nodeid=nodeid, title=case_title)
                plan_items = build_step_plan(root_dir=self._root_dir, nodeid=nodeid)
                self._append_log(
                    "[steps.trace] initial_plan_loaded "
                    f"case={nodeid} items={len(plan_items)}"
                )
                for item in plan_items:
                    raw_step_id = str(item.get("id", "") or "step")
                    definition_id = str(item.get("definition_id", "") or raw_step_id)
                    self._append_log(
                        "[steps.trace] initial_step "
                        f"case={nodeid} id={raw_step_id} kind={str(item.get('kind', 'action') or 'action')} "
                        f"definition_id={definition_id}"
                    )
                    self._step_store.upsert_step_row(
                        {
                            "step_id": f"plan:{nodeid}:{raw_step_id}",
                            "case_nodeid": nodeid,
                            "parent_id": case_row_id,
                            "title": str(item.get("title", "") or raw_step_id),
                            "kind": str(item.get("kind", "action") or "action"),
                            "definition_id": definition_id,
                            "expected": item.get("expected", ""),
                        },
                        status="planned",
                    )
        finally:
            self._step_store.end_initial_plan()

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
            self._run_adb_serial = run_config.dut_serial
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
        self._logs.append(row)
        self.logsChanged.emit()

    def _apply_event(self, payload: dict[str, Any]) -> None:
        event_type = str(payload.get("type", ""))
        if event_type == "case_started":
            self._step_store.ensure_case_row(
                case_nodeid=str(payload.get("case_nodeid", "")),
                title=str(payload.get("title", "")),
                status="running",
            )
            return

        if event_type == "case_finished":
            self._step_store.mark_case_finished(payload)
            return

        if event_type == "step_planned":
            self._step_store.upsert_step_row(payload, status="planned", allow_create=False)
            return

        if event_type == "step_started":
            self._step_store.mark_step_started(payload)
            return

        if event_type == "step_finished":
            applied, delay_ms, delayed_payload = self._step_store.apply_step_finished(
                payload,
                min_running_display_sec=self._MIN_STEP_RUNNING_DISPLAY_SEC,
            )
            if delay_ms and delayed_payload is not None:
                QTimer.singleShot(delay_ms, lambda p=delayed_payload: self._apply_event(p))
            return

        if event_type == "step_evidence":
            self._step_store.apply_step_evidence(payload)
            return

        if event_type == "log":
            message = str(payload.get("message", "")).strip()
            line = str(payload.get("line") or "").strip()
            if message or line:
                self._append_log_record(
                    {
                        "line": line or message,
                        "message": message or line,
                        "level": str(payload.get("level", "info") or "info"),
                        "domain": str(payload.get("domain", "test") or "test"),
                        "source": str(payload.get("source", "") or ""),
                        "case_nodeid": str(payload.get("case_nodeid", "") or ""),
                        "step_id": str(payload.get("step_id", "") or ""),
                        "extra": dict(payload.get("extra") or {}),
                    }
                )

    def _finish_run(self, returncode: int) -> None:
        if self._stop_requested:
            self._append_log("[run] stopped")
        elif returncode == 0:
            self._append_log("[run] completed successfully")
        else:
            self._append_log(f"[run] failed with exit code {returncode}")
        try:
            duration_ms = (
                int((time.monotonic() - self._run_started_monotonic) * 1000)
                if self._run_started_monotonic
                else 0
            )
            report = build_run_report(
                run_id=self._run_id,
                started_at=self._run_started_at or self._now_iso(),
                finished_at=self._now_iso(),
                duration_ms=duration_ms,
                returncode=returncode,
                stopped=self._stop_requested,
                adb_serial=self._run_adb_serial,
                selected_nodeids=self._run_selected_nodeids,
                steps=self._step_store.snapshot(),
                logs=self._logs,
            )
            try:
                self._report_store.save(report)
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
                    "run_id": str(self._run_id or ""),
                }
            )

    @Slot(result=bool)
    def hasLogs(self) -> bool:
        return bool(self._logs)

    @Slot(result=bool)
    def hasSteps(self) -> bool:
        return bool(self._step_store.rows())

    @Slot(result="QVariantList")
    def logRows(self):
        return list(self._logs)

    @Slot(result=str)
    def logText(self) -> str:
        return "\n".join(str(item.get("line", "")) for item in self._logs)

    @Slot(result="QVariantList")
    def stepRows(self):
        return list(self._step_store.rows())

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
            self._begin_report_context(nodeids=nodeids, adb_serial=run_config.dut_serial)
            self._stop_requested = False
            self._append_start_diagnostics(nodeids=nodeids, adb_serial=run_config.dut_serial)
            self._append_initial_step_plan(nodeids=nodeids)
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
