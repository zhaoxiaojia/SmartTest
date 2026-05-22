from __future__ import annotations

import json
import re
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QStandardPaths, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

from testing.reporting import ReportStore, build_run_report
from testing.cases.catalog import is_packaged_runtime
from testing.runner.config import RunConfig, build_run_config_from_state, resolve_dut_serial
from testing.runner.execution import TestRunSession, start_pytest_run
from testing.steps import build_step_plan
from testing.state.store import load_state


class RunBridge(QObject):
    runningChanged = Signal()
    logsChanged = Signal()
    stepsChanged = Signal()
    errorOccurred = Signal(str)

    _logSignal = Signal(str)
    _eventSignal = Signal("QVariantMap")
    _finishSignal = Signal(int)
    _MIN_STEP_RUNNING_DISPLAY_SEC = 0.12
    _LOOP_ID_RE = re.compile(r"^(?P<prefix>.+?)\.(?P<marker>cycle|loop)(?:\.(?P<index>\d+))?\.(?P<tail>.+)$", re.IGNORECASE)
    _LOOP_TITLE_RE = re.compile(
        r"^(?P<marker>\s*(?:cycle|loop))(?:\s+(?P<index>\d+)\s*/\s*(?P<total>\d+))?(?P<suffix>\s*:.*)$",
        re.IGNORECASE,
    )
    _LOOP_PAREN_TITLE_RE = re.compile(
        r"^(?P<head>.*?)(?P<marker>cycle|loop)?\s*\((?P<index>\d+)\s*/\s*(?P<total>\d+)\)\s*$",
        re.IGNORECASE,
    )
    def __init__(self, root_dir: Path):
        super().__init__(QGuiApplication.instance())
        self._root_dir = root_dir.resolve()
        run_logs_dir = self._default_run_logs_dir()
        self._stdout_log_path = run_logs_dir / "tmp_main_stdout.log"
        self._stderr_log_path = run_logs_dir / "tmp_main_stderr.log"
        self._stdout_mirror_log_path = self._root_dir / "tmp_main_stdout.log"
        self._stderr_mirror_log_path = self._root_dir / "tmp_main_stderr.log"
        self._running = False
        self._logs: list[dict[str, Any]] = []
        self._steps: list[dict[str, Any]] = []
        self._step_index: dict[str, int] = {}
        self._step_alias_index: dict[tuple[str, str], str | None] = {}
        self._initial_step_keys: set[tuple[str, str]] = set()
        self._runtime_added_step_keys: set[tuple[str, str]] = set()
        self._building_initial_plan = False
        self._hidden_step_ids: set[str] = set()
        self._step_started_at: dict[str, float] = {}
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

    def _default_run_logs_dir(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "run_logs"

    def _now_iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _trace_timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def _resolve_adb_serial(self, saved_dut: str) -> str | None:
        normalized_saved = str(saved_dut or "").strip()
        print(f"{self._trace_timestamp()} [RunBridge] saved dut: {normalized_saved or '<empty>'}")
        return resolve_dut_serial(normalized_saved)

    def _selected_run_config(self) -> RunConfig:
        state = load_state(self._default_state_path())
        run_config, diagnostics = build_run_config_from_state(root_dir=self._root_dir, state=state)
        for line in diagnostics:
            print(line)
            self._append_log(line)
        return run_config

    def _selected_run_inputs(self) -> tuple[list[str], str, dict[str, dict[str, Any]]]:
        run_config = self._selected_run_config()
        return (
            list(run_config.nodeids),
            str(run_config.global_context.get("dut", "") or ""),
            {key: dict(value) for key, value in run_config.case_configs.items()},
        )

    def _set_running(self, running: bool) -> None:
        if self._running == running:
            return
        self._running = running
        self._append_log(f"[run.trace] running={self._running}")
        self.runningChanged.emit()

    def _reset_run_data(self) -> None:
        self._logs = []
        self._steps = []
        self._step_index = {}
        self._step_alias_index = {}
        self._initial_step_keys = set()
        self._runtime_added_step_keys = set()
        self._building_initial_plan = False
        self._hidden_step_ids = set()
        self._step_started_at = {}
        self._write_local_log(self._stdout_log_path, "", mode="w")
        self._write_local_log(self._stderr_log_path, "", mode="w")
        self._write_local_log(self._stdout_mirror_log_path, "", mode="w", required=False)
        self._write_local_log(self._stderr_mirror_log_path, "", mode="w", required=False)
        self.logsChanged.emit()
        self.stepsChanged.emit()

    def _begin_report_context(self, *, nodeids: list[str], adb_serial: str | None) -> None:
        self._run_id = uuid4().hex
        self._run_started_at = self._now_iso()
        self._run_started_monotonic = time.monotonic()
        self._run_selected_nodeids = list(nodeids)
        self._run_adb_serial = adb_serial

    def _write_local_log(self, path: Path, text: str, *, mode: str = "a", required: bool = True) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open(mode, encoding="utf-8") as fh:
                fh.write(text)
                if mode != "w" or text:
                    fh.write("\n")
            return True
        except OSError as exc:
            if required:
                print(f"{self._trace_timestamp()} [RunBridge] failed to write log {path}: {exc}")
            return False

    def _append_local_log(self, path: Path, text: str) -> None:
        if not self._write_local_log(path, text):
            return
        mirror = None
        if path == self._stdout_log_path:
            mirror = self._stdout_mirror_log_path
        elif path == self._stderr_log_path:
            mirror = self._stderr_mirror_log_path
        if mirror is not None:
            self._write_local_log(mirror, text, required=False)

    def _append_traceback_log(self, exc: BaseException) -> None:
        for line in traceback.format_exception(type(exc), exc, exc.__traceback__):
            for entry in line.rstrip().splitlines():
                self._append_local_log(self._stderr_log_path, entry)

    def _append_start_diagnostics(self, *, nodeids: list[str], adb_serial: str | None) -> None:
        diagnostics = [
            f"[run] diagnostics log: {self._stdout_log_path}",
            f"[run] root_dir: {self._root_dir}",
            f"[run] packaged_runtime: {is_packaged_runtime()}",
            f"[run] selected cases: {len(nodeids)}",
            f"[run] adb_serial: {adb_serial or '<auto>'}",
        ]
        for line in diagnostics:
            self._append_log(line)

    def _append_initial_step_plan(self, *, nodeids: list[str], case_configs: dict[str, dict[str, Any]]) -> None:
        self._building_initial_plan = True
        try:
            for nodeid in nodeids:
                case_title = nodeid.rsplit("::", 1)[-1] if "::" in nodeid else nodeid
                case_row_id = self._ensure_case_row(case_nodeid=nodeid, title=case_title)
                config = dict(case_configs.get(nodeid, {}))
                plan_items = build_step_plan(root_dir=self._root_dir, nodeid=nodeid, case_config=config)
                self._append_log(
                    "[steps.trace] initial_plan_loaded "
                    f"case={nodeid} items={len(plan_items)} config_keys={','.join(sorted(config)) or '<none>'}"
                )
                for item in plan_items:
                    raw_step_id = str(item.get("id", "") or "step")
                    definition_id = str(item.get("definition_id", "") or raw_step_id)
                    self._append_log(
                        "[steps.trace] initial_step "
                        f"case={nodeid} id={raw_step_id} kind={str(item.get('kind', 'action') or 'action')} "
                        f"definition_id={definition_id}"
                    )
                    self._upsert_step_row(
                        {
                            "step_id": f"plan:{nodeid}:{raw_step_id}",
                            "case_nodeid": nodeid,
                            "parent_id": case_row_id,
                            "title": str(item.get("title", "") or raw_step_id),
                            "kind": str(item.get("kind", "action") or "action"),
                            "definition_id": definition_id,
                            "params": dict(item.get("params", {}) if isinstance(item.get("params", {}), dict) else {}),
                            "expected": item.get("expected", ""),
                        },
                        status="planned",
                    )
        finally:
            self._building_initial_plan = False

    def _start_run_session(
        self,
        run_config: RunConfig,
    ) -> TestRunSession:
        return start_pytest_run(
            root_dir=self._root_dir,
            nodeids=run_config.nodeids,
            run_config=run_config,
        )

    def _pump_stdout(self, session: TestRunSession) -> None:
        if session.process.stdout is None:
            self._logSignal.emit("[run.trace] stdout pump skipped: no stdout pipe")
            return
        self._logSignal.emit(
            f"[run.trace] stdout pump start pid={getattr(session.process, 'pid', '<unknown>')}"
        )
        for line in session.process.stdout:
            self._logSignal.emit(line.rstrip())
        self._logSignal.emit(
            f"[run.trace] stdout pump ended poll={session.process.poll()}"
        )

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
        self._logSignal.emit(
            f"[run.trace] wait_for_completion start pid={getattr(session.process, 'pid', '<unknown>')}"
        )
        returncode = session.process.wait()
        self._logSignal.emit(f"[run.trace] process.wait returned {returncode}")
        time.sleep(0.2)
        self._finishSignal.emit(returncode)

    def _start_run_background(
        self,
        *,
        run_config: RunConfig,
    ) -> None:
        try:
            self._run_adb_serial = run_config.dut_serial
            session = self._start_run_session(run_config)
            self._session = session
            self._logSignal.emit(
                f"[run] runner session started pid={getattr(session.process, 'pid', '<unknown>')}"
            )
            threading.Thread(target=self._pump_stdout, args=(session,), daemon=True).start()
            threading.Thread(target=self._pump_events, args=(session,), daemon=True).start()
            threading.Thread(target=self._wait_for_completion, args=(session,), daemon=True).start()
        except Exception as exc:  # noqa: BLE001
            self._append_local_log(self._stderr_log_path, str(exc))
            self._append_traceback_log(exc)
            self.errorOccurred.emit(self.tr("Failed to start test run. {detail}").format(detail=str(exc)))
            self._finishSignal.emit(1)

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
                "parent_id": "",
                "params": {},
                "expected": "",
                "actual": "",
                "error": "",
                "duration_ms": 0,
                "evidence": [],
            }
        )
        self._remember_step_row(self._steps[-1])
        self.stepsChanged.emit()
        return row_id

    def _step_key(self, row: dict[str, Any]) -> tuple[str, str]:
        case_nodeid = str(row.get("case_nodeid", "") or "")
        raw_id = str(row.get("id", "") or "").rsplit(":", 1)[-1]
        definition_id = str(row.get("definition_id", "") or "")
        if ".cycle." in raw_id or ".loop." in raw_id:
            stable_id = raw_id
        else:
            stable_id = definition_id or raw_id or str(row.get("title", "") or "")
        return case_nodeid, stable_id

    def _step_snapshot_for_compare(self) -> list[dict[str, str]]:
        return [
            {
                "case_nodeid": str(row.get("case_nodeid", "") or ""),
                "id": str(row.get("id", "") or ""),
                "kind": str(row.get("kind", "") or ""),
                "definition_id": str(row.get("definition_id", "") or ""),
                "title": str(row.get("title", "") or ""),
                "status": str(row.get("status", "") or ""),
            }
            for row in self._steps
        ]

    def _remember_step_row(self, row: dict[str, Any]) -> None:
        key = self._step_key(row)
        if self._building_initial_plan:
            self._initial_step_keys.add(key)
            return
        if key in self._initial_step_keys or key in self._runtime_added_step_keys:
            return
        self._runtime_added_step_keys.add(key)

    def _log_unmatched_runtime_step(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self._append_log(
            "[steps.trace] unmatched_runtime_step "
            f"event={event_type} case={str(payload.get('case_nodeid', '') or '<empty>')} "
            f"step_id={str(payload.get('step_id', '') or payload.get('id', '') or '<empty>')} "
            f"definition_id={str(payload.get('definition_id', '') or '<empty>')} "
            f"kind={str(payload.get('kind', '') or '<empty>')} "
            f"title={str(payload.get('title', '') or '<empty>')}"
        )

    def _step_aliases(self, payload: dict[str, Any]) -> list[str]:
        aliases: list[str] = []
        for key in ("step_id", "id", "definition_id", "title"):
            value = str(payload.get(key, "") or "").strip()
            if value:
                aliases.append(value)
                aliases.append(value.rsplit(":", 1)[-1])
        raw_id = str(payload.get("step_id", "") or payload.get("id", "") or "").rsplit(":", 1)[-1]
        segments = [part for part in raw_id.replace("-", ".").replace("_", ".").split(".") if part]
        for index in range(len(segments)):
            aliases.append("_".join(segments[index:]))
        normalized: list[str] = []
        for value in aliases:
            item = "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
            if item and item not in normalized:
                normalized.append(item)
        return normalized

    def _register_step_aliases(self, row_id: str, payload: dict[str, Any]) -> None:
        case_nodeid = str(payload.get("case_nodeid", "") or "")
        for alias in self._step_aliases(payload):
            key = (case_nodeid, alias)
            existing = self._step_alias_index.get(key)
            if existing is None and key in self._step_alias_index:
                continue
            if existing is not None and existing != row_id:
                self._step_alias_index[key] = None
                continue
            self._step_alias_index[key] = row_id

    def _rebuild_step_lookup(self) -> None:
        self._step_index = {}
        self._step_alias_index = {}
        for index, row in enumerate(self._steps):
            row_id = str(row.get("id", "") or "")
            if not row_id:
                continue
            self._step_index[row_id] = index
            self._register_step_aliases(row_id, {"step_id": row_id, **row})

    def _resolve_step_row_id(self, payload: dict[str, Any]) -> str:
        step_id = str(payload.get("step_id", "") or payload.get("id", ""))
        if step_id in self._step_index:
            index = self._step_index[step_id]
            row_id = str(self._steps[index].get("id", "") or step_id)
            self._register_step_aliases(row_id, payload)
            return row_id
        case_nodeid = str(payload.get("case_nodeid", "") or "")
        for alias in self._step_aliases(payload):
            row_id = self._step_alias_index.get((case_nodeid, alias))
            if row_id and row_id in self._step_index:
                self._step_index[step_id] = self._step_index[row_id]
                self._register_step_aliases(row_id, payload)
                return row_id
        return step_id

    def _sync_loop_group_progress(self, *, row_id: str, payload: dict[str, Any]) -> bool:
        source_id = str(payload.get("step_id", "") or payload.get("id", ""))
        source_match = self._LOOP_ID_RE.match(source_id.rsplit(":", 1)[-1])
        if source_match is None:
            source_match = self._LOOP_ID_RE.match(row_id.rsplit(":", 1)[-1])
        title = str(payload.get("title", "") or "").strip()
        title_match = self._LOOP_TITLE_RE.match(title)
        paren_title_match = self._LOOP_PAREN_TITLE_RE.match(title)
        meta = dict(payload.get("meta", {}) if isinstance(payload.get("meta", {}), dict) else {})
        case_nodeid = str(payload.get("case_nodeid", "") or "")
        progress_index = ""
        progress_total = ""
        if title_match is not None:
            progress_index = str(title_match.group("index") or "")
            progress_total = str(title_match.group("total") or "")
        if (not progress_index or not progress_total) and paren_title_match is not None:
            progress_index = str(paren_title_match.group("index") or "")
            progress_total = str(paren_title_match.group("total") or "")
        if not progress_index or not progress_total:
            progress_index = str(meta.get("index", "") or "")
            progress_total = str(meta.get("total", "") or "")
        if source_match is None or not progress_index or not progress_total:
            return False
        group_prefix = source_match.group("prefix")
        marker = source_match.group("marker").lower()
        progress = f"{progress_index}/{progress_total}"
        current_index = self._step_index.get(row_id, -1)
        updated_count = 0
        reset_count = 0
        for item in self._steps:
            if str(item.get("case_nodeid", "") or "") != case_nodeid:
                continue
            item_id = str(item.get("id", "") or "")
            row_match = self._LOOP_ID_RE.match(str(item.get("id", "") or "").rsplit(":", 1)[-1])
            title_match = self._LOOP_TITLE_RE.match(str(item.get("title", "") or "").strip())
            if row_match is None or title_match is None:
                continue
            if row_match.group("prefix") != group_prefix or row_match.group("marker").lower() != marker:
                continue
            label = title_match.group("marker")
            new_title = f"{label} {progress}{title_match.group('suffix')}"
            if new_title == str(item.get("title", "") or ""):
                pass
            else:
                item["title"] = new_title
                updated_count += 1
            item_index = self._step_index.get(item_id, -1)
            if current_index >= 0 and item_index > current_index and str(item.get("status", "") or "") != "planned":
                item["status"] = "planned"
                item["actual"] = ""
                item["error"] = ""
                item["duration_ms"] = 0
                reset_count += 1
        if updated_count == 0 and reset_count == 0:
            return False
        self._append_log(
            "[steps.trace] cycle_progress "
            f"case={case_nodeid} source={source_id or '<empty>'} progress={progress} "
            f"updated={updated_count} reset={reset_count}"
        )
        return True

    def _is_framework_step(self, payload: dict[str, Any]) -> bool:
        definition_id = str(payload.get("definition_id", "") or "")
        return definition_id in {"android_client.run_case", "android_client.stage"}

    def _is_case_execute_summary_step(self, payload: dict[str, Any]) -> bool:
        original_step_id = str(payload.get("step_id", "") or payload.get("id", "") or "")
        raw_id = original_step_id.rsplit(":", 1)[-1]
        definition_id = str(payload.get("definition_id", "") or "")
        title = str(payload.get("title", "") or "").strip().lower()
        return (
            title.startswith("execute ")
            and (raw_id.endswith(".execute") or definition_id.endswith(".execute") or raw_id == "execute_case")
        )

    def _upsert_step_row(self, payload: dict[str, Any], *, status: str, allow_create: bool = True) -> str:
        case_nodeid = str(payload.get("case_nodeid", ""))
        parent_id = str(payload.get("parent_id") or self._ensure_case_row(case_nodeid=case_nodeid, title=case_nodeid))
        parent_index = self._step_index.get(parent_id)
        parent_depth = int(self._steps[parent_index].get("depth", 0)) if parent_index is not None else 0
        original_step_id = str(payload.get("step_id", "") or payload.get("id", ""))
        if self._is_framework_step(payload) or self._is_case_execute_summary_step(payload):
            if original_step_id:
                self._hidden_step_ids.add(original_step_id)
            return original_step_id
        step_id = original_step_id if self._building_initial_plan else self._resolve_step_row_id(payload)
        if not step_id:
            return ""
        row = {
            "id": step_id,
            "title": str(payload.get("title", "")),
            "status": status,
            "depth": parent_depth + 1,
            "phase": str(payload.get("phase", "call")),
            "kind": str(payload.get("kind", "action")),
            "definition_id": str(payload.get("definition_id", "") or ""),
            "case_nodeid": case_nodeid,
            "parent_id": parent_id,
            "params": dict(payload.get("params", {}) if isinstance(payload.get("params", {}), dict) else {}),
            "expected": payload.get("expected", ""),
            "actual": payload.get("actual", ""),
            "error": str(payload.get("error", "") or ""),
            "duration_ms": int(payload.get("duration_ms", 0) or 0),
            "evidence": [],
        }
        index = self._step_index.get(step_id)
        if index is None:
            if not allow_create:
                self._log_unmatched_runtime_step(event_type=f"step_{status}", payload=payload)
                if original_step_id:
                    self._hidden_step_ids.add(original_step_id)
                return ""
            self._step_index[step_id] = len(self._steps)
            self._steps.append(row)
            self._register_step_aliases(step_id, payload)
            self._remember_step_row(row)
        else:
            if status == "planned":
                existing = self._steps[index]
                self._register_step_aliases(step_id, payload)
                return step_id
            existing = self._steps[index]
            evidence = list(existing.get("evidence", []) or [])
            preserved_parent_id = existing.get("parent_id", "")
            preserved_depth = existing.get("depth", row["depth"])
            preserved_definition_id = existing.get("definition_id", "")
            update_values = {key: value for key, value in row.items() if value not in ("", {}, [])}
            matched_by_alias = original_step_id and original_step_id != step_id
            incoming_loop = self._LOOP_ID_RE.match(original_step_id.rsplit(":", 1)[-1]) is not None
            existing_loop = self._LOOP_ID_RE.match(str(existing.get("id", "") or "").rsplit(":", 1)[-1]) is not None
            if matched_by_alias and incoming_loop and existing_loop:
                update_values.pop("title", None)
            existing.update(update_values)
            if preserved_parent_id and parent_id not in self._step_index:
                existing["parent_id"] = preserved_parent_id
                existing["depth"] = preserved_depth
            if preserved_definition_id and row.get("definition_id"):
                existing["definition_id"] = preserved_definition_id
            existing["status"] = status
            existing["evidence"] = evidence
            self._register_step_aliases(step_id, payload)
        self.stepsChanged.emit()
        return step_id

    def _apply_step_finished(self, payload: dict[str, Any]) -> None:
        original_step_id = str(payload.get("step_id", ""))
        if original_step_id in self._hidden_step_ids:
            return
        step_id = self._resolve_step_row_id(payload)
        index = self._step_index.get(step_id)
        if index is None:
            self._log_unmatched_runtime_step(event_type="step_finished", payload=payload)
            return

        started_at = self._step_started_at.get(step_id)
        if started_at is not None and not payload.get("_smarttest_delayed_finish"):
            now = float(payload.get("timestamp", time.time()) or time.time())
            remaining_sec = self._MIN_STEP_RUNNING_DISPLAY_SEC - max(0.0, now - started_at)
            if remaining_sec > 0:
                delayed_payload = dict(payload)
                delayed_payload["_smarttest_delayed_finish"] = True
                delayed_payload["_smarttest_started_at"] = started_at
                delay_ms = max(1, int(remaining_sec * 1000))
                self._append_log(
                    "[steps.trace] defer_finish "
                    f"case={str(payload.get('case_nodeid', '') or '<empty>')} "
                    f"step_id={step_id} delay_ms={delay_ms}"
                )
                QTimer.singleShot(delay_ms, lambda p=delayed_payload: self._apply_event(p))
                return

        if payload.get("_smarttest_delayed_finish") and started_at != payload.get("_smarttest_started_at"):
            self._append_log(
                "[steps.trace] drop_stale_deferred_finish "
                f"case={str(payload.get('case_nodeid', '') or '<empty>')} step_id={step_id}"
            )
            return

        self._steps[index]["status"] = str(payload.get("status", "passed"))
        self._steps[index]["actual"] = payload.get("actual", "")
        self._steps[index]["error"] = str(payload.get("error", "") or "")
        if "duration_ms" in payload:
            self._steps[index]["duration_ms"] = int(payload.get("duration_ms", 0) or 0)
        else:
            started_at = self._step_started_at.pop(step_id, None)
            if started_at is not None:
                self._steps[index]["duration_ms"] = int(
                    (float(payload.get("timestamp", time.time())) - started_at) * 1000
                )
        self.stepsChanged.emit()
        error = str(payload.get("error", "") or "").strip()
        if error:
            self._append_log(f"[step-error] {error}")

    def _apply_event(self, payload: dict[str, Any]) -> None:
        event_type = str(payload.get("type", ""))
        if event_type == "case_started":
            self._ensure_case_row(
                case_nodeid=str(payload.get("case_nodeid", "")),
                title=str(payload.get("title", "")),
            )
            return

        if event_type == "case_finished":
            case_nodeid = str(payload.get("case_nodeid", "") or "")
            planned_count = sum(
                1
                for row in self._steps
                if str(row.get("case_nodeid", "") or "") == case_nodeid
                and str(row.get("status", "") or "") == "planned"
                and str(row.get("kind", "") or "") != "case"
            )
            if planned_count:
                self._append_log(
                    "[steps.trace] case_finished_kept_planned "
                    f"case={case_nodeid} status={str(payload.get('status', '') or '<empty>')} count={planned_count}"
                )
            row_id = f"case:{case_nodeid}"
            index = self._step_index.get(row_id)
            if index is not None:
                self._steps[index]["status"] = str(payload.get("status", "passed"))
                self._steps[index]["duration_ms"] = int(payload.get("duration_ms", 0) or 0)
                self.stepsChanged.emit()
            return

        if event_type == "step_planned":
            self._upsert_step_row(payload, status="planned", allow_create=False)
            return

        if event_type == "step_started":
            step_id = self._upsert_step_row(payload, status="running", allow_create=False)
            if not step_id:
                return
            loop_changed = self._sync_loop_group_progress(row_id=step_id, payload=payload)
            self._step_started_at[step_id] = float(payload.get("timestamp", time.time()) or time.time())
            if loop_changed:
                self.stepsChanged.emit()
            return

        if event_type == "step_finished":
            self._apply_step_finished(payload)
            return

        if event_type == "step_evidence":
            step_id = str(payload.get("step_id", "") or "")
            if step_id in self._hidden_step_ids:
                return
            step_id = self._resolve_step_row_id(payload)
            index = self._step_index.get(step_id)
            evidence = {
                "title": str(payload.get("title", "") or ""),
                "type": str(payload.get("evidence_type", "log") or "log"),
                "level": str(payload.get("level", "info") or "info"),
                "content": payload.get("content", ""),
                "meta": dict(payload.get("meta", {}) if isinstance(payload.get("meta", {}), dict) else {}),
            }
            if index is not None:
                items = list(self._steps[index].get("evidence", []) or [])
                items.append(evidence)
                self._steps[index]["evidence"] = items
                self.stepsChanged.emit()
            return

        if event_type == "log":
            message = str(payload.get("message", "")).strip()
            if message:
                self._append_log(message)

    def _finish_run(self, returncode: int) -> None:
        self._append_log(
            f"[run.trace] finish_run enter returncode={returncode} stop_requested={self._stop_requested}"
        )
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
                steps=self._steps,
                logs=self._logs,
            )
            try:
                self._report_store.save(report)
            except OSError as exc:
                self.errorOccurred.emit(self.tr("Failed to save run report. {detail}").format(detail=str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._append_traceback_log(exc)
            self.errorOccurred.emit(self.tr("Failed to finish test run. {detail}").format(detail=str(exc)))
        finally:
            if self._session is not None:
                try:
                    self._session.cleanup()
                except Exception as exc:  # noqa: BLE001
                    self._append_traceback_log(exc)
                self._session = None
            self._set_running(False)
            self._append_log(f"[run.trace] finish_run exit running={self._running}")

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
        try:
            run_config = self._selected_run_config()
            nodeids = list(run_config.nodeids)
            case_configs = {key: dict(value) for key, value in run_config.case_configs.items()}
            if not nodeids:
                self.errorOccurred.emit(self.tr("No selected test cases to run."))
                return

            self._reset_run_data()
            self._begin_report_context(nodeids=nodeids, adb_serial=run_config.dut_serial)
            self._stop_requested = False
            self._append_start_diagnostics(nodeids=nodeids, adb_serial=run_config.dut_serial)
            self._append_initial_step_plan(nodeids=nodeids, case_configs=case_configs)
        except Exception as exc:  # noqa: BLE001
            self._append_local_log(self._stderr_log_path, str(exc))
            self._append_traceback_log(exc)
            self.errorOccurred.emit(self.tr("Failed to start pytest run. {detail}").format(detail=str(exc)))
            return

        self._session = None
        self._set_running(True)

        threading.Thread(
            target=self._start_run_background,
            kwargs={
                "run_config": run_config,
            },
            daemon=True,
        ).start()

    @Slot()
    def stopRun(self) -> None:
        if not self._running or self._session is None:
            self._append_log(
                f"[run.trace] stopRun ignored running={self._running} session={self._session is not None}"
            )
            return
        process = getattr(self._session, "process", None)
        poll_value = process.poll() if process is not None else "<unknown>"
        self._append_log(
            f"[run.trace] stopRun requested pid={getattr(process, 'pid', '<unknown>')} "
            f"poll={poll_value}"
        )
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
