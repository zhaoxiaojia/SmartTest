import os
import sys
import asyncio
from pathlib import Path
from qasync import QEventLoop

from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtWebEngineQuick import QtWebEngineQuick

from FluentUI import FluentUI
from FluentUI.FluLogger import LogSetup, Logger
from example.AppInfo import AppInfo
from example.component.CircularReveal import CircularReveal
from example.component.FileWatcher import FileWatcher
from example.component.OpenGLItem import OpenGLItem
from example.helper.InitializrHelper import InitializrHelper
from example.helper.SettingsHelper import SettingsHelper
from example.helper.TranslateHelper import TranslateHelper
from example.component.Callback import Callback
from example.imports import resource_rc as rc
from example.helper import Async
from example.bridge.AuthBridge import AuthBridge
from example.bridge.HomeBridge import HomeBridge
from example.bridge.JiraBridge import JiraBridge
from example.bridge.ReportBridge import ReportBridge
from example.bridge.RunBridge import RunBridge
from example.bridge.TestPageBridge import TestPageBridge
from example.bridge.ToolBridge import ToolBridge
from example.bridge.RedmineBridge import RedmineBridge
from example.bridge.DebugBridge import DebugBridge
from example.bridge.BootVideoBridge import BootVideoBridge
from example.context_registry import register_context_objects
from support.logging import smart_log

_uri = "example"
_major = 1
_minor = 0


def _runtime_root() -> Path:
    packaged_root = getattr(sys, "_MEIPASS", None)
    if packaged_root:
        return Path(packaged_root)
    return Path(__file__).resolve().parents[2]


def _exit_code_from_event_result(result) -> int:
    if isinstance(result, bool) or result is None:
        return 0
    if isinstance(result, int):
        return result
    return 0


# noinspection PyTypeChecker
def main():
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    # Prefer D3D11 on Windows to avoid OpenGL driver/session issues that can
    # cause Qt Quick windows to fail to show or exit immediately.
    if sys.platform.startswith("win"):
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Direct3D11)
    else:
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    QGuiApplication.setOrganizationName("Amlogic")
    QGuiApplication.setOrganizationDomain("")
    QGuiApplication.setApplicationName("SmartTest")
    QGuiApplication.setApplicationDisplayName("SmartTest")
    QtWebEngineQuick.initialize()
    LogSetup("SmartTest")
    Logger().debug(f"Load the resource '{rc.__name__}'")
    app = QGuiApplication(sys.argv)
    QGuiApplication.setWindowIcon(QIcon(":/example/res/image/taskbar_icon.png"))

    qmlRegisterType(Callback, _uri, _major, _minor, "Callback")
    qmlRegisterType(CircularReveal, _uri, _major, _minor, "CircularReveal")
    qmlRegisterType(FileWatcher, _uri, _major, _minor, "FileWatcher")
    qmlRegisterType(OpenGLItem, _uri, _major, _minor, "OpenGLItem")

    engine = QQmlApplicationEngine()
    # Surface QML load/import errors in the console (helps when Qt doesn't print them).
    def _on_qml_warnings(warnings):
        for w in warnings:
            try:
                smart_log(w.toString(), level="warning", domain="ui", source="qml")
            except Exception:
                smart_log(str(w), level="warning", domain="ui", source="qml")

    try:
        engine.warnings.connect(_on_qml_warnings)
    except Exception:
        pass

    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)
    app_close_event = asyncio.Event()
    event_loop.create_task(Async.boot())

    app.aboutToQuit.connect(engine.deleteLater)
    app.aboutToQuit.connect(app_close_event.set)
    app.aboutToQuit.connect(lambda: event_loop.create_task(Async.delete()))

    runtime_root = _runtime_root()
    smart_log(
        "SmartTest UI runtime initialized (runtime_root=%s, entrypoint=%s)",
        str(runtime_root),
        str(Path(sys.argv[0]).resolve()),
        domain="ui",
        source="startup",
        extra={"runtime_root": str(runtime_root), "entrypoint": str(Path(sys.argv[0]).resolve())},
    )
    auth_bridge = AuthBridge()
    redmine_bridge = RedmineBridge(auth_bridge)
    translate_helper = TranslateHelper()
    translate_helper.init(engine)
    register_context_objects(
        engine,
        {
            "AppInfo": AppInfo(),
            "InitializrHelper": InitializrHelper(),
            "SettingsHelper": SettingsHelper(),
            "TranslateHelper": translate_helper,
            "AuthBridge": auth_bridge,
            "ToolBridge": ToolBridge(runtime_root, auth_bridge),
            "RedmineBridge": redmine_bridge,
            "HomeBridge": HomeBridge(),
            "TestPageBridge": TestPageBridge(runtime_root),
            "RunBridge": RunBridge(runtime_root),
            "ReportBridge": ReportBridge(),
            "JiraBridge": JiraBridge(auth_bridge),
            "DebugBridge": DebugBridge(runtime_root),
            "BootVideoBridge": BootVideoBridge(runtime_root),
        },
    )
    app.aboutToQuit.connect(redmine_bridge.close)
    FluentUI.registerTypes(engine)
    qml_file = QUrl("qrc:/example/qml/App.qml")
    engine.load(qml_file)
    if not engine.rootObjects():
        sys.exit(-1)
    with event_loop:
        result = event_loop.run_until_complete(app_close_event.wait())
        exit_code = _exit_code_from_event_result(result)
        if exit_code == 931:
            QProcess.startDetached(QGuiApplication.instance().applicationFilePath(), QGuiApplication.instance().arguments())
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
