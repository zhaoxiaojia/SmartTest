from __future__ import annotations

import contextlib
import json
import os
import queue
import tempfile
import threading
import time
import traceback
from pathlib import Path
from typing import Any, TextIO

from testing.cases.catalog import load_packaged_test_catalog
from testing.params.registry import default_registry
from testing.params.schema import ParamValueType
from testing.runner.android_client import trigger_android_client_case
from testing.runtime.events import emit_event


class _QueueStdout:
    def __init__(self):
        self._queue: queue.Queue[str | None] = queue.Queue()

    def write_line(self, line: str) -> None:
        self._queue.put(str(line).rstrip("\n") + "\n")

    def close(self) -> None:
        self._queue.put(None)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        item = self._queue.get()
        if item is None:
            raise StopIteration
        return item


class _LogWriter:
    def __init__(self, sink):
        self._sink = sink
        self._buffer = ""

    def write(self, text: str) -> int:
        value = str(text or "")
        self._buffer += value
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line:
                self._sink(line)
        return len(value)

    def flush(self) -> None:
        if self._buffer:
            self._sink(self._buffer)
            self._buffer = ""


class PackagedRunProcess:
    def __init__(
        self,
        *,
        event_file: Path,
        nodeids: list[str],
        adb_serial: str | None,
        case_configs: dict[str, dict[str, object]],
    ):
        self.stdout: TextIO | _QueueStdout | None = _QueueStdout()
        self._returncode: int | None = None
        self._done = threading.Event()
        self._stop_requested = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            kwargs={
                "event_file": event_file,
                "nodeids": nodeids,
                "adb_serial": adb_serial,
                "case_configs": case_configs,
            },
            daemon=True,
        )
        self._thread.start()

    def poll(self) -> int | None:
        return self._returncode

    def wait(self, timeout: float | None = None) -> int:
        if not self._done.wait(timeout):
            raise TimeoutError("Packaged test run did not finish before timeout.")
        return int(self._returncode or 0)

    def terminate(self) -> None:
        self._stop_requested.set()

    def kill(self) -> None:
        self._stop_requested.set()

    def _log(self, line: str) -> None:
        stdout = self.stdout
        if isinstance(stdout, _QueueStdout):
            stdout.write_line(line)

    def _run(
        self,
        *,
        event_file: Path,
        nodeids: list[str],
        adb_serial: str | None,
        case_configs: dict[str, dict[str, object]],
    ) -> None:
        previous_event_path = os.environ.get("SMARTTEST_STEP_EVENTS_OUT")
        previous_serial = os.environ.get("SMARTTEST_ADB_SERIAL")
        os.environ["SMARTTEST_STEP_EVENTS_OUT"] = str(event_file)
        if adb_serial:
            os.environ["SMARTTEST_ADB_SERIAL"] = str(adb_serial)
        try:
            catalog_by_nodeid = {str(row.get("nodeid", "")): row for row in load_packaged_test_catalog()}
            for nodeid in nodeids:
                if self._stop_requested.is_set():
                    self._returncode = 1
                    return
                row = catalog_by_nodeid.get(nodeid, {})
                android_case_id = str(row.get("android_case_id", "") or "").strip()
                if not android_case_id:
                    raise RuntimeError(f"Packaged runner cannot resolve android case id for {nodeid}")
                self._run_one(
                    nodeid=nodeid,
                    title=str(row.get("name", "") or nodeid),
                    file=str(row.get("file", "") or nodeid.split("::", 1)[0]),
                    android_case_id=android_case_id,
                    params=_android_case_params(
                        android_case_id=android_case_id,
                        values=dict(case_configs.get(nodeid) or {}),
                    ),
                    adb_serial=adb_serial,
                )
            self._returncode = 0
        except Exception as exc:  # noqa: BLE001
            self._log(f"[packaged-runner-error] {exc}")
            self._log("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip())
            self._returncode = 1
        finally:
            if previous_event_path is None:
                os.environ.pop("SMARTTEST_STEP_EVENTS_OUT", None)
            else:
                os.environ["SMARTTEST_STEP_EVENTS_OUT"] = previous_event_path
            if previous_serial is None:
                os.environ.pop("SMARTTEST_ADB_SERIAL", None)
            else:
                os.environ["SMARTTEST_ADB_SERIAL"] = previous_serial
            stdout = self.stdout
            if isinstance(stdout, _QueueStdout):
                stdout.close()
            self._done.set()

    def _run_one(
        self,
        *,
        nodeid: str,
        title: str,
        file: str,
        android_case_id: str,
        params: dict[str, str],
        adb_serial: str | None,
    ) -> None:
        started = time.monotonic()
        emit_event("case_started", case_nodeid=nodeid, title=title, file=file)
        self._log(f"[packaged-runner] case_id={android_case_id} nodeid={nodeid}")
        if params:
            self._log(f"[packaged-runner] params={json.dumps(params, ensure_ascii=False, sort_keys=True)}")
        stdout_writer = _LogWriter(self._log)
        stderr_writer = _LogWriter(self._log)
        try:
            with contextlib.redirect_stdout(stdout_writer), contextlib.redirect_stderr(stderr_writer):
                result = trigger_android_client_case(
                    case_id=android_case_id,
                    params=params,
                    trigger=nodeid,
                    source="packaged",
                    adb_serial=adb_serial,
                )
            for line in str(result.stdout or "").splitlines():
                self._log(line)
            for line in str(result.stderr or "").splitlines():
                self._log(line)
            status = "passed"
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            self._log(str(exc))
            raise
        finally:
            stdout_writer.flush()
            stderr_writer.flush()
            emit_event(
                "case_finished",
                case_nodeid=nodeid,
                status=status,
                duration_ms=int((time.monotonic() - started) * 1000),
            )


def start_packaged_run(
    *,
    nodeids: list[str],
    adb_serial: str | None = None,
    case_configs: dict[str, dict[str, object]] | None = None,
):
    from testing.runner.execution import TestRunSession

    tempdir = tempfile.TemporaryDirectory(prefix="smarttest_packaged_run_")
    event_file = Path(tempdir.name) / "events.jsonl"
    process = PackagedRunProcess(
        event_file=event_file,
        nodeids=nodeids,
        adb_serial=adb_serial,
        case_configs=case_configs or {},
    )
    return TestRunSession(process=process, event_file=event_file, tempdir=tempdir, adb_serial=adb_serial)


def _android_case_params(*, android_case_id: str, values: dict[str, object]) -> dict[str, str]:
    registry = default_registry()
    params: dict[str, str] = {}
    prefix = f"{android_case_id}:"
    for raw_key, raw_value in values.items():
        key = str(raw_key)
        if not key.startswith(prefix):
            continue
        field = registry.get_param(key)
        params[key] = _format_param_value(raw_value, integer=field is not None and field.type == ParamValueType.INT)
    return params


def _format_param_value(value: object, *, integer: bool) -> str:
    if integer:
        return str(int(float(str(value).strip())))
    return str(value)
