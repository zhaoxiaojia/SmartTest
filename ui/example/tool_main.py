from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path

from example.imports import tool_resource_rc as _tool_resource_rc


TOOL_CONTEXT_NAMES = (
    "AppInfo", "FrontendStateBridge", "TranslateHelper", "AISettingsBridge",
    "AuthBridge", "ToolBridge", "RedmineBridge", "JiraAuditBridge",
    "ConfluenceAuditBridge", "DailyReportBridge", "ScheduleBridge",
)

PORTABLE_SMOKE_MODULES = (
    "openpyxl",
    "atlassian.confluence",
    "win32com.client",
    "win32cred",
    "ldap3",
    "qrcode",
    "support.report.excel",
    "tool.common.project_weekly_audit.report",
    "tool.common.project_weekly_audit.command",
    "tool.common.project_weekly_audit.scheduler",
)


def portable_smoke_imports() -> None:
    for module_name in PORTABLE_SMOKE_MODULES:
        importlib.import_module(module_name)
    if any(
        name == "matplotlib" or name.startswith("matplotlib.")
        for name in sys.modules
    ):
        raise RuntimeError("portable smoke unexpectedly loaded matplotlib")
    print("SmartTestTool portable smoke imports: PASS")


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        executable_root = Path(sys.executable).resolve().parent
        if (executable_root / "config" / "personnel.json").is_file():
            return executable_root
    packaged_root = Path(getattr(sys, "_MEIPASS", ""))
    if packaged_root and (packaged_root / "config" / "personnel.json").is_file():
        return packaged_root
    return Path(__file__).resolve().parents[2]


def restart_for_exit_code(
    exit_code: int,
    executable: str,
    arguments: list[str],
    start_detached,
) -> bool:
    if exit_code != 931:
        return False
    start_detached(executable, arguments)
    return True


def create_context_objects(engine) -> dict[str, object]:
    from example.AppInfo import AppInfo
    from example.bridge.AISettingsBridge import AISettingsBridge
    from example.bridge.AuthBridge import AuthBridge
    from example.bridge.ConfluenceAuditBridge import ConfluenceAuditBridge
    from example.bridge.DailyReportBridge import create_daily_report_bridge
    from example.bridge.FrontendStateBridge import FrontendStateBridge
    from example.bridge.JiraAuditBridge import JiraAuditBridge
    from example.bridge.RedmineBridge import RedmineBridge
    from example.bridge.ScheduleBridge import ScheduleBridge
    from example.bridge.ToolBridge import ToolBridge
    from example.helper.TranslateHelper import TranslateHelper
    from ui.frontend_state import FrontendStateStore
    from ui.jsonTool import app_data_dir

    root = runtime_root()
    auth = AuthBridge()
    store = FrontendStateStore(app_data_dir() / "frontend_state.json")
    translate = TranslateHelper(store)
    translate.init(engine)
    confluence = ConfluenceAuditBridge(auth)
    daily_report = create_daily_report_bridge(auth, app_data_dir(), root)
    return {
        "AppInfo": AppInfo(),
        "FrontendStateBridge": FrontendStateBridge(
            auth, store, legacy_path=app_data_dir() / "example.ini"
        ),
        "TranslateHelper": translate,
        "AISettingsBridge": AISettingsBridge(),
        "AuthBridge": auth,
        "ToolBridge": ToolBridge(root, auth),
        "RedmineBridge": RedmineBridge(auth),
        "JiraAuditBridge": JiraAuditBridge(auth),
        "ConfluenceAuditBridge": confluence,
        "DailyReportBridge": daily_report,
        "ScheduleBridge": ScheduleBridge({
            "confluence": confluence, "daily_report": daily_report,
        }),
    }


def main() -> None:
    if "--portable-smoke-imports" in sys.argv:
        portable_smoke_imports()
        return
    from qasync import QEventLoop
    from PySide6.QtCore import QProcess, QUrl
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    from FluentUI import FluentUI
    from FluentUI.FluLogger import LogSetup
    from example.context_registry import register_context_objects
    from example.helper import Async

    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    QQuickWindow.setGraphicsApi(
        QSGRendererInterface.GraphicsApi.Direct3D11
        if sys.platform.startswith("win")
        else QSGRendererInterface.GraphicsApi.OpenGL
    )
    QGuiApplication.setOrganizationName("Amlogic")
    QGuiApplication.setApplicationName("SmartTestTool")
    QGuiApplication.setApplicationDisplayName("SmartTest Tool")
    LogSetup("SmartTestTool")
    app = QGuiApplication(sys.argv)
    app.setWindowIcon(QIcon(":/example/res/image/taskbar_icon.png"))
    engine = QQmlApplicationEngine()
    objects = create_context_objects(engine)
    register_context_objects(engine, objects)
    redmine = objects["RedmineBridge"]
    app.aboutToQuit.connect(redmine.close)
    FluentUI.registerTypes(engine)

    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)
    event_loop.create_task(Async.boot())
    app.aboutToQuit.connect(lambda: event_loop.create_task(Async.delete()))
    engine.load(QUrl("qrc:/example/qml/tool/ToolApp.qml"))
    if not engine.rootObjects():
        raise RuntimeError("SmartTestTool QML shell failed to load")
    with event_loop:
        exit_code = event_loop.run_forever()
    restart_for_exit_code(
        exit_code,
        app.applicationFilePath(),
        app.arguments(),
        QProcess.startDetached,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
