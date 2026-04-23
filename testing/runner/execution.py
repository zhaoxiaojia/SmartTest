from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestRunSession:
    process: subprocess.Popen[str]
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
        except subprocess.TimeoutExpired:
            self.process.kill()


def start_pytest_run(
    *,
    root_dir: Path,
    nodeids: list[str],
    adb_serial: str | None = None,
    case_configs: dict[str, dict[str, object]] | None = None,
) -> TestRunSession:
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
    )
    return TestRunSession(
        process=process,
        event_file=event_file,
        tempdir=tempdir,
        adb_serial=adb_serial,
    )
