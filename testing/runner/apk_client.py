from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import Mapping

from android_client import PACKAGE_NAME, PRIVILEGED_CASE_IDS
from testing.test_context import smarttest_context
from testing.runtime.config import current_dut_serial
from testing.runtime.steps import step as runtime_step, step_log
from testing.steps.definitions import ActionContext, action_plan, get_action
from testing.params.adb_devices import resolve_adb_serial_for_command
from testing.tool.dut_tool.duts.android import android as AndroidDut
from tools.logging import smart_log


DEFAULT_COMPONENT = "com.smarttest.mobile/com.smarttest.mobile.command.CommandActivity"
DEFAULT_ACTION_RUN = "com.smarttest.mobile.action.RUN"
DEFAULT_ACTION_STOP = "com.smarttest.mobile.action.STOP"
DEFAULT_STATUS_URI = "content://com.smarttest.mobile.status/snapshot"
DEFAULT_STATUS_FILE = "files/runner_snapshot.json"
DEFAULT_PUBLIC_STATUS_FILE = "/sdcard/Android/data/com.smarttest.mobile/files/runner_snapshot.json"
DEFAULT_POLL_INTERVAL_SEC = 1.0
DEFAULT_NO_RESPONSE_TIMEOUT_SEC = 3600.0
DEFAULT_DUT_UNAVAILABLE_STAGE_TOKENS = {
    "rebooting dut",
    "entering deep suspend",
    "waiting for deep suspend resume",
}
DEFAULT_HOST_QUIET_STAGE_TOKENS = {"entering deep suspend", "waiting for deep suspend resume"}
DEFAULT_HOST_QUIET_SEC = 25.0
DEFAULT_ADB_COMMAND_TIMEOUT_SEC = 10.0
_DYNAMIC_STEP_ID_RE = re.compile(r"^(?P<prefix>.+?)\.(?P<marker>cycle|loop)\.(?P<index>\d+)\.(?P<tail>.+)$", re.IGNORECASE)
_PLANNED_REPEAT_STEP_ID_RE = re.compile(r"^(?P<prefix>.+?)\.(?P<marker>cycle|loop)\.(?P<tail>.+)$", re.IGNORECASE)
_STAGE_LOOP_RE = re.compile(r"\b(?P<marker>cycle|loop)\s+(?P<index>\d+)\s*/\s*(?P<total>\d+)\b", re.IGNORECASE)
_TERMINAL_STATUSES = {"passed", "failed", "skipped", "stopped"}
_ADB_DUT_CACHE: dict[str, AndroidDut] = {}


@dataclass
class _ApkStep:
    title: str
    kind: str
    definition_id: str
    step_id: str = field(default_factory=lambda: f"step:{uuid.uuid4().hex}")
    expected: object = ""
    parent_id: str | None = None
    started: bool = False
    finished: bool = False
    enabled: bool = False

    def __post_init__(self) -> None:
        self.enabled = _emit_apk_step("step_planned", self)

    def start(self) -> None:
        if self.enabled and not self.started:
            self.started = _emit_apk_step("step_started", self)

    def evidence(self, title: str, content: object, *, evidence_type: str = "log", level: str = "info") -> None:
        case_nodeid = smarttest_context().current_case_nodeid()
        if not self.enabled or not case_nodeid:
            return
        smarttest_context().events.emit(
            "step_evidence",
            case_nodeid=case_nodeid,
            step_id=self.step_id,
            title=title,
            evidence_type=evidence_type,
            level=level,
            content=content,
            meta={},
        )

    def finish(self, status: str, *, error: str = "", actual: object = "") -> None:
        if not self.enabled or self.finished:
            return
        self.start()
        self.finished = True
        case_nodeid = smarttest_context().current_case_nodeid()
        if case_nodeid:
            smarttest_context().events.emit(
                "step_finished",
                step_id=self.step_id,
                case_nodeid=case_nodeid,
                status=status,
                title=self.title,
                kind=self.kind,
                definition_id=self.definition_id,
                error=error,
                actual=actual,
            )


def _emit_apk_step(event_type: str, step: _ApkStep) -> bool:
    case_nodeid = smarttest_context().current_case_nodeid()
    if not case_nodeid:
        return False
    parent = smarttest_context().current_step()
    smarttest_context().events.emit(
        event_type,
        step_id=step.step_id,
        case_nodeid=case_nodeid,
        parent_id=step.parent_id if step.parent_id is not None else (parent["id"] if parent else None),
        title=step.title,
        phase="call",
        kind=step.kind,
        definition_id=step.definition_id,
        meta={"definition_id": step.definition_id},
        expected=step.expected,
    )
    return True


class ApkStageTracker:
    def __init__(self, *, case_id: str, request_id: str) -> None:
        self._case_id = case_id
        self._request_id = request_id
        self._parent = _ApkStep(
            title=f"Run APK case: {case_id}",
            kind="action",
            definition_id="android_client.run_case",
            expected="APK reports Completed with zero failed cases.",
        )
        self._parent.start()
        self._current_stage: _ApkStep | None = None
        self._current_stage_key = ""
        self._planned_steps: dict[str, _ApkStep] = {}
        self._dynamic_steps: dict[str, _ApkStep] = {}
        self._terminal = False

    def evidence(self, title: str, content: object, *, evidence_type: str = "log", level: str = "info") -> None:
        self._parent.evidence(title, content, evidence_type=evidence_type, level=level)

    def observe_snapshot(self, snapshot: Mapping[str, object]) -> None:
        if not self._parent.enabled:
            return
        self.evidence("APK snapshot", "", evidence_type="status", level="info")
        self._sync_planned_steps(snapshot)
        self._sync_step_states(snapshot)
        if self._planned_steps:
            return
        phase = str(snapshot.get("phase", "") or "").strip()
        stage = str(snapshot.get("currentStage", "") or "").strip() or phase or "waiting for APK status"
        stage_key = f"{phase}:{stage}"
        if stage_key == self._current_stage_key:
            return
        if self._current_stage is not None:
            self._current_stage.finish("passed")
        self._current_stage_key = stage_key
        self._current_stage = _ApkStep(
            title=stage,
            kind="external",
            definition_id="android_client.stage",
            expected="APK advances to the next stage or terminal status.",
            parent_id=self._parent.step_id,
        )
        self._current_stage.start()

    def _sync_planned_steps(self, snapshot: Mapping[str, object]) -> None:
        planned_steps = snapshot.get("plannedSteps", [])
        if not isinstance(planned_steps, list):
            return
        for item in planned_steps:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id", "") or "").strip()
            if not raw_id or raw_id in self._planned_steps:
                continue
            self._planned_steps[raw_id] = _ApkStep(
                step_id=f"{self._request_id}:{raw_id}",
                title=str(item.get("title", "") or raw_id),
                kind=str(item.get("kind", "") or "action"),
                definition_id=str(item.get("definitionId", "") or raw_id),
                expected=str(item.get("expected", "") or ""),
                parent_id=self._parent.step_id,
            )

    def _sync_step_states(self, snapshot: Mapping[str, object]) -> None:
        states = snapshot.get("stepStates", [])
        if not isinstance(states, list):
            return
        for item in states:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id", "") or "").strip()
            step = self._planned_steps.get(raw_id) or self._dynamic_step(raw_id=raw_id, snapshot=snapshot)
            if step is None:
                self._parent.evidence(
                    "[steps.debug.apk_unresolved]",
                    {
                        "raw_id": raw_id,
                        "status": str(item.get("status", "") or ""),
                        "currentStage": str(snapshot.get("currentStage", "") or ""),
                        "currentLoop": snapshot.get("currentLoop", ""),
                        "totalLoops": snapshot.get("totalLoops", ""),
                        "known_planned_ids": sorted(self._planned_steps.keys()),
                        "known_dynamic_ids": sorted(self._dynamic_steps.keys()),
                    },
                    evidence_type="log",
                    level="warning",
                )
                continue
            runtime_title = self._runtime_step_title(raw_id=raw_id, step=step, snapshot=snapshot)
            if runtime_title:
                step.title = runtime_title
            status = str(item.get("status", "") or "").strip()
            if status == "running":
                step.start()
            elif status in _TERMINAL_STATUSES:
                step.finish(status, actual=item.get("actual", ""), error=str(item.get("error", "") or ""))

    def _dynamic_step(self, *, raw_id: str, snapshot: Mapping[str, object]) -> _ApkStep | None:
        if not raw_id:
            return None
        existing = self._dynamic_steps.get(raw_id)
        if existing is not None:
            return existing
        match = _DYNAMIC_STEP_ID_RE.match(raw_id)
        if match is None:
            return None
        step = _ApkStep(
            step_id=f"{self._request_id}:{raw_id}",
            title=self._dynamic_step_title(raw_id=raw_id, snapshot=snapshot),
            kind=self._dynamic_step_kind(match.group("tail")),
            definition_id=f"{match.group('prefix')}.{match.group('marker')}.{match.group('tail')}",
            expected="APK reports this cycle step finished.",
            parent_id=self._parent.step_id,
        )
        self._dynamic_steps[raw_id] = step
        return step

    def _dynamic_step_title(self, *, raw_id: str, snapshot: Mapping[str, object]) -> str:
        match = _DYNAMIC_STEP_ID_RE.match(raw_id)
        if match is None:
            return raw_id
        marker, _, total = self._snapshot_loop_marker(snapshot)
        label = f"{match.group('marker').capitalize()} {match.group('index')}"
        if marker:
            label = f"{marker.capitalize()} {match.group('index')}"
        tail = match.group("tail").replace("_", " ")
        return f"{label}/{total}: {tail}" if total else f"{label}: {tail}"

    def _runtime_step_title(self, *, raw_id: str, step: _ApkStep, snapshot: Mapping[str, object]) -> str:
        dynamic_match = _DYNAMIC_STEP_ID_RE.match(raw_id)
        if dynamic_match is not None:
            return self._dynamic_step_title(raw_id=raw_id, snapshot=snapshot)
        planned_match = _PLANNED_REPEAT_STEP_ID_RE.match(raw_id)
        if planned_match is None:
            return step.title
        marker, index, total = self._snapshot_loop_marker(snapshot)
        if not index or not total:
            return step.title
        title = str(step.title or raw_id)
        suffix = re.sub(r"^(Cycle|Loop)\s*(\d+\s*/\s*\d+)?\s*:\s*", "", title, count=1, flags=re.IGNORECASE).strip()
        prefix = marker.capitalize() if marker else planned_match.group("marker").capitalize()
        return f"{prefix} {index}/{total}: {suffix or planned_match.group('tail').replace('_', ' ')}"

    def _snapshot_loop_marker(self, snapshot: Mapping[str, object]) -> tuple[str, str, str]:
        stage_match = _STAGE_LOOP_RE.search(str(snapshot.get("currentStage", "") or ""))
        marker = stage_match.group("marker") if stage_match else ""
        index = stage_match.group("index") if stage_match else str(snapshot.get("currentLoop", "") or "")
        total = stage_match.group("total") if stage_match else str(snapshot.get("totalLoops", "") or "")
        return marker, index, total

    def _dynamic_step_kind(self, tail: str) -> str:
        normalized = str(tail or "").lower()
        return "check" if any(token in normalized for token in ("check", "verify", "capture", "ping", "bluetooth")) else "step"

    def status_waiting(self, reason: str) -> None:
        target = self._current_stage or self._parent
        target.evidence("Status channel waiting", reason, evidence_type="status", level="warning")

    def finish(self, status: str, *, error: str = "", actual: object = "") -> None:
        if self._terminal:
            return
        self._terminal = True
        if self._planned_steps:
            for step in self._planned_steps.values():
                if step.started:
                    step.finish("stopped" if status == "failed" else status)
        elif self._current_stage is not None:
            self._current_stage.finish(status, error=error if status == "failed" else "", actual=actual)
        self._parent.finish(status, error=error, actual=actual)


def _adb_result_is_offline(result: subprocess.CompletedProcess[str]) -> bool:
    text = f"{result.stdout or ''}\n{result.stderr or ''}".lower()
    return (
        "device offline" in text
        or "offline" in text and "error:" in text
        or "device" in text and "not found" in text
        or "no devices/emulators found" in text
    )


def _run_adb_command(
    *,
    adb_executable: str,
    adb_serial: str | None,
    args: list[str],
    timeout_sec: float = DEFAULT_ADB_COMMAND_TIMEOUT_SEC,
) -> subprocess.CompletedProcess[str]:
    serial = resolve_adb_serial_for_command(adb_serial) or ""
    dut = _ADB_DUT_CACHE.get(serial)
    if dut is None:
        dut = AndroidDut(serialnumber=serial, prepare=False)
        _ADB_DUT_CACHE[serial] = dut
    result = dut.adb_call(*args, timeout=timeout_sec)
    command = getattr(result, "command", [adb_executable, *args])
    return subprocess.CompletedProcess(command, result.returncode, result.stdout, result.stderr)


def _serial_for_log(serial: str | None) -> str:
    text = str(serial or "").strip()
    if not text:
        return "<default>"
    return text.encode("unicode_escape").decode("ascii")


def _stage_tokens(name: str, default: set[str]) -> set[str]:
    raw = str(os.environ.get(name, "") or "").strip()
    return {token.strip().lower() for token in raw.split(",") if token.strip()} if raw else set(default)


def _next_dut_unavailable_wait_state(
    *,
    phase: str,
    current_stage: str,
    matches_request: bool,
    waiting_for_device_resume: bool,
) -> bool:
    if not matches_request:
        return waiting_for_device_resume
    if phase in {"Completed", "Failed"}:
        return False
    if phase != "Running":
        return waiting_for_device_resume
    tokens = _stage_tokens("SMARTTEST_ANDROID_DUT_UNAVAILABLE_STAGE_TOKENS", DEFAULT_DUT_UNAVAILABLE_STAGE_TOKENS)
    if any(token in str(current_stage or "").lower() for token in tokens):
        return True
    return waiting_for_device_resume


def _snapshot_read_failure_key(error_text: str) -> str:
    text = str(error_text or "")
    if "no devices/emulators found" in text:
        return "no devices/emulators found"
    if "Unable to locate JSON payload" in text:
        return "empty status payload"
    if "run-as: package not an application" in text:
        return "run-as unavailable"
    first_line = text.strip().splitlines()[0] if text.strip() else "<empty>"
    return first_line[:160]


def _force_stop_apk(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    package_name: str = PACKAGE_NAME,
) -> subprocess.CompletedProcess[str]:
    result = _run_adb_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["shell", "am", "force-stop", package_name],
    )
    if result.returncode != 0:
        smart_log(
            f"force-stop failed rc={result.returncode} stderr={result.stderr.strip()}",
            level="warning",
            domain="android",
            source="android_client",
        )
    return result


def _prepare_apk_request(context: ActionContext) -> str:
    summary = f"case_id={context.case_id} parameter_count={len(context.params)}"
    step_log(summary)
    return summary


def apk_case_plan(
    case_id: str,
    runtime_definition_ids: list[str] | None = None,
    *,
    prepare_definition_id: str = "android_client.prepare_request",
    trigger_definition_id: str = "android_client.trigger_case",
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "steps": [
            *action_plan([prepare_definition_id, trigger_definition_id]),
            *action_plan(runtime_definition_ids or []),
        ],
    }


def run_apk_case(
    *,
    case_id: str,
    trigger: str,
    prepare_definition_id: str = "android_client.prepare_request",
    trigger_definition_id: str = "android_client.trigger_case",
) -> subprocess.CompletedProcess[str]:
    resolved_params = smarttest_context().params.apk_params(case_id, trigger)
    context = ActionContext(case_id=case_id, params=resolved_params, trigger=trigger)
    prepare_action = get_action(prepare_definition_id)
    with runtime_step(
        prepare_action.title,
        kind=prepare_action.kind,
        definition_id=prepare_action.definition_id,
        expected=prepare_action.expected,
    ):
        _prepare_apk_request(context)

    trigger_action = get_action(trigger_definition_id)
    with runtime_step(
        trigger_action.title,
        kind=trigger_action.kind,
        definition_id=trigger_action.definition_id,
        expected=trigger_action.expected,
        stress_tolerant=False,
    ):
        result = trigger_apk_case(
            case_id=case_id,
            params=resolved_params,
            trigger=trigger,
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if stdout:
            step_log(stdout)
        if stderr:
            step_log(stderr, level="warning")
        return result


def _launch_apk_main(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    package_name: str = PACKAGE_NAME,
) -> subprocess.CompletedProcess[str]:
    component = f"{package_name}/com.smarttest.mobile.MainActivity"
    result = _run_adb_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["shell", "am", "start", "-n", component],
    )
    if result.returncode != 0:
        smart_log(
            f"launch-main failed rc={result.returncode} stderr={result.stderr.strip()}",
            level="warning",
            domain="android",
            source="android_client",
        )
    return result


def _adb_get_state(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
) -> str:
    result = _run_adb_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["get-state"],
    )
    if result.returncode != 0:
        stderr = str(result.stderr or "").strip().lower()
        if "device" in stderr and "not found" in stderr:
            return "not_found"
        return "offline"
    return str(result.stdout or "").strip() or "unknown"


def _adb_is_boot_completed(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
) -> bool | None:
    result = _run_adb_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["shell", "getprop", "sys.boot_completed"],
    )
    if result.returncode != 0:
        return None
    return str(result.stdout or "").strip() == "1"


def _start_apk_run(
    *,
    adb_executable: str,
    component: str,
    case_id: str,
    request_id: str,
    trigger: str,
    source: str,
    params: Mapping[str, str] | None = None,
    adb_serial: str | None = None,
    log_prefix: str = "[testing.runner.apk_client]",
) -> subprocess.CompletedProcess[str]:
    args = [
        "shell",
        "am",
        "start",
        "-n",
        component,
        "-a",
        DEFAULT_ACTION_RUN,
        "--es",
        "case_id",
        case_id,
        "--es",
        "source",
        source,
        "--es",
        "trigger",
        trigger,
        "--es",
        "request_id",
        request_id,
    ]
    if params:
        encoded_params = base64.urlsafe_b64encode(
            json.dumps(dict(params), ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        ).decode("ascii").rstrip("=")
        args.extend(["--es", "params_b64", encoded_params])
    result = _run_adb_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=args,
    )
    if result.returncode != 0:
        smart_log(
            f"{log_prefix} trigger failed rc={result.returncode} stderr={result.stderr.strip()}",
            level="warning",
            domain="android",
            source="android_client",
        )
    return result


def stop_apk_run(
    *,
    adb_serial: str | None = None,
    reason: str = "host stop",
) -> subprocess.CompletedProcess[str]:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        raise RuntimeError("adb is not available in PATH.")

    component = os.environ.get("SMARTTEST_ANDROID_COMPONENT", DEFAULT_COMPONENT)
    result = _run_adb_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=[
            "shell",
            "am",
            "start",
            "-n",
            component,
            "-a",
            DEFAULT_ACTION_STOP,
            "--es",
            "reason",
            reason,
        ],
    )
    return result


def apk_installed(*, adb_serial: str | None = None, package_name: str = PACKAGE_NAME) -> bool:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        raise RuntimeError("adb is not available in PATH.")

    result = _run_adb_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["shell", "pm", "path", package_name],
    )
    if result.returncode != 0:
        if _adb_result_is_offline(result):
            raise RuntimeError(
                "ADB device is unavailable while checking APK install state.\n"
                f"serial={_serial_for_log(adb_serial)}\n"
                f"stderr={str(result.stderr or '').strip()}"
            )
        return False
    return "package:" in str(result.stdout or "")


def _extract_json_payload(raw: str) -> str:
    text = str(raw or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"Unable to locate JSON payload in content output: {text}")
    return text[start : end + 1]


def _run_snapshot_command(
    *,
    adb_executable: str,
    adb_serial: str | None,
    shell_args: list[str],
) -> subprocess.CompletedProcess[str]:
    return _run_adb_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["shell", *shell_args],
    )


def _read_snapshot_json(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    shell_args: list[str],
    failure_label: str,
    require_stdout: bool = True,
) -> dict[str, object]:
    result = _run_snapshot_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=shell_args,
    )
    stdout = str(result.stdout or "").strip()
    stderr = str(result.stderr or "").strip()
    if result.returncode != 0 or (require_stdout and not stdout):
        raise RuntimeError(
            f"{failure_label} snapshot read failed.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}\n"
            f"returncode={result.returncode}"
    )
    return json.loads(_extract_json_payload(stdout))


def read_apk_snapshot(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    status_uri: str = DEFAULT_STATUS_URI,
    verbose: bool = True,
) -> dict[str, object]:
    attempts = [
        ("public-file", ["cat", DEFAULT_PUBLIC_STATUS_FILE], True),
        ("run-as", ["run-as", PACKAGE_NAME, "cat", DEFAULT_STATUS_FILE], True),
        ("content", ["content", "read", "--uri", status_uri], False),
    ]
    for label, shell_args, require_stdout in attempts:
        try:
            return _read_snapshot_json(
                adb_executable=adb_executable,
                adb_serial=adb_serial,
                shell_args=shell_args,
                failure_label=label,
                require_stdout=require_stdout,
            )
        except Exception as exc:  # noqa: BLE001
            if label == "content":
                raise
            if verbose:
                smart_log(f"[android_client.status] {label} fallback: {exc}", level="warning", domain="android", source="android_client")
    raise RuntimeError("APK snapshot read failed without an attempted reader.")


def _snapshot_signature(snapshot: dict[str, object]) -> str:
    return json.dumps(snapshot, sort_keys=True, ensure_ascii=False)


def _snapshot_request_id(snapshot: dict[str, object]) -> str:
    active_request = snapshot.get("activeRequest", {})
    if isinstance(active_request, dict):
        request_id = str(active_request.get("requestId", "") or "")
        if request_id:
            return request_id

    report = snapshot.get("report", {})
    if isinstance(report, dict):
        request_id = str(report.get("requestId", "") or "")
        if request_id:
            return request_id

    return ""


def _no_poll_case_ids() -> set[str]:
    raw = str(os.environ.get("SMARTTEST_ANDROID_NO_POLL_CASES", "") or "").strip()
    return {token.strip() for token in raw.split(",") if token.strip()} if raw else set()


def _slow_poll_case_ids() -> set[str]:
    raw = str(os.environ.get("SMARTTEST_ANDROID_SLOW_POLL_CASES", "") or "").strip()
    return {token.strip() for token in raw.split(",") if token.strip()} if raw else set()


def _snapshot_matches_request(snapshot: dict[str, object], *, request_id: str) -> bool:
    if not request_id:
        return False
    if _snapshot_request_id(snapshot) == request_id:
        return True

    last_command_summary = str(snapshot.get("lastCommandSummary", "") or "")
    return request_id in last_command_summary


def _snapshot_case_ids(snapshot: dict[str, object]) -> list[str]:
    active_request = snapshot.get("activeRequest", {})
    case_ids = active_request.get("caseIds", []) if isinstance(active_request, dict) else []
    return [str(item) for item in case_ids] if isinstance(case_ids, list) else []


def _snapshot_log_count(snapshot: dict[str, object]) -> int:
    try:
        return int(snapshot.get("logCount", 0) or 0)
    except (TypeError, ValueError):
        pass
    log_lines = snapshot.get("logLines", [])
    return len(log_lines) if isinstance(log_lines, list) else 0


def _snapshot_log_start_index(snapshot: dict[str, object]) -> int:
    try:
        return int(snapshot.get("logStartIndex", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _iter_unseen_snapshot_logs(
    snapshot: dict[str, object],
    *,
    seen_log_count: int,
) -> tuple[list[str], int]:
    log_lines = snapshot.get("logLines", [])
    if not isinstance(log_lines, list):
        return [], max(seen_log_count, _snapshot_log_count(snapshot))

    log_start = _snapshot_log_start_index(snapshot)
    log_total = _snapshot_log_count(snapshot)
    if log_total <= 0:
        log_total = log_start + len(log_lines)

    if seen_log_count > log_total:
        seen_log_count = log_start
    first_unseen_offset = max(0, seen_log_count - log_start)
    new_lines = [str(line) for line in log_lines[first_unseen_offset:]]
    return new_lines, max(seen_log_count, log_total)


def _recent_log_text(snapshot: dict[str, object], limit: int) -> str:
    log_lines = snapshot.get("logLines", [])
    return "\n".join(str(item) for item in log_lines[-limit:]) if isinstance(log_lines, list) else ""


def _adb_shell_capture_text(
    *,
    adb_executable: str,
    adb_serial: str | None,
    shell_args: list[str],
) -> tuple[int, str, str]:
    result = _run_snapshot_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=shell_args,
    )
    return result.returncode, str(result.stdout or "").strip(), str(result.stderr or "").strip()


def _collect_device_failure_debug(
    *,
    adb_executable: str,
    adb_serial: str | None,
) -> None:
    probes = [
        ("getprop sys.boot_completed", ["getprop", "sys.boot_completed"]),
        ("getprop sys.powerctl", ["getprop", "sys.powerctl"]),
        ("/proc/uptime", ["cat", "/proc/uptime"]),
    ]
    for label, shell_args in probes:
        code, stdout, stderr = _adb_shell_capture_text(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            shell_args=shell_args,
        )
        smart_log(
            "[android_client.power] "
            f"{label} returncode={code} value={stdout or '<empty>'} "
            f"stderr={stderr or '<empty>'}",
            domain="android", source="android_client")


def wait_for_apk_case_completion(
    *,
    adb_executable: str,
    case_id: str,
    request_id: str,
    trigger: str,
    adb_serial: str | None = None,
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
    no_response_timeout_sec: float = DEFAULT_NO_RESPONSE_TIMEOUT_SEC,
    baseline_signature: str | None = None,
    baseline_log_count: int = 0,
    stage_tracker: ApkStageTracker | None = None,
) -> dict[str, object]:
    started = False
    fresh_run_observed = False
    seen_log_count = max(0, int(baseline_log_count or 0))
    no_response_deadline = time.monotonic() + no_response_timeout_sec
    last_snapshot: dict[str, object] | None = None
    last_error: str = ""
    last_status_line = ""
    waiting_for_device_resume = False
    host_quiet_until = 0.0
    host_quiet_logged = False
    last_device_state = ""
    last_boot_completed: bool | None = None
    last_snapshot_channel_ready = False
    last_snapshot_failure_key = ""

    while True:
        now = time.monotonic()
        if now >= no_response_deadline:
            break
        if (
            waiting_for_device_resume
            and now < host_quiet_until
        ):
            if not host_quiet_logged:
                remaining = max(0.0, host_quiet_until - now)
                smart_log(
                    "[android_client.power] "
                    f"host quiet mode: hold adb polling for {remaining:.1f}s",
                    domain="android", source="android_client")
                host_quiet_logged = True
            time.sleep(poll_interval_sec)
            continue

        if waiting_for_device_resume:
            device_state = _adb_get_state(adb_executable=adb_executable, adb_serial=adb_serial)
            if device_state != last_device_state:
                status = "dut alive" if device_state == "device" else f"dut lost state={device_state or '<empty>'}"
                smart_log(f"[android_client.power] {status}", domain="android", source="android_client")
                last_device_state = device_state
            if device_state == "device":
                boot_completed = _adb_is_boot_completed(adb_executable=adb_executable, adb_serial=adb_serial)
                if boot_completed != last_boot_completed:
                    smart_log(f"[android_client.power] boot_completed={boot_completed}", domain="android", source="android_client")
                    last_boot_completed = boot_completed
            else:
                last_boot_completed = None
            last_snapshot_channel_ready = False

        try:
            snapshot = read_apk_snapshot(
                adb_executable=adb_executable,
                adb_serial=adb_serial,
                verbose=False,
            )
            last_snapshot = snapshot
            last_snapshot_failure_key = ""
            if waiting_for_device_resume and not last_snapshot_channel_ready:
                last_snapshot_channel_ready = True
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            failure_key = _snapshot_read_failure_key(last_error)
            prefix = (
                "[android_client.power] status channel waiting"
                if waiting_for_device_resume
                else "[android_client.status] snapshot read failed"
            )
            if failure_key != last_snapshot_failure_key:
                smart_log(f"{prefix}: {failure_key}", level="warning", domain="android", source="android_client")
                if stage_tracker is not None:
                    stage_tracker.status_waiting(failure_key)
                last_snapshot_failure_key = failure_key
            if waiting_for_device_resume:
                last_snapshot_channel_ready = False
                time.sleep(poll_interval_sec)
                continue
            time.sleep(poll_interval_sec)
            continue

        new_log_lines, seen_log_count = _iter_unseen_snapshot_logs(
            snapshot,
            seen_log_count=seen_log_count,
        )
        for line in new_log_lines:
            smart_log(f"[android_client.log] {line}", domain="android", source="android_client")

        active_request = snapshot.get("activeRequest", {})
        active_trigger = str(active_request.get("trigger", "") or "") if isinstance(active_request, dict) else ""
        phase = str(snapshot.get("phase", "") or "")
        current_stage = str(snapshot.get("currentStage", "") or "")
        signature = _snapshot_signature(snapshot)
        snapshot_changed = signature != (baseline_signature or "")
        active_request_id = _snapshot_request_id(snapshot)
        matches_request = _snapshot_matches_request(snapshot, request_id=request_id)
        if matches_request:
            started = True
            no_response_deadline = time.monotonic() + no_response_timeout_sec
        if snapshot_changed and matches_request:
            fresh_run_observed = True
        if matches_request and stage_tracker is not None:
            stage_tracker.observe_snapshot(snapshot)

        status_line = (
            "[android_client.status] "
            f"phase={phase or '<empty>'} "
            f"started={started} "
            f"fresh_run={fresh_run_observed} "
            f"snapshot_changed={snapshot_changed} "
            f"request_id={active_request_id or '<empty>'} "
            f"matches_request={matches_request} "
            f"log_count={seen_log_count} "
            f"trigger={active_trigger or '<empty>'}"
        )
        if status_line != last_status_line:
            smart_log(status_line, domain="android", source="android_client")
            last_status_line = status_line

        next_waiting_for_device_resume = _next_dut_unavailable_wait_state(
            phase=phase,
            current_stage=current_stage,
            matches_request=matches_request,
            waiting_for_device_resume=waiting_for_device_resume,
        )
        if next_waiting_for_device_resume != waiting_for_device_resume:
            smart_log(
                "[android_client.power] "
                f"waiting_for_resume={next_waiting_for_device_resume} "
                f"phase={phase or '<empty>'} stage={current_stage or '<empty>'}",
                domain="android", source="android_client")
            if next_waiting_for_device_resume:
                last_snapshot_channel_ready = False
                host_quiet_tokens = _stage_tokens(
                    "SMARTTEST_ANDROID_HOST_QUIET_STAGE_TOKENS",
                    DEFAULT_HOST_QUIET_STAGE_TOKENS,
                )
                if any(token in str(current_stage or "").lower() for token in host_quiet_tokens):
                    host_quiet_until = time.monotonic() + float(
                        os.environ.get("SMARTTEST_ANDROID_HOST_QUIET_SEC", DEFAULT_HOST_QUIET_SEC),
                    )
                    host_quiet_logged = False
            else:
                host_quiet_until = 0.0
                host_quiet_logged = False
        waiting_for_device_resume = next_waiting_for_device_resume

        if phase == "Completed" and fresh_run_observed:
            if stage_tracker is not None:
                stage_tracker.finish("passed", actual=status_line)
            return snapshot

        if phase == "Failed" and fresh_run_observed:
            _collect_device_failure_debug(
                adb_executable=adb_executable,
                adb_serial=adb_serial,
            )
            report = snapshot.get("report", {})
            status_text = ""
            if isinstance(report, dict):
                status_text = str(report.get("statusText", "") or "")
            error_text = (
                "APK case failed on DUT.\n"
                f"case_id={case_id}\n"
                f"trigger={trigger}\n"
                f"status={status_text or phase}\n"
                f"recent_logs:\n{_recent_log_text(snapshot, 12)}"
            )
            if stage_tracker is not None:
                stage_tracker.finish("failed", error=error_text, actual=status_text or phase)
            raise RuntimeError(
                error_text
            )
        if phase in {"Completed", "Failed"} and matches_request and not fresh_run_observed:
            smart_log(
                "[android_client.status] ignoring stale terminal snapshot "
                f"phase={phase} request_id={request_id}",
                level="warning",
                domain="android", source="android_client")

        if phase == "Idle":
            recent_text = _recent_log_text(snapshot, 8)
            if request_id in recent_text and ("Run cancelled" in recent_text or "Received stop request" in recent_text):
                raise RuntimeError(
                    "APK case cancelled on DUT.\n"
                    f"case_id={case_id}\n"
                    f"request_id={request_id}\n"
                    f"trigger={trigger}"
                )

        time.sleep(poll_interval_sec)

    error_text = (
        "Timed out waiting for APK status feedback.\n"
        f"case_id={case_id}\n"
        f"trigger={trigger}\n"
        f"no_response_timeout_sec={no_response_timeout_sec}\n"
        f"last_snapshot={last_snapshot}\n"
        f"last_error={last_error}"
    )
    if stage_tracker is not None:
        stage_tracker.finish("failed", error=error_text)
    raise RuntimeError(error_text)


def trigger_apk_case(
    *,
    case_id: str,
    params: Mapping[str, str] | None = None,
    trigger: str,
    source: str = "pytest",
    adb_serial: str | None = None,
) -> subprocess.CompletedProcess[str]:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        smart_log("adb executable not found in PATH", level="error", domain="android", source="android_client")
        raise RuntimeError("adb is not available in PATH.")

    component = os.environ.get("SMARTTEST_ANDROID_COMPONENT", DEFAULT_COMPONENT)
    requested_serial = str(adb_serial or current_dut_serial())
    smart_log(f"case_id={case_id}", domain="android", source="android_client")
    smart_log(f"adb={adb_executable}", domain="android", source="android_client")
    smart_log(f"requested_serial={_serial_for_log(requested_serial)}", domain="android", source="android_client")
    smart_log(f"effective_serial={_serial_for_log(resolve_adb_serial_for_command(requested_serial))}", domain="android", source="android_client")
    smart_log(f"component={component}", domain="android", source="android_client")
    request_id = f"{case_id}-{uuid.uuid4().hex[:12]}"
    smart_log(f"request_id={request_id}", domain="android", source="android_client")
    stage_tracker = ApkStageTracker(case_id=case_id, request_id=request_id)
    require_privileged = case_id in PRIVILEGED_CASE_IDS
    smart_log(f"require_privileged={require_privileged}", domain="android", source="android_client")
    if require_privileged and apk_installed(adb_serial=requested_serial):
        stop_apk_run(
            adb_serial=requested_serial,
            reason=f"prepare privileged provisioning for {case_id}",
        )
        time.sleep(1.0)
        _launch_apk_main(adb_executable=adb_executable, adb_serial=requested_serial)
    installed = apk_installed(adb_serial=requested_serial)
    smart_log(f"installed_before_run={installed}", domain="android", source="android_client")
    if not installed:
        raise RuntimeError(
            "APK is not installed on DUT. Refresh the DUT list from the Test page before running."
        )
    _force_stop_apk(adb_executable=adb_executable, adb_serial=requested_serial)
    baseline_signature = None
    baseline_log_count = 0
    try:
        baseline_snapshot = read_apk_snapshot(adb_executable=adb_executable, adb_serial=requested_serial)
        baseline_signature = _snapshot_signature(baseline_snapshot)
        baseline_log_count = _snapshot_log_count(baseline_snapshot)
        baseline_phase = str(baseline_snapshot.get("phase", "") or "")
        baseline_request_id = _snapshot_request_id(baseline_snapshot)
        baseline_case_ids = _snapshot_case_ids(baseline_snapshot)
        smart_log(
            "[testing.runner.apk_client] baseline "
            f"phase={baseline_phase or '<empty>'} "
            f"request_id={baseline_request_id or '<empty>'} "
            f"case_ids={baseline_case_ids}",
            domain="android", source="android_client")
        if (
            baseline_phase in {"Running", "Stopping"}
            and case_id in baseline_case_ids
        ):
            smart_log(
                "[testing.runner.apk_client] stop stale active run before new request "
                f"case_id={case_id} baseline_request_id={baseline_request_id or '<empty>'}",
                level="warning",
                domain="android", source="android_client")
            stop_apk_run(
                adb_serial=requested_serial,
                reason=f"reset stale APK run before request {request_id}",
            )
            time.sleep(2.0)
            _force_stop_apk(adb_executable=adb_executable, adb_serial=requested_serial)
            baseline_signature = None
            baseline_log_count = 0
    except Exception as exc:  # noqa: BLE001
        smart_log(f"baseline snapshot unavailable: {exc}", level="warning", domain="android", source="android_client")
    result = _start_apk_run(
        adb_executable=adb_executable,
        component=component,
        case_id=case_id,
        request_id=request_id,
        trigger=trigger,
        source=source,
        params=params,
        adb_serial=requested_serial,
    )
    combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode != 0 or "Error:" in combined_output or "Exception occurred" in combined_output:
        error_text = (
            "Failed to trigger APK case.\n"
            f"component={component}\n"
            f"case_id={case_id}\n"
            f"trigger={trigger}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        stage_tracker.finish("failed", error=error_text)
        raise RuntimeError(error_text)
    if result.stdout:
        stage_tracker.evidence("Trigger stdout", result.stdout.strip(), evidence_type="stdout")
    if result.stderr:
        stage_tracker.evidence("Trigger stderr", result.stderr.strip(), evidence_type="stderr", level="warning")
    if case_id in _no_poll_case_ids():
        smart_log(
            "[testing.runner.apk_client] no-poll mode enabled; "
            f"skip host status polling for case_id={case_id} request_id={request_id}",
            domain="android", source="android_client")
        stage_tracker.finish("passed", actual="Triggered without host status polling.")
        return result
    wait_poll_interval_sec = DEFAULT_POLL_INTERVAL_SEC
    if case_id in _slow_poll_case_ids():
        wait_poll_interval_sec = float(
            os.environ.get("SMARTTEST_ANDROID_SLOW_POLL_INTERVAL_SEC", "5.0"),
        )
        smart_log(
            "[testing.runner.apk_client] slow-poll mode enabled; "
            f"poll_interval={wait_poll_interval_sec}s for case_id={case_id}",
            domain="android", source="android_client")
    try:
        snapshot = wait_for_apk_case_completion(
            adb_executable=adb_executable,
            case_id=case_id,
            request_id=request_id,
            trigger=trigger,
            adb_serial=requested_serial,
            poll_interval_sec=wait_poll_interval_sec,
            no_response_timeout_sec=float(
                os.environ.get("SMARTTEST_ANDROID_NO_RESPONSE_TIMEOUT_SEC", DEFAULT_NO_RESPONSE_TIMEOUT_SEC),
            ),
            baseline_signature=baseline_signature,
            baseline_log_count=baseline_log_count,
            stage_tracker=stage_tracker,
        )
    except Exception as exc:
        stage_tracker.finish("failed", error=str(exc))
        raise
    report = snapshot.get("report", {})
    if isinstance(report, dict):
        smart_log(
            "[testing.runner.apk_client] final report: "
            f"total={report.get('totalCount')} "
            f"passed={report.get('successCount')} "
            f"failed={report.get('failedCount')} "
            f"status={report.get('statusText')}",
            domain="android", source="android_client")
    return result


