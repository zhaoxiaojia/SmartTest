from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

from ui.example.bridge.RunBridge import RunBridge
from ui.example.helper.AppPaths import app_data_dir


def test_app_data_dir_uses_distinct_organization_and_application(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    QCoreApplication.setOrganizationName("Amlogic")
    QCoreApplication.setApplicationName("SmartTest")

    path = app_data_dir()

    assert path.parts[-2:] == ("Amlogic", "SmartTest")
    assert all(left != right for left, right in zip(path.parts, path.parts[1:]))


def test_run_bridge_paths_use_app_data_root_without_extra_smarttest(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    QCoreApplication.setOrganizationName("Amlogic")
    QCoreApplication.setApplicationName("SmartTest")

    bridge = RunBridge(tmp_path)

    assert bridge._default_state_path() == app_data_dir() / "test_page_state.json"
    assert bridge._default_reports_dir() == app_data_dir() / "reports"
    assert bridge._default_run_logs_dir() == app_data_dir() / "run_logs"
