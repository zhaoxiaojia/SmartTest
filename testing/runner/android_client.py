from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from typing import Mapping

from android_client import PACKAGE_NAME, PRIVILEGED_CASE_IDS, ensure_test_apk_installed
from testing.runtime.config import current_dut_serial
from testing.runtime.events import current_case_nodeid, current_step, emit_event
from testing.tool.adb import build_adb_command, effective_adb_serial


DEFAULT_COMPONENT = "com.smarttest.mobile/com.smarttest.mobile.command.CommandActivity"
DEFAULT_ACTION_RUN = "com.smarttest.mobile.action.RUN"
DEFAULT_ACTION_STOP = "com.smarttest.mobile.action.STOP"
DEFAULT_EXTRA_REQUEST_ID = "request_id"
DEFAULT_EXTRA_PARAMS_B64 = "params_b64"
DEFAULT_STATUS_URI = "content://com.smarttest.mobile.status/snapshot"
DEFAULT_STATUS_FILE = "files/runner_snapshot.json"
DEFAULT_PUBLIC_STATUS_FILE = "/sdcard/Android/data/com.smarttest.mobile/files/runner_snapshot.json"
DEFAULT_POLL_INTERVAL_SEC = 1.0
DEFAULT_TIMEOUT_SEC = 3600.0
DEFAULT_MAX_CONSECUTIVE_STATUS_FAILURES = 5
DEFAULT_DUT_UNAVAILABLE_STAGE_TOKENS = {"rebooting dut", "entering deep suspend"}
DEFAULT_HOST_QUIET_STAGE_TOKENS = {"entering deep suspend"}
DEFAULT_HOST_QUIET_SEC = 25.0
DEFAULT_NO_POLL_CASE_IDS: set[str] = set()
DEFAULT_SLOW_POLL_CASE_IDS: set[str] = set()
_DYNAMIC_STEP_ID_RE = re.compile(r"^(?P<prefix>.+?)\.(?P<marker>cycle|loop)\.(?P<index>\d+)\.(?P<tail>.+)$", re.IGNORECASE)
_STAGE_LOOP_RE = re.compile(r"\b(?P<marker>cycle|loop)\s+(?P<index>\d+)\s*/\s*(?P<total>\d+)\b", re.IGNORECASE)


def _event_time() -> float:
    return time.time()


def _emit_runtime_step_planned(
    *,
    step_id: str,
    title: str,
    kind: str,
    definition_id: str,
    params: Mapping[str, object] | None = None,
    expected: object = "",
    parent_id: str | None = None,
) -> bool:
    case_nodeid = current_case_nodeid()
    if not case_nodeid:
        return False
    parent = current_step()
    emit_event(
        "step_planned",
        step_id=step_id,
        case_nodeid=case_nodeid,
        parent_id=parent_id if parent_id is not None else (parent["id"] if parent else None),
        title=title,
        phase="call",
        kind=kind,
        definition_id=definition_id,
        meta={"definition_id": definition_id},
        params=dict(params or {}),
        expected=expected,
    )
    return True


def _emit_runtime_step_started(
    *,
    step_id: str,
    title: str,
    kind: str,
    definition_id: str,
    params: Mapping[str, object] | None = None,
    expected: object = "",
    parent_id: str | None = None,
) -> bool:
    case_nodeid = current_case_nodeid()
    if not case_nodeid:
        return False
    parent = current_step()
    emit_event(
        "step_started",
        step_id=step_id,
        case_nodeid=case_nodeid,
        parent_id=parent_id if parent_id is not None else (parent["id"] if parent else None),
        title=title,
        phase="call",
        kind=kind,
        definition_id=definition_id,
        meta={"definition_id": definition_id},
        params=dict(params or {}),
        expected=expected,
    )
    return True


def _emit_runtime_step_finished(
    *,
    step_id: str,
    status: str,
    error: str = "",
    actual: object = "",
) -> bool:
    case_nodeid = current_case_nodeid()
    if not case_nodeid:
        return False
    emit_event(
        "step_finished",
        step_id=step_id,
        case_nodeid=case_nodeid,
        status=status,
        error=error,
        actual=actual,
    )
    return True


def _emit_runtime_step_evidence(
    *,
    step_id: str,
    title: str,
    content: object,
    evidence_type: str = "log",
    level: str = "info",
) -> bool:
    case_nodeid = current_case_nodeid()
    if not case_nodeid:
        return False
    emit_event(
        "step_evidence",
        case_nodeid=case_nodeid,
        step_id=step_id,
        title=title,
        evidence_type=evidence_type,
        level=level,
        content=content,
        meta={},
    )
    return True


def _json_pair_list_to_dict(raw_items: object) -> dict[str, object]:
    if not isinstance(raw_items, list):
        return {}
    result: dict[str, object] = {}
    for item in raw_items:
        if isinstance(item, dict):
            key = str(item.get("key", "") or "")
            if key:
                result[key] = item.get("value", "")
    return result


class _RuntimeStep:
    def __init__(
        self,
        *,
        title: str,
        kind: str,
        definition_id: str,
        step_id: str | None = None,
        params: Mapping[str, object] | None = None,
        expected: object = "",
        parent_id: str | None = None,
    ) -> None:
        self.step_id = step_id or f"step:{uuid.uuid4().hex}"
        self._title = title
        self._kind = kind
        self._definition_id = definition_id
        self._params = dict(params or {})
        self._expected = expected
        self._parent_id = parent_id
        self._started = False
        self._finished = False
        self.enabled = _emit_runtime_step_planned(
            step_id=self.step_id,
            title=self._title,
            kind=self._kind,
            definition_id=self._definition_id,
            params=self._params,
            expected=self._expected,
            parent_id=self._parent_id,
        )

    def start(self) -> None:
        if not self.enabled or self._started:
            return
        self._started = True
        _emit_runtime_step_started(
            step_id=self.step_id,
            title=self._title,
            kind=self._kind,
            definition_id=self._definition_id,
            params=self._params,
            expected=self._expected,
            parent_id=self._parent_id,
        )

    def evidence(self, title: str, content: object, *, evidence_type: str = "log", level: str = "info") -> None:
        if not self.enabled:
            return
        _emit_runtime_step_evidence(
            step_id=self.step_id,
            title=title,
            content=content,
            evidence_type=evidence_type,
            level=level,
        )

    def finish(self, status: str, *, error: str = "", actual: object = "") -> None:
        if not self.enabled or self._finished:
            return
        if not self._started:
            self.start()
        self._finished = True
        _emit_runtime_step_finished(
            step_id=self.step_id,
            status=status,
            error=error,
            actual=actual,
        )

    @property
    def started(self) -> bool:
        return self._started


class _AndroidClientStageTracker:
    def __init__(
        self,
        *,
        case_id: str,
        request_id: str,
        params: Mapping[str, str] | None,
    ) -> None:
        self._case_id = case_id
        self._request_id = request_id
        self._parent = _RuntimeStep(
            title=f"Run android_client case: {case_id}",
            kind="action",
            definition_id="android_client.run_case",
            params={"case_id": case_id, "request_id": request_id, **dict(params or {})},
            expected="android_client reports Completed with zero failed cases.",
        )
        self._parent.start()
        self._current_stage: _RuntimeStep | None = None
        self._current_stage_key = ""
        self._planned_steps: dict[str, _RuntimeStep] = {}
        self._dynamic_steps: dict[str, _RuntimeStep] = {}
        self._terminal = False

    def evidence(self, title: str, content: object, *, evidence_type: str = "log", level: str = "info") -> None:
        self._parent.evidence(title, content, evidence_type=evidence_type, level=level)

    def observe_snapshot(self, snapshot: Mapping[str, object]) -> None:
        if not self._parent.enabled:
            return
        self._sync_planned_steps(snapshot)
        self._sync_step_states(snapshot)
        if self._planned_steps:
            return
        stage = str(snapshot.get("currentStage", "") or "").strip()
        phase = str(snapshot.get("phase", "") or "").strip()
        if not stage:
            stage = phase or "waiting for android_client status"
        stage_key = f"{phase}:{stage}"
        if stage_key == self._current_stage_key:
            return
        if self._current_stage is not None:
            self._current_stage.finish("passed")
        self._current_stage_key = stage_key
        self._current_stage = _RuntimeStep(
            title=stage,
            kind="external",
            definition_id="android_client.stage",
            params={"phase": phase, "case_id": self._case_id, "request_id": self._request_id},
            expected="android_client advances to the next stage or terminal status.",
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
            parameters = _json_pair_list_to_dict(item.get("parameters", []))
            step = _RuntimeStep(
                step_id=f"{self._request_id}:{raw_id}",
                title=str(item.get("title", "") or raw_id),
                kind=str(item.get("kind", "") or "action"),
                definition_id=str(item.get("definitionId", "") or raw_id),
                params=parameters,
                expected=str(item.get("expected", "") or ""),
                parent_id=self._parent.step_id,
            )
            self._planned_steps[raw_id] = step

    def _sync_step_states(self, snapshot: Mapping[str, object]) -> None:
        states = snapshot.get("stepStates", [])
        if not isinstance(states, list):
            return
        for item in states:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id", "") or "").strip()
            step = self._planned_steps.get(raw_id)
            if step is None:
                step = self._dynamic_step(raw_id=raw_id, snapshot=snapshot)
                if step is None:
                    continue
            status = str(item.get("status", "") or "").strip()
            if status == "running":
                step.start()
            elif status in {"passed", "failed", "skipped", "stopped"}:
                step.finish(
                    status,
                    actual=item.get("actual", ""),
                    error=str(item.get("error", "") or ""),
                )

    def _dynamic_step(self, *, raw_id: str, snapshot: Mapping[str, object]) -> _RuntimeStep | None:
        if not raw_id:
            return None
        existing = self._dynamic_steps.get(raw_id)
        if existing is not None:
            return existing
        match = _DYNAMIC_STEP_ID_RE.match(raw_id)
        if match is None:
            return None
        compact_id = f"{match.group('prefix')}.{match.group('marker')}.{match.group('tail')}"
        step = _RuntimeStep(
            step_id=f"{self._request_id}:{raw_id}",
            title=self._dynamic_step_title(raw_id=raw_id, snapshot=snapshot),
            kind=self._dynamic_step_kind(match.group("tail")),
            definition_id=compact_id,
            params={"case_id": self._case_id, "request_id": self._request_id},
            expected="android_client reports this cycle step finished.",
            parent_id=self._parent.step_id,
        )
        self._dynamic_steps[raw_id] = step
        return step

    def _dynamic_step_title(self, *, raw_id: str, snapshot: Mapping[str, object]) -> str:
        match = _DYNAMIC_STEP_ID_RE.match(raw_id)
        if match is None:
            return raw_id
        marker = match.group("marker").capitalize()
        index = match.group("index")
        current_stage = str(snapshot.get("currentStage", "") or "")
        stage_match = _STAGE_LOOP_RE.search(current_stage)
        total = stage_match.group("total") if stage_match else str(snapshot.get("totalLoops", "") or "")
        tail = match.group("tail").replace("_", " ")
        if total:
            return f"{marker} {index}/{total}: {tail}"
        return f"{marker} {index}: {tail}"

    def _dynamic_step_kind(self, tail: str) -> str:
        normalized = str(tail or "").lower()
        if any(token in normalized for token in ("check", "verify", "capture", "ping", "bluetooth")):
            return "check"
        return "step"

    def status_waiting(self, reason: str) -> None:
        if self._current_stage is not None:
            self._current_stage.evidence("Status channel waiting", reason, evidence_type="status", level="warning")
        else:
            self._parent.evidence("Status channel waiting", reason, evidence_type="status", level="warning")

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


def _subprocess_creationflags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def build_case_params(case_id: str, **params: object) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for param_id, value in params.items():
        resolved[f"{case_id}:{param_id}"] = str(value)
    return resolved


def _adb_base_cmd(*, adb_executable: str, adb_serial: str | None = None) -> list[str]:
    return build_adb_command(adb_executable=adb_executable, selected_serial=adb_serial, args=[])


def _serial_for_log(serial: str | None) -> str:
    text = str(serial or "").strip()
    if not text:
        return "<default>"
    return text.encode("unicode_escape").decode("ascii")


def _env_token_set(name: str, default: set[str]) -> set[str]:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return set(default)
    return {token.strip().lower() for token in raw.split(",") if token.strip()}


def _stage_contains_token(stage: str, tokens: set[str]) -> bool:
    normalized_stage = str(stage or "").lower()
    return any(token and token in normalized_stage for token in tokens)


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
    if _stage_contains_token(
        current_stage,
        _env_token_set("SMARTTEST_ANDROID_DUT_UNAVAILABLE_STAGE_TOKENS", DEFAULT_DUT_UNAVAILABLE_STAGE_TOKENS),
    ):
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


def _force_stop_android_client(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    package_name: str = PACKAGE_NAME,
) -> subprocess.CompletedProcess[str]:
    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(["shell", "am", "force-stop", package_name])
    print(f"[testing.runner.android_client] force-stop command: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    print(f"[testing.runner.android_client] force-stop stdout: {result.stdout.strip()}")
    print(f"[testing.runner.android_client] force-stop stderr: {result.stderr.strip()}")
    return result


def _launch_android_client_main(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    package_name: str = PACKAGE_NAME,
) -> subprocess.CompletedProcess[str]:
    component = f"{package_name}/com.smarttest.mobile.MainActivity"
    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(["shell", "am", "start", "-n", component])
    print(f"[testing.runner.android_client] launch-main command: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    print(f"[testing.runner.android_client] launch-main stdout: {result.stdout.strip()}")
    print(f"[testing.runner.android_client] launch-main stderr: {result.stderr.strip()}")
    return result


def _adb_get_state(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
) -> str:
    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.append("get-state")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
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
    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(["shell", "getprop", "sys.boot_completed"])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    if result.returncode != 0:
        return None
    return str(result.stdout or "").strip() == "1"


def _start_android_client_run(
    *,
    adb_executable: str,
    component: str,
    case_id: str,
    request_id: str,
    trigger: str,
    source: str,
    params: Mapping[str, str] | None = None,
    adb_serial: str | None = None,
    log_prefix: str = "[testing.runner.android_client]",
) -> subprocess.CompletedProcess[str]:
    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(
        [
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
            DEFAULT_EXTRA_REQUEST_ID,
            request_id,
        ],
    )
    if params:
        encoded_params = base64.urlsafe_b64encode(
            json.dumps(dict(params), ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        ).decode("ascii").rstrip("=")
        cmd.extend(["--es", DEFAULT_EXTRA_PARAMS_B64, encoded_params])
    print(f"{log_prefix} trigger command: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    print(f"{log_prefix} trigger stdout: {result.stdout.strip()}")
    print(f"{log_prefix} trigger stderr: {result.stderr.strip()}")
    return result


def stop_android_client_run(
    *,
    adb_serial: str | None = None,
    reason: str = "host stop",
) -> subprocess.CompletedProcess[str]:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        raise RuntimeError("adb is not available in PATH.")

    component = os.environ.get("SMARTTEST_ANDROID_COMPONENT", DEFAULT_COMPONENT)
    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(
        [
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
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    return result


def android_client_installed(*, adb_serial: str | None = None, package_name: str = PACKAGE_NAME) -> bool:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        raise RuntimeError("adb is not available in PATH.")

    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(["shell", "pm", "path", package_name])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    if result.returncode != 0:
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
    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(["shell", *shell_args])
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=_subprocess_creationflags(),
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


def _read_snapshot_via_run_as(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    package_name: str = PACKAGE_NAME,
    status_file: str = DEFAULT_STATUS_FILE,
) -> dict[str, object]:
    return _read_snapshot_json(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=["run-as", package_name, "cat", status_file],
        failure_label="run-as",
    )


def _read_snapshot_via_public_file(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    status_file: str = DEFAULT_PUBLIC_STATUS_FILE,
) -> dict[str, object]:
    return _read_snapshot_json(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=["cat", status_file],
        failure_label="public",
    )


def _read_snapshot_via_content_provider(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    status_uri: str = DEFAULT_STATUS_URI,
) -> dict[str, object]:
    return _read_snapshot_json(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=["content", "read", "--uri", status_uri],
        failure_label="content",
        require_stdout=False,
    )


def read_android_client_snapshot(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    status_uri: str = DEFAULT_STATUS_URI,
    verbose: bool = True,
) -> dict[str, object]:
    try:
        return _read_snapshot_via_public_file(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
        )
    except Exception as public_file_error:  # noqa: BLE001
        if verbose:
            print(f"[android_client.status] public-file fallback: {public_file_error}")
    try:
        return _read_snapshot_via_run_as(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
        )
    except Exception as run_as_error:  # noqa: BLE001
        if verbose:
            print(f"[android_client.status] run-as fallback: {run_as_error}")
    return _read_snapshot_via_content_provider(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        status_uri=status_uri,
    )


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
    if not raw:
        return set(DEFAULT_NO_POLL_CASE_IDS)
    return {token.strip() for token in raw.split(",") if token.strip()}


def _slow_poll_case_ids() -> set[str]:
    raw = str(os.environ.get("SMARTTEST_ANDROID_SLOW_POLL_CASES", "") or "").strip()
    if not raw:
        return set(DEFAULT_SLOW_POLL_CASE_IDS)
    return {token.strip() for token in raw.split(",") if token.strip()}


def _snapshot_matches_request(snapshot: dict[str, object], *, request_id: str) -> bool:
    if not request_id:
        return False
    if _snapshot_request_id(snapshot) == request_id:
        return True

    last_command_summary = str(snapshot.get("lastCommandSummary", "") or "")
    return request_id in last_command_summary


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
    for prop in ("sys.boot_completed", "sys.powerctl"):
        code, prop_stdout, prop_stderr = _adb_shell_capture_text(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            shell_args=["getprop", prop],
        )
        print(
            "[android_client.power] "
            f"getprop {prop} returncode={code} value={prop_stdout or '<empty>'} "
            f"stderr={prop_stderr or '<empty>'}"
        )

    code, uptime_stdout, uptime_stderr = _adb_shell_capture_text(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=["cat", "/proc/uptime"],
    )
    print(
        "[android_client.power] "
        f"/proc/uptime returncode={code} value={uptime_stdout or '<empty>'} "
        f"stderr={uptime_stderr or '<empty>'}"
    )


def wait_for_android_client_case_completion(
    *,
    adb_executable: str,
    case_id: str,
    request_id: str,
    trigger: str,
    adb_serial: str | None = None,
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    baseline_signature: str | None = None,
    baseline_log_count: int = 0,
    component: str = DEFAULT_COMPONENT,
    source: str = "pytest",
    params: Mapping[str, str] | None = None,
    stage_tracker: _AndroidClientStageTracker | None = None,
) -> dict[str, object]:
    started = False
    fresh_run_observed = False
    seen_log_count = max(0, int(baseline_log_count or 0))
    deadline = time.monotonic() + timeout_sec
    last_snapshot: dict[str, object] | None = None
    last_error: str = ""
    consecutive_failures = 0
    last_status_line = ""
    waiting_for_device_resume = False
    host_quiet_until = 0.0
    host_quiet_logged = False
    last_device_state = ""
    last_boot_completed: bool | None = None
    last_snapshot_channel_ready = False
    last_snapshot_failure_key = ""

    while time.monotonic() < deadline:
        if (
            waiting_for_device_resume
            and time.monotonic() < host_quiet_until
        ):
            if not host_quiet_logged:
                remaining = max(0.0, host_quiet_until - time.monotonic())
                print(
                    "[android_client.power] "
                    f"host quiet mode: hold adb polling for {remaining:.1f}s"
                )
                host_quiet_logged = True
            time.sleep(poll_interval_sec)
            continue

        if waiting_for_device_resume:
            device_state = _adb_get_state(adb_executable=adb_executable, adb_serial=adb_serial)
            if device_state != last_device_state:
                if device_state == "device":
                    print("[android_client.power] dut alive")
                else:
                    print(f"[android_client.power] dut lost state={device_state or '<empty>'}")
                last_device_state = device_state
            boot_completed = None
            if device_state == "device":
                boot_completed = _adb_is_boot_completed(adb_executable=adb_executable, adb_serial=adb_serial)
                if boot_completed != last_boot_completed:
                    print(f"[android_client.power] boot_completed={boot_completed}")
                    last_boot_completed = boot_completed
            else:
                last_boot_completed = None
            last_snapshot_channel_ready = False

        try:
            snapshot = read_android_client_snapshot(
                adb_executable=adb_executable,
                adb_serial=adb_serial,
                verbose=False,
            )
            last_snapshot = snapshot
            consecutive_failures = 0
            last_snapshot_failure_key = ""
            if waiting_for_device_resume and not last_snapshot_channel_ready:
                print("[android_client.power] snapshot channel ready after DUT resume")
                last_snapshot_channel_ready = True
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            consecutive_failures += 1
            failure_key = _snapshot_read_failure_key(last_error)
            if waiting_for_device_resume:
                if failure_key != last_snapshot_failure_key:
                    print(f"[android_client.power] status channel waiting: {failure_key}")
                    if stage_tracker is not None:
                        stage_tracker.status_waiting(failure_key)
                    last_snapshot_failure_key = failure_key
                last_snapshot_channel_ready = False
                time.sleep(poll_interval_sec)
                continue
            if failure_key != last_snapshot_failure_key:
                print(f"[android_client.status] snapshot read failed: {failure_key}")
                if stage_tracker is not None:
                    stage_tracker.status_waiting(failure_key)
                last_snapshot_failure_key = failure_key
            if started and consecutive_failures >= DEFAULT_MAX_CONSECUTIVE_STATUS_FAILURES:
                raise RuntimeError(
                    "Lost android_client status channel after DUT run started.\n"
                    f"case_id={case_id}\n"
                    f"trigger={trigger}\n"
                    f"last_snapshot={last_snapshot}\n"
                    f"last_error={last_error}"
                ) from exc
            time.sleep(poll_interval_sec)
            continue

        log_lines = snapshot.get("logLines", [])
        if isinstance(log_lines, list):
            if len(log_lines) < seen_log_count:
                seen_log_count = 0
            for line in log_lines[seen_log_count:]:
                print(f"[android_client.log] {line}")
            seen_log_count = len(log_lines)

        active_request = snapshot.get("activeRequest", {})
        if not isinstance(active_request, dict):
            active_request = {}
        active_case_ids = active_request.get("caseIds", [])
        if not isinstance(active_case_ids, list):
            active_case_ids = []
        active_trigger = str(active_request.get("trigger", "") or "")
        phase = str(snapshot.get("phase", "") or "")
        current_stage = str(snapshot.get("currentStage", "") or "")
        signature = _snapshot_signature(snapshot)
        snapshot_changed = signature != (baseline_signature or "")
        active_request_id = _snapshot_request_id(snapshot)
        matches_request = _snapshot_matches_request(snapshot, request_id=request_id)
        if matches_request:
            started = True
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
            print(status_line)
            last_status_line = status_line

        next_waiting_for_device_resume = _next_dut_unavailable_wait_state(
            phase=phase,
            current_stage=current_stage,
            matches_request=matches_request,
            waiting_for_device_resume=waiting_for_device_resume,
        )
        if next_waiting_for_device_resume != waiting_for_device_resume:
            print(
                "[android_client.power] "
                f"waiting_for_resume={next_waiting_for_device_resume} "
                f"phase={phase or '<empty>'} stage={current_stage or '<empty>'}"
            )
            if next_waiting_for_device_resume:
                last_snapshot_channel_ready = False
                if _stage_contains_token(
                    current_stage,
                    _env_token_set("SMARTTEST_ANDROID_HOST_QUIET_STAGE_TOKENS", DEFAULT_HOST_QUIET_STAGE_TOKENS),
                ):
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
            recent_logs = snapshot.get("logLines", [])
            recent_log_text = ""
            if isinstance(recent_logs, list):
                recent_log_text = "\n".join(str(item) for item in recent_logs[-12:])
            error_text = (
                "android_client case failed on DUT.\n"
                f"case_id={case_id}\n"
                f"trigger={trigger}\n"
                f"status={status_text or phase}\n"
                f"recent_logs:\n{recent_log_text}"
            )
            if stage_tracker is not None:
                stage_tracker.finish("failed", error=error_text, actual=status_text or phase)
            raise RuntimeError(
                error_text
            )
        if phase in {"Completed", "Failed"} and matches_request and not fresh_run_observed:
            print(
                "[android_client.status] ignoring stale terminal snapshot "
                f"phase={phase} request_id={request_id}"
            )

        if phase == "Idle":
            recent_logs = snapshot.get("logLines", [])
            if isinstance(recent_logs, list):
                recent_text = "\n".join(str(item) for item in recent_logs[-8:])
            else:
                recent_text = ""
            if request_id in recent_text and ("Run cancelled" in recent_text or "Received stop request" in recent_text):
                raise RuntimeError(
                    "android_client case cancelled on DUT.\n"
                    f"case_id={case_id}\n"
                    f"request_id={request_id}\n"
                    f"trigger={trigger}"
                )

        if not started:
            time.sleep(poll_interval_sec)
            continue

        time.sleep(poll_interval_sec)

    error_text = (
        "Timed out while waiting for android_client case completion.\n"
        f"case_id={case_id}\n"
        f"trigger={trigger}\n"
        f"last_snapshot={last_snapshot}\n"
        f"last_error={last_error}"
    )
    if stage_tracker is not None:
        stage_tracker.finish("failed", error=error_text)
    raise RuntimeError(error_text)


def trigger_android_client_case(
    *,
    case_id: str,
    params: Mapping[str, str] | None = None,
    trigger: str,
    source: str = "pytest",
    adb_serial: str | None = None,
) -> subprocess.CompletedProcess[str]:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        print("[testing.runner.android_client] adb executable not found in PATH")
        raise RuntimeError("adb is not available in PATH.")

    component = os.environ.get("SMARTTEST_ANDROID_COMPONENT", DEFAULT_COMPONENT)
    requested_serial = str(adb_serial or current_dut_serial())
    print(f"[testing.runner.android_client] case_id={case_id}")
    print(f"[testing.runner.android_client] adb={adb_executable}")
    print(f"[testing.runner.android_client] requested_serial={_serial_for_log(requested_serial)}")
    print(f"[testing.runner.android_client] effective_serial={_serial_for_log(effective_adb_serial(requested_serial))}")
    print(f"[testing.runner.android_client] component={component}")
    print(f"[testing.runner.android_client] params={dict(params or {})}")
    request_id = f"{case_id}-{uuid.uuid4().hex[:12]}"
    print(f"[testing.runner.android_client] request_id={request_id}")
    stage_tracker = _AndroidClientStageTracker(case_id=case_id, request_id=request_id, params=params)
    if params:
        stage_tracker.evidence("Request parameters", dict(params), evidence_type="params")
    require_privileged = case_id in PRIVILEGED_CASE_IDS
    print(f"[testing.runner.android_client] require_privileged={require_privileged}")
    if require_privileged and android_client_installed(adb_serial=requested_serial):
        stop_android_client_run(
            adb_serial=requested_serial,
            reason=f"prepare privileged provisioning for {case_id}",
        )
        time.sleep(1.0)
        _launch_android_client_main(adb_executable=adb_executable, adb_serial=requested_serial)
    ensure_test_apk_installed(adb_serial=requested_serial, require_privileged=require_privileged)
    installed = android_client_installed(adb_serial=requested_serial)
    print(f"[testing.runner.android_client] installed_after_ensure={installed}")
    if not installed:
        raise RuntimeError("android_client is still not installed after install attempt.")
    _force_stop_android_client(adb_executable=adb_executable, adb_serial=requested_serial)
    baseline_signature = None
    baseline_log_count = 0
    try:
        baseline_snapshot = read_android_client_snapshot(adb_executable=adb_executable, adb_serial=requested_serial)
        baseline_signature = _snapshot_signature(baseline_snapshot)
        baseline_logs = baseline_snapshot.get("logLines", [])
        if isinstance(baseline_logs, list):
            baseline_log_count = len(baseline_logs)
        else:
            baseline_log_count = int(baseline_snapshot.get("logCount", 0) or 0)
        baseline_phase = str(baseline_snapshot.get("phase", "") or "")
        baseline_request_id = _snapshot_request_id(baseline_snapshot)
        baseline_active_request = baseline_snapshot.get("activeRequest", {})
        if not isinstance(baseline_active_request, dict):
            baseline_active_request = {}
        baseline_case_ids = baseline_active_request.get("caseIds", [])
        if not isinstance(baseline_case_ids, list):
            baseline_case_ids = []
        print(
            "[testing.runner.android_client] baseline "
            f"phase={baseline_phase or '<empty>'} "
            f"request_id={baseline_request_id or '<empty>'} "
            f"case_ids={[str(item) for item in baseline_case_ids]}"
        )
        if (
            baseline_phase in {"Running", "Stopping"}
            and case_id in [str(item) for item in baseline_case_ids]
        ):
            print(
                "[testing.runner.android_client] stop stale active run before new request "
                f"case_id={case_id} baseline_request_id={baseline_request_id or '<empty>'}"
            )
            stop_android_client_run(
                adb_serial=requested_serial,
                reason=f"reset stale android_client run before request {request_id}",
            )
            time.sleep(2.0)
            _force_stop_android_client(adb_executable=adb_executable, adb_serial=requested_serial)
            baseline_signature = None
            baseline_log_count = 0
    except Exception as exc:  # noqa: BLE001
        print(f"[testing.runner.android_client] baseline snapshot unavailable: {exc}")
    result = _start_android_client_run(
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
            "Failed to trigger android_client case.\n"
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
        print(
            "[testing.runner.android_client] no-poll mode enabled; "
            f"skip host status polling for case_id={case_id} request_id={request_id}"
        )
        stage_tracker.finish("passed", actual="Triggered without host status polling.")
        return result
    wait_poll_interval_sec = DEFAULT_POLL_INTERVAL_SEC
    if case_id in _slow_poll_case_ids():
        wait_poll_interval_sec = float(
            os.environ.get("SMARTTEST_ANDROID_SLOW_POLL_INTERVAL_SEC", "5.0"),
        )
        print(
            "[testing.runner.android_client] slow-poll mode enabled; "
            f"poll_interval={wait_poll_interval_sec}s for case_id={case_id}"
        )
    try:
        snapshot = wait_for_android_client_case_completion(
            adb_executable=adb_executable,
            case_id=case_id,
            request_id=request_id,
            trigger=trigger,
            adb_serial=requested_serial,
            poll_interval_sec=wait_poll_interval_sec,
            timeout_sec=float(os.environ.get("SMARTTEST_ANDROID_CASE_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC)),
            baseline_signature=baseline_signature,
            baseline_log_count=baseline_log_count,
            component=component,
            source=source,
            params=params,
            stage_tracker=stage_tracker,
        )
    except Exception as exc:
        stage_tracker.finish("failed", error=str(exc))
        raise
    report = snapshot.get("report", {})
    if isinstance(report, dict):
        print(
            "[testing.runner.android_client] final report: "
            f"total={report.get('totalCount')} "
            f"passed={report.get('successCount')} "
            f"failed={report.get('failedCount')} "
            f"status={report.get('statusText')}"
        )
    return result
