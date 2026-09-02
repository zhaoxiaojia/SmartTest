import os
from pathlib import Path
import subprocess
import sys

import web.scripts.dev as dev


class FakeProcess:
    def __init__(self, pid, polls=None, returncode=None):
        self.pid = pid
        self._polls = list(polls or [])
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self):
        if self._polls:
            value = self._polls.pop(0)
            if value is not None:
                self.returncode = value
            return value
        return self.returncode

    def terminate(self): self.terminated = True
    def kill(self): self.killed = True
    def wait(self, timeout=None): return self.returncode


def test_direct_script_loads_core_logging_outside_repository_cwd(tmp_path):
    script = Path(dev.__file__).resolve()
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", f"import runpy; runpy.run_path({str(script)!r})"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_external_port_owner_is_terminated_automatically_before_start():
    backend = FakeProcess(10, polls=[None, 1], returncode=1)
    frontend = FakeProcess(20, polls=[None, None])
    processes = iter([backend, frontend])
    starts = []
    kills = []
    occupied = iter([True, True, False])
    result = dev.run(
        popen=lambda *args, **kwargs: starts.append((args, kwargs)) or next(processes),
        port_in_use=lambda: next(occupied),
        port_owner=lambda: [{"owner_pid": 4321, "target_pids": [4321, 4322]}],
        terminate_port_owner=lambda pid: kills.append(pid),
        wait_for_health=lambda *_args, **_kwargs: True,
        terminate_tree=lambda process: kills.append(process.pid),
        wait_for_port_release=lambda: True,
        sleep=lambda _seconds: None,
    )
    assert result == 1
    assert kills[:2] == [4321, 4322]
    assert len(starts) == 2


def test_occupied_port_without_resolvable_owner_is_not_killed():
    kills = []
    result = dev.run(
        popen=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not start")),
        port_in_use=lambda: True,
        port_owner=lambda: [],
        terminate_port_owner=lambda pid: kills.append(pid),
    )
    assert result == 2
    assert kills == []


def test_port_owner_resolver_returns_live_workers_for_stale_listener_parent():
    class Result:
        returncode = 0
        stdout = '[{"owner_pid":2184,"target_pids":[19992]}]'

    owners = dev.find_backend_port_owners(run=lambda *_args, **_kwargs: Result())

    assert owners == [{"owner_pid": 2184, "target_pids": [19992]}]


def test_port_cleanup_repeats_for_each_orphan_listener_until_port_is_free():
    occupied = iter([True, True, True, False])
    owners = iter([
        [{"owner_pid": 2184, "target_pids": [19992]}],
        [{"owner_pid": 35920, "target_pids": [39188]}],
        [{"owner_pid": 43808, "target_pids": [41920]}],
    ])
    killed = []

    assert dev.clear_existing_backend_processes(
        port_in_use=lambda: next(occupied),
        port_owners=lambda: next(owners),
        terminate_pid=lambda pid: killed.append(pid),
        sleep=lambda _seconds: None,
    ) is True
    assert killed == [19992, 39188, 41920]


def test_windows_tree_cleanup_targets_only_the_recorded_parent_pid():
    commands = []
    process = FakeProcess(4321, returncode=1)

    dev.terminate_owned_process(
        process,
        platform="win32",
        run=lambda command, **kwargs: commands.append((command, kwargs)),
    )

    assert commands == [
        (["taskkill", "/PID", "4321", "/T", "/F"],
         {"check": False, "capture_output": True, "text": True}),
    ]


def test_backend_failure_cleans_the_other_child_and_checks_port_release():
    backend = FakeProcess(10, polls=[None, 1], returncode=1)
    frontend = FakeProcess(20, polls=[None, None])
    processes = iter([backend, frontend])
    cleaned = []
    release_checks = []

    result = dev.run(
        popen=lambda *_args, **_kwargs: next(processes),
        port_in_use=lambda: False,
        wait_for_health=lambda *_args, **_kwargs: True,
        terminate_tree=lambda process: cleaned.append(process.pid),
        wait_for_port_release=lambda: release_checks.append(True) or True,
        sleep=lambda _seconds: None,
    )

    assert result == 1
    assert cleaned == [10, 20]
    assert release_checks == [True]


def test_keyboard_interrupt_returns_zero_and_cleans_both_children():
    processes = iter([FakeProcess(10), FakeProcess(20)])
    cleaned = []

    result = dev.run(
        popen=lambda *_args, **_kwargs: next(processes),
        port_in_use=lambda: False,
        wait_for_health=lambda *_args, **_kwargs: True,
        terminate_tree=lambda process: cleaned.append(process.pid),
        wait_for_port_release=lambda: True,
        sleep=lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    assert result == 0
    assert cleaned == [10, 20]


def test_health_readiness_reports_success_timeout_and_child_failure(monkeypatch):
    responses = iter([OSError("starting"), object()])

    class ReadyResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    def open_ready(*_args, **_kwargs):
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return ReadyResponse()

    clock = iter([0.0, 0.1, 0.2, 0.3])
    assert dev.wait_for_backend_health(
        [FakeProcess(1), FakeProcess(2)], timeout_seconds=1,
        urlopen=open_ready, monotonic=lambda: next(clock), sleep=lambda _seconds: None,
    ) is True
    assert dev.wait_for_backend_health(
        [FakeProcess(1), FakeProcess(2)], timeout_seconds=0,
        urlopen=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()),
        monotonic=lambda: 1.0, sleep=lambda _seconds: None,
    ) is False
    assert dev.wait_for_backend_health(
        [FakeProcess(1, returncode=3), FakeProcess(2)], timeout_seconds=1,
        urlopen=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
        monotonic=lambda: 0.0, sleep=lambda _seconds: None,
    ) is False
