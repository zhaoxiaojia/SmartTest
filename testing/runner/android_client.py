from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from typing import Mapping


DEFAULT_COMPONENT = "com.smarttest.mobile/com.smarttest.mobile.command.CommandActivity"
DEFAULT_ACTION_RUN = "com.smarttest.mobile.action.RUN"


def build_case_params(case_id: str, **params: object) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for param_id, value in params.items():
        resolved[f"{case_id}:{param_id}"] = str(value)
    return resolved


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
        raise RuntimeError("adb is not available in PATH.")

    component = os.environ.get("SMARTTEST_ANDROID_COMPONENT", DEFAULT_COMPONENT)
    serial = adb_serial or os.environ.get("SMARTTEST_ADB_SERIAL", "").strip()
    extras = [
        "--es case_id " + shlex.quote(case_id),
        "--es source " + shlex.quote(source),
        "--es trigger " + shlex.quote(trigger),
    ]
    if params:
        raw_params = ";".join(f"{key}={value}" for key, value in params.items())
        extras.append("--es params " + shlex.quote(raw_params))

    remote_command = " ".join(
        [
            "am start",
            "-n",
            shlex.quote(component),
            "-a",
            shlex.quote(DEFAULT_ACTION_RUN),
            *extras,
        ]
    )

    cmd = [adb_executable]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["shell", remote_command])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode != 0 or "Error:" in combined_output or "Exception occurred" in combined_output:
        raise RuntimeError(
            "Failed to trigger android_client case.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result
