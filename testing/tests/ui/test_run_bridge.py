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
