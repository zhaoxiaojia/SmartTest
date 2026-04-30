from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QGuiApplication

from ui.example.bridge.RunBridge import RunBridge


def test_run_bridge_toggle_updates_shared_running_state() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    observed: list[bool] = []
    bridge.runningChanged.connect(lambda: observed.append(bridge.isRunning))

    assert bridge.isRunning is False

    bridge._set_running(True)
    assert bridge.isRunning is True

    bridge._set_running(False)
    assert bridge.isRunning is False

    bridge._set_running(True)
    assert bridge.isRunning is True
    assert observed == [True, False, True]


def test_run_bridge_resolves_single_connected_device_when_saved_dut_is_stale(monkeypatch) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    monkeypatch.setattr("ui.example.bridge.RunBridge.list_adb_devices", lambda: ["R58N123ABC"])

    assert bridge._resolve_adb_serial("aaaa") == "R58N123ABC"


def test_run_bridge_keeps_saved_device_when_it_exists(monkeypatch) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())
    monkeypatch.setattr("ui.example.bridge.RunBridge.list_adb_devices", lambda: ["ABC123", "XYZ789"])

    assert bridge._resolve_adb_serial("XYZ789") == "XYZ789"


def test_run_bridge_stop_uses_session_stop() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(Path.cwd())

    class _Session:
        def __init__(self) -> None:
            self.reasons: list[str] = []

        def stop(self, reason: str = "UI stop button") -> None:
            self.reasons.append(reason)

    session = _Session()
    bridge._session = session
    bridge._set_running(True)

    bridge.stopRun()

    assert session.reasons == ["UI stop button"]


def test_run_bridge_uses_writable_run_log_dir(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(tmp_path)

    assert bridge._stdout_log_path.name == "tmp_main_stdout.log"
    assert bridge._stderr_log_path.name == "tmp_main_stderr.log"
    assert bridge._stdout_log_path.parent.name == "run_logs"
    assert bridge._stdout_mirror_log_path == tmp_path.resolve() / "tmp_main_stdout.log"


def test_run_bridge_start_failure_writes_stderr_log(monkeypatch, tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = RunBridge(tmp_path)
    bridge._stdout_log_path = tmp_path / "logs" / "tmp_main_stdout.log"
    bridge._stderr_log_path = tmp_path / "logs" / "tmp_main_stderr.log"
    bridge._stdout_mirror_log_path = tmp_path / "tmp_main_stdout.log"
    bridge._stderr_mirror_log_path = tmp_path / "tmp_main_stderr.log"
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)

    def fail_selected_targets():
        raise RuntimeError("selection failed")

    monkeypatch.setattr(bridge, "_selected_run_targets", fail_selected_targets)

    bridge.startRun()

    stderr = bridge._stderr_log_path.read_text(encoding="utf-8")
    assert "selection failed" in stderr
    assert "RuntimeError" in stderr
    assert errors and "selection failed" in errors[-1]
