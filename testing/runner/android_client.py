from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
import uuid
from typing import Mapping

from android_client import PACKAGE_NAME, PRIVILEGED_CASE_IDS, ensure_test_apk_installed
from testing.params.adb_devices import resolve_adb_serial_for_command


DEFAULT_COMPONENT = "com.smarttest.mobile/com.smarttest.mobile.command.CommandActivity"
DEFAULT_ACTION_RUN = "com.smarttest.mobile.action.RUN"
DEFAULT_ACTION_STOP = "com.smarttest.mobile.action.STOP"
DEFAULT_EXTRA_REQUEST_ID = "request_id"
DEFAULT_EXTRA_PARAMS_B64 = "params_b64"
DEFAULT_STATUS_URI = "content://com.smarttest.mobile.status/snapshot"
DEFAULT_STATUS_FILE = "files/runner_snapshot.json"
DEFAULT_PUBLIC_STATUS_FILE = "/sdcard/Android/data/com.smarttest.mobile/files/runner_snapshot.json"
DEFAULT_AUTO_SUSPEND_DEBUG_FILE = "/sdcard/Android/data/com.smarttest.mobile/files/auto_suspend_debug.log"
DEFAULT_POLL_INTERVAL_SEC = 1.0
DEFAULT_TIMEOUT_SEC = 3600.0
DEFAULT_MAX_CONSECUTIVE_STATUS_FAILURES = 5
AUTO_REBOOT_DUT_STAGE_TOKEN = "rebooting dut"
AUTO_SUSPEND_DUT_STAGE_TOKEN = "entering deep suspend"
AUTO_SUSPEND_HOST_QUIET_SEC = 25.0
DEFAULT_NO_POLL_CASE_IDS: set[str] = set()
DEFAULT_SLOW_POLL_CASE_IDS = {"auto_suspend", "auto_reboot"}


def build_case_params(case_id: str, **params: object) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for param_id, value in params.items():
        resolved[f"{case_id}:{param_id}"] = str(value)
    return resolved


def _adb_base_cmd(*, adb_executable: str, adb_serial: str | None = None) -> list[str]:
    cmd = [adb_executable]
    serial = resolve_adb_serial_for_command(adb_serial)
    if serial:
        cmd.extend(["-s", serial])
    return cmd


def _next_power_resume_wait_state(
    *,
    case_id: str,
    phase: str,
    current_stage: str,
    matches_request: bool,
    waiting_for_device_resume: bool,
) -> bool:
    stage_token = ""
    if case_id == "auto_reboot":
        stage_token = AUTO_REBOOT_DUT_STAGE_TOKEN
    elif case_id == "auto_suspend":
        stage_token = AUTO_SUSPEND_DUT_STAGE_TOKEN
    if not stage_token or not matches_request:
        return waiting_for_device_resume
    if phase in {"Completed", "Failed"}:
        return False
    if phase != "Running":
        return waiting_for_device_resume
    if stage_token in current_stage:
        return True
    if waiting_for_device_resume and stage_token not in current_stage:
        return False
    return waiting_for_device_resume


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
    )


def _read_snapshot_via_run_as(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    package_name: str = PACKAGE_NAME,
    status_file: str = DEFAULT_STATUS_FILE,
) -> dict[str, object]:
    result = _run_snapshot_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=["run-as", package_name, "cat", status_file],
    )
    stdout = str(result.stdout or "").strip()
    stderr = str(result.stderr or "").strip()
    if result.returncode != 0 or not stdout:
        raise RuntimeError(
            "run-as snapshot read failed.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}\n"
            f"returncode={result.returncode}"
    )
    return json.loads(_extract_json_payload(stdout))


def _read_snapshot_via_public_file(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    status_file: str = DEFAULT_PUBLIC_STATUS_FILE,
) -> dict[str, object]:
    result = _run_snapshot_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=["cat", status_file],
    )
    stdout = str(result.stdout or "").strip()
    stderr = str(result.stderr or "").strip()
    if result.returncode != 0 or not stdout:
        raise RuntimeError(
            "public snapshot read failed.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}\n"
            f"returncode={result.returncode}"
        )
    return json.loads(_extract_json_payload(stdout))


def _read_snapshot_via_content_provider(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    status_uri: str = DEFAULT_STATUS_URI,
) -> dict[str, object]:
    result = _run_snapshot_command(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=["content", "read", "--uri", status_uri],
    )
    stdout = str(result.stdout or "").strip()
    stderr = str(result.stderr or "").strip()
    if result.returncode != 0:
        raise RuntimeError(
            "content snapshot read failed.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}\n"
            f"returncode={result.returncode}"
        )
    return json.loads(_extract_json_payload(stdout))


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


def _collect_auto_suspend_failure_debug(
    *,
    adb_executable: str,
    adb_serial: str | None,
    request_id: str,
) -> None:
    print(
        "[android_client.power] collecting auto_suspend debug artifacts "
        f"request_id={request_id or '<empty>'}"
    )

    return_code, stdout, stderr = _adb_shell_capture_text(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        shell_args=["cat", DEFAULT_AUTO_SUSPEND_DEBUG_FILE],
    )
    if return_code == 0 and stdout:
        lines = stdout.splitlines()
        request_matches = [line for line in lines if request_id and request_id in line]
        selected = request_matches[-120:] if request_matches else lines[-120:]
        print("[android_client.power] auto_suspend_debug tail begin")
        for line in selected:
            print(f"[android_client.power.log] {line}")
        print("[android_client.power] auto_suspend_debug tail end")
    else:
        print(
            "[android_client.power] auto_suspend_debug unavailable "
            f"returncode={return_code} stdout={stdout or '<empty>'} stderr={stderr or '<empty>'}"
        )

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
    suspend_quiet_until = 0.0
    suspend_quiet_logged = False
    last_device_state = ""
    last_boot_completed: bool | None = None
    last_snapshot_channel_ready = False

    while time.monotonic() < deadline:
        if (
            waiting_for_device_resume
            and case_id == "auto_suspend"
            and time.monotonic() < suspend_quiet_until
        ):
            if not suspend_quiet_logged:
                remaining = max(0.0, suspend_quiet_until - time.monotonic())
                print(
                    "[android_client.power] "
                    f"host quiet mode for auto_suspend: hold adb polling for {remaining:.1f}s"
                )
                suspend_quiet_logged = True
            time.sleep(poll_interval_sec)
            continue

        if waiting_for_device_resume:
            device_state = _adb_get_state(adb_executable=adb_executable, adb_serial=adb_serial)
            if device_state != last_device_state:
                print(f"[android_client.power] device_state={device_state}")
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
                verbose=not waiting_for_device_resume,
            )
            last_snapshot = snapshot
            consecutive_failures = 0
            if waiting_for_device_resume and not last_snapshot_channel_ready:
                print("[android_client.power] snapshot channel ready after DUT resume")
                last_snapshot_channel_ready = True
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            consecutive_failures += 1
            if waiting_for_device_resume:
                last_snapshot_channel_ready = False
                time.sleep(poll_interval_sec)
                continue
            print(f"[android_client.status] snapshot read failed: {last_error}")
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

        next_waiting_for_device_resume = _next_power_resume_wait_state(
            case_id=case_id,
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
                if case_id == "auto_suspend":
                    suspend_quiet_until = time.monotonic() + AUTO_SUSPEND_HOST_QUIET_SEC
                    suspend_quiet_logged = False
            else:
                suspend_quiet_until = 0.0
                suspend_quiet_logged = False
        waiting_for_device_resume = next_waiting_for_device_resume

        if phase == "Completed" and fresh_run_observed:
            return snapshot

        if phase == "Failed" and fresh_run_observed:
            if case_id == "auto_suspend":
                _collect_auto_suspend_failure_debug(
                    adb_executable=adb_executable,
                    adb_serial=adb_serial,
                    request_id=request_id,
                )
            report = snapshot.get("report", {})
            status_text = ""
            if isinstance(report, dict):
                status_text = str(report.get("statusText", "") or "")
            raise RuntimeError(
                "android_client case failed on DUT.\n"
                f"case_id={case_id}\n"
                f"trigger={trigger}\n"
                f"status={status_text or phase}"
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

    raise RuntimeError(
        "Timed out while waiting for android_client case completion.\n"
        f"case_id={case_id}\n"
        f"trigger={trigger}\n"
        f"last_snapshot={last_snapshot}\n"
        f"last_error={last_error}"
    )


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
    serial = str(adb_serial or os.environ.get("SMARTTEST_ADB_SERIAL", "").strip())
    print(f"[testing.runner.android_client] case_id={case_id}")
    print(f"[testing.runner.android_client] adb={adb_executable}")
    print(f"[testing.runner.android_client] use_explicit_serial={bool(resolve_adb_serial_for_command(serial))}")
    print(f"[testing.runner.android_client] component={component}")
    print(f"[testing.runner.android_client] params={dict(params or {})}")
    request_id = f"{case_id}-{uuid.uuid4().hex[:12]}"
    print(f"[testing.runner.android_client] request_id={request_id}")
    require_privileged = case_id in PRIVILEGED_CASE_IDS
    print(f"[testing.runner.android_client] require_privileged={require_privileged}")
    if require_privileged and android_client_installed(adb_serial=serial):
        stop_android_client_run(
            adb_serial=serial,
            reason=f"prepare privileged provisioning for {case_id}",
        )
        time.sleep(1.0)
        _launch_android_client_main(adb_executable=adb_executable, adb_serial=serial)
    ensure_test_apk_installed(adb_serial=serial, require_privileged=require_privileged)
    installed = android_client_installed(adb_serial=serial)
    print(f"[testing.runner.android_client] installed_after_ensure={installed}")
    if not installed:
        raise RuntimeError("android_client is still not installed after install attempt.")
    _force_stop_android_client(adb_executable=adb_executable, adb_serial=serial)
    baseline_signature = None
    baseline_log_count = 0
    try:
        baseline_snapshot = read_android_client_snapshot(adb_executable=adb_executable, adb_serial=serial)
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
                adb_serial=serial,
                reason=f"reset stale android_client run before request {request_id}",
            )
            time.sleep(2.0)
            _force_stop_android_client(adb_executable=adb_executable, adb_serial=serial)
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
        adb_serial=serial,
    )
    combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode != 0 or "Error:" in combined_output or "Exception occurred" in combined_output:
        raise RuntimeError(
            "Failed to trigger android_client case.\n"
            f"component={component}\n"
            f"case_id={case_id}\n"
            f"trigger={trigger}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    if case_id in _no_poll_case_ids():
        print(
            "[testing.runner.android_client] no-poll mode enabled; "
            f"skip host status polling for case_id={case_id} request_id={request_id}"
        )
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
    snapshot = wait_for_android_client_case_completion(
        adb_executable=adb_executable,
        case_id=case_id,
        request_id=request_id,
        trigger=trigger,
        adb_serial=serial,
        poll_interval_sec=wait_poll_interval_sec,
        timeout_sec=float(os.environ.get("SMARTTEST_ANDROID_CASE_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC)),
        baseline_signature=baseline_signature,
        baseline_log_count=baseline_log_count,
        component=component,
        source=source,
        params=params,
    )
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
