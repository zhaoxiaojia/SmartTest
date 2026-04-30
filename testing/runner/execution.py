from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from testing.cases.catalog import is_packaged_runtime


def _subprocess_creationflags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class TestRunSession:
    process: Any
    event_file: Path
    tempdir: tempfile.TemporaryDirectory[str]
    adb_serial: str | None = None

    def cleanup(self) -> None:
        self.tempdir.cleanup()

    def stop(self, reason: str = "UI stop button") -> None:
        if self.process.poll() is not None:
            return
        if self.adb_serial:
            try:
                import time
                from testing.runner.android_client import _force_stop_android_client, stop_android_client_run
                import shutil

                stop_android_client_run(adb_serial=self.adb_serial, reason=reason)
                time.sleep(1.0)
                adb_executable = shutil.which("adb")
                if adb_executable:
                    _force_stop_android_client(adb_executable=adb_executable, adb_serial=self.adb_serial)
            except Exception:
                pass
        self.process.terminate()
        try:
            self.process.wait(timeout=5.0)
        except (subprocess.TimeoutExpired, TimeoutError):
            self.process.kill()


def start_pytest_run(
    *,
    root_dir: Path,
    nodeids: list[str],
    adb_serial: str | None = None,
    case_configs: dict[str, dict[str, object]] | None = None,
) -> TestRunSession:
    if is_packaged_runtime():
        from testing.runner.packaged import start_packaged_run

        return start_packaged_run(nodeids=nodeids, adb_serial=adb_serial, case_configs=case_configs)

    root_dir = root_dir.resolve()
    tempdir = tempfile.TemporaryDirectory(prefix="smarttest_pytest_run_")
    event_file = Path(tempdir.name) / "events.jsonl"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root_dir) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONUNBUFFERED"] = "1"
    env["SMARTTEST_STEP_EVENTS_OUT"] = str(event_file)
    env["SMARTTEST_CASE_CONFIGS_JSON"] = json.dumps(case_configs or {}, ensure_ascii=False)
    if adb_serial:
        env["SMARTTEST_ADB_SERIAL"] = str(adb_serial)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-s",
        "-q",
        "--disable-warnings",
        *nodeids,
    ]
    process = subprocess.Popen(
        cmd,
        cwd=str(root_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=_subprocess_creationflags(),
    )
    return TestRunSession(
        process=process,
        event_file=event_file,
        tempdir=tempdir,
        adb_serial=adb_serial,
    )
