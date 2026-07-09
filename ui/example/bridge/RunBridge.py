from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from testing.cases.catalog import is_packaged_runtime, load_runtime_test_catalog
from testing.cases.discovery import PytestDiscoveryError, discover_pytest_cases
from testing.params.validation import RunValidationIssue, validate_run_request
from testing.runner.config import RunConfig, build_run_config_from_state
from testing.runner.execution import TestRunSession, start_pytest_run
from testing.state.store import load_state
from testing.test_context import TestContext, smarttest_context
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
    _finishSignal = Signal(str, int)
    _MIN_STEP_RUNNING_DISPLAY_SEC = 0.12

    def __init__(self, root_dir: Path):
        super().__init__(QGuiApplication.instance())
        self._root_dir = root_dir.resolve()
        self._running = False
        self._session: TestRunSession | None = None
        self._sessions: dict[str, TestRunSession] = {}
        self._contexts: dict[str, TestContext] = {}
        self._run_configs: dict[str, RunConfig] = {}
        self._returncodes: dict[str, int | None] = {}
        self._statuses: dict[str, str] = {}
        self._finished_reports: dict[str, dict[str, Any]] = {}
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
        self._contexts = {}
        self._run_configs = {}
        self._returncodes = {}
        self._statuses = {}
        self._finished_reports = {}
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
            self._append_log(line, domain="runner", source="RunBridge", extra={"dut_serial": adb_serial or ""})

    def _pump_stdout(self, serial: str, session: TestRunSession) -> None:
        if session.process.stdout is None:
            return
        for line in session.process.stdout:
            self._append_log_for_dut(serial, line.rstrip(), domain="runner", source="stdout")

    def _pump_events(self, serial: str, session: TestRunSession) -> None:
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
                            self._append_log_for_dut(serial, f"[event-decode-error] {line}", domain="runner", source="events")
                            continue
                        payload["dut_serial"] = serial
                        self._eventSignal.emit(payload)
            if process_done:
                if buffer.strip():
                    try:
                        payload = json.loads(buffer.strip())
                        payload["dut_serial"] = serial
                        self._eventSignal.emit(payload)
                    except json.JSONDecodeError:
                        self._append_log_for_dut(serial, f"[event-decode-error] {buffer.strip()}", domain="runner", source="events")
                return
            time.sleep(0.1)

    def _wait_for_completion(self, serial: str, session: TestRunSession) -> None:
        returncode = session.process.wait()
        time.sleep(0.2)
        self._finishSignal.emit(serial, returncode)

    def _start_run_background(
        self,
        *,
        run_config: RunConfig,
    ) -> None:
        serial = str(run_config.dut_serial or "").strip()
        try:
            session = start_pytest_run(
                root_dir=self._root_dir,
                run_config=run_config,
            )
            self._sessions[serial] = session
            self._append_log_for_dut(
                serial,
                f"[run] runner session started pid={getattr(session.process, 'pid', '<unknown>')}",
                domain="runner",
                source="RunBridge",
            )
            threading.Thread(target=self._pump_stdout, args=(serial, session), daemon=True).start()
            threading.Thread(target=self._pump_events, args=(serial, session), daemon=True).start()
            threading.Thread(target=self._wait_for_completion, args=(serial, session), daemon=True).start()
        except Exception as exc:  # noqa: BLE001
            self._append_exception_log(exc, source="RunBridge.start_background")
            self.errorOccurred.emit(self.tr("Failed to start test run. {detail}").format(detail=str(exc)))
            self._finishSignal.emit(serial, 1)

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

    def _append_log_for_dut(
        self,
        serial: str,
        line: str,
        *,
        domain: str = "runner",
        level: str = "info",
        source: str = "stdout",
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload_extra = dict(extra or {})
        payload_extra.setdefault("dut_serial", serial)
        record = smart_log(
            line,
            domain=domain,
            level=level,
            source=source,
            extra=payload_extra,
            emit_runtime_event=False,
        )
        self._append_log_record(record, serial=serial)

    def _append_log_record(self, record: Any, *, serial: str = "") -> None:
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
        target_serial = str(serial or row.get("extra", {}).get("dut_serial", "") if isinstance(row.get("extra"), dict) else serial).strip()
        context = self._contexts.get(target_serial)
        if context is not None:
            context.append_log(row)
        else:
            smarttest_context().append_log(row)
        self.logsChanged.emit()

    def _apply_event(self, payload: dict[str, Any]) -> None:
        serial = str(payload.get("dut_serial", "") or "").strip()
        context = self._contexts.get(serial, smarttest_context())
        context.apply_event(payload, min_running_display_sec=self._MIN_STEP_RUNNING_DISPLAY_SEC)
        if str(payload.get("type", "")) == "log":
            self.logsChanged.emit()
        else:
            self.stepsChanged.emit()

    def _finish_run(self, serial: str, returncode: int) -> None:
        normalized_serial = str(serial or "").strip()
        if not normalized_serial:
            normalized_serial = "<default>"
        self._returncodes[normalized_serial] = int(returncode)
        self._statuses[normalized_serial] = "stopped" if self._stop_requested else ("passed" if returncode == 0 else "failed")
        report: dict[str, Any] = {}
        if self._stop_requested:
            self._append_log_for_dut(normalized_serial, "[run] stopped")
        elif returncode == 0:
            self._append_log_for_dut(normalized_serial, "[run] completed successfully")
        else:
            self._append_log_for_dut(normalized_serial, f"[run] failed with exit code {returncode}")
            session = self._sessions.get(normalized_serial)
            if session is not None:
                session.cleanup_failed_run(f"pytest failed with exit code {returncode}")
        try:
            context = self._contexts.get(normalized_serial)
            if context is None:
                context = smarttest_context()
            report = context.finish_run(
                returncode=returncode,
                stopped=self._stop_requested,
                finished_at=self._now_iso(),
            )
            self._finished_reports[normalized_serial] = dict(report)
            try:
                save_run_report(report, reports_dir=self._default_reports_dir())
            except OSError as exc:
                self.errorOccurred.emit(self.tr("Failed to save run report. {detail}").format(detail=str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._append_exception_log(exc, source="RunBridge.finish_run")
            self.errorOccurred.emit(self.tr("Failed to finish test run. {detail}").format(detail=str(exc)))
        finally:
            session = self._sessions.pop(normalized_serial, None)
            if session is not None:
                try:
                    session.cleanup()
                except Exception as exc:  # noqa: BLE001
                    self._append_exception_log(exc, source="RunBridge.cleanup")
            self.stepsChanged.emit()
            self.logsChanged.emit()
            if not self._sessions and all(value is not None for value in self._returncodes.values()):
                batch_report: dict[str, Any] = {}
                if len(self._finished_reports) > 1:
                    batch_report = self._save_batch_report()
                self._session = None
                self._set_running(False)
                failed = [code for code in self._returncodes.values() if int(code or 0) != 0]
                preferred = batch_report or next(iter(self._finished_reports.values()), {})
                self.runFinished.emit(
                    {
                        "returncode": 1 if failed else 0,
                        "stopped": bool(self._stop_requested),
                        "run_id": str(preferred.get("run_id", "") if isinstance(preferred, dict) else ""),
                    }
                )

    def _save_batch_report(self) -> dict[str, Any]:
        finished_at = self._now_iso()
        results: list[dict[str, Any]] = []
        for serial, report in self._finished_reports.items():
            results.append(
                {
                    "dut_serial": serial,
                    "run_id": str(report.get("run_id", "") or ""),
                    "status": str(report.get("status", "") or self._statuses.get(serial, "")),
                    "returncode": int(report.get("returncode", self._returncodes.get(serial) or 0) or 0),
                    "duration_ms": int(report.get("duration_ms", 0) or 0),
                    "counts": dict(report.get("counts", {}) if isinstance(report.get("counts"), dict) else {}),
                }
            )
        counts = {
            "total": len(results),
            "passed": sum(1 for item in results if item.get("status") == "passed"),
            "failed": sum(1 for item in results if item.get("status") == "failed"),
            "skipped": 0,
            "running": 0,
        }
        status = "stopped" if self._stop_requested else ("failed" if counts["failed"] else "passed")
        first_config = next(iter(self._run_configs.values()), RunConfig())
        report = {
            "kind": "batch",
            "run_id": uuid4().hex,
            "title": f"{finished_at.replace('T', ' ')[:19]}  Batch {status}",
            "started_at": next(iter(self._finished_reports.values()), {}).get("started_at", finished_at),
            "finished_at": finished_at,
            "duration_ms": max((int(item.get("duration_ms", 0) or 0) for item in results), default=0),
            "returncode": 1 if status == "failed" else 0,
            "stopped": self._stop_requested,
            "status": status,
            "adb_serial": f"{len(results)} DUTs",
            "selected_nodeids": list(first_config.nodeids),
            "summary": counts,
            "counts": counts,
            "cases": [],
            "steps": [],
            "logs": [],
            "dut_results": results,
        }
        save_run_report(report, reports_dir=self._default_reports_dir())
        return report

    @Slot(result=bool)
    def hasLogs(self) -> bool:
        return any(context.has_logs() for context in self._contexts.values()) or smarttest_context().has_logs()

    @Slot(result=bool)
    def hasSteps(self) -> bool:
        return any(context.has_steps() for context in self._contexts.values()) or smarttest_context().has_steps()

    @Slot(result="QVariantList")
    def logRows(self):
        if self._contexts:
            first = next(iter(self._contexts.values()))
            return first.log_rows()
        return smarttest_context().log_rows()

    @Slot(result=str)
    def logText(self) -> str:
        return "\n".join(str(item.get("line", "")) for item in self.logRows())

    @Slot(result="QVariantList")
    def stepRows(self):
        if self._contexts:
            first = next(iter(self._contexts.values()))
            return first.step_rows()
        return smarttest_context().step_rows()

    @Slot(result="QVariantList")
    def dutRunRows(self):
        rows: list[dict[str, Any]] = []
        for serial, context in self._contexts.items():
            steps = context.step_rows()
            logs = context.log_rows()
            case_rows = [row for row in steps if str(row.get("kind", "") or "") == "case"]
            total = len(case_rows)
            completed = sum(1 for row in case_rows if str(row.get("status", "") or "") in {"passed", "failed", "skipped"})
            failed = sum(1 for row in case_rows if str(row.get("status", "") or "") == "failed")
            running = sum(1 for row in case_rows if str(row.get("status", "") or "") == "running")
            planned = sum(1 for row in case_rows if str(row.get("status", "") or "") == "planned")
            status = self._statuses.get(serial, "running" if self._running else "planned")
            if failed:
                status = "failed"
            elif running:
                status = "running"
            elif total and completed == total and status == "running":
                status = "passed"
            rows.append(
                {
                    "dut_serial": serial,
                    "status": status,
                    "total": total,
                    "completed": completed,
                    "failed": failed,
                    "running": running,
                    "planned": planned,
                    "progress_text": f"{completed}/{total}" if total else "0/0",
                    "steps": steps,
                    "logs": logs,
                    "log_count": len(logs),
                }
            )
        return rows

    @Slot(result=bool)
    def startRun(self) -> bool:
        if self._running:
            return False
        try:
            run_config = self._selected_run_config()
            nodeids = list(run_config.nodeids)
            dut_serials = list(run_config.dut_serials or ([run_config.dut_serial] if run_config.dut_serial else []))
            if not nodeids:
                self.errorOccurred.emit(self.tr("No selected test cases to run."))
                return False

            validation_issues = self._validate_current_run_request(run_config.dut_serial)
            if validation_issues:
                self.validationFailed.emit(self._format_run_validation_message(validation_issues))
                return False

            self._reset_run_data()
            started_at = self._now_iso()
            for serial in dut_serials:
                per_dut_config = replace(run_config, dut_serial=serial, dut_serials=[serial])
                context = TestContext()
                context.params.bind_ui_state(load_state(self._default_state_path()))
                context.begin_run(root_dir=self._root_dir, run_config=per_dut_config, started_at=started_at)
                self._contexts[serial] = context
                self._run_configs[serial] = per_dut_config
                self._returncodes[serial] = None
                self._statuses[serial] = "running"
            self._stop_requested = False
            for serial in dut_serials:
                self._append_start_diagnostics(nodeids=nodeids, adb_serial=serial)
            self.stepsChanged.emit()
        except Exception as exc:  # noqa: BLE001
            self._append_exception_log(exc, source="RunBridge.startRun")
            self.errorOccurred.emit(self.tr("Failed to start pytest run. {detail}").format(detail=str(exc)))
            return False

        self._session = None
        self._set_running(True)

        for serial in dut_serials:
            threading.Thread(
                target=self._start_run_background,
                kwargs={
                    "run_config": self._run_configs[serial],
                },
                daemon=True,
            ).start()
        return True

    @Slot()
    def stopRun(self) -> None:
        if not self._running:
            return
        self._stop_requested = True
        for session in list(self._sessions.values()):
            session.stop("UI stop button")

    @Slot(result=bool)
    def toggleRun(self) -> bool:
        if self._running:
            self.stopRun()
            return True
        return self.startRun()

    def _get_is_running(self) -> bool:
        return self._running

    isRunning = Property(bool, _get_is_running, notify=runningChanged)
