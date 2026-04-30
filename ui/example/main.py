import os
import sys
import asyncio
from pathlib import Path
from qasync import QEventLoop

from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

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
from example.bridge.AIBridge import AIBridge
from example.bridge.HomeBridge import HomeBridge
from example.bridge.JiraBridge import JiraBridge
from example.bridge.ReportBridge import ReportBridge
from example.bridge.RunBridge import RunBridge
from example.bridge.TestPageBridge import TestPageBridge

_uri = "example"
_major = 1
_minor = 0


# noinspection PyTypeChecker
def main():
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    # Prefer D3D11 on Windows to avoid OpenGL driver/session issues that can
    # cause Qt Quick windows to fail to show or exit immediately.
    if sys.platform.startswith("win"):
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Direct3D11)
    else:
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    QGuiApplication.setOrganizationName("SmartTest")
    QGuiApplication.setOrganizationDomain("")
    QGuiApplication.setApplicationName("SmartTest")
    QGuiApplication.setApplicationDisplayName("SmartTest")
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
                print(w.toString(), file=sys.stderr)
            except Exception:
                print(str(w), file=sys.stderr)

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

    context = engine.rootContext()
    TranslateHelper().init(engine)
    context.setContextProperty("AppInfo", AppInfo())

    context.setContextProperty("InitializrHelper", InitializrHelper())
    context.setContextProperty("SettingsHelper", SettingsHelper())
    context.setContextProperty("TranslateHelper", TranslateHelper())
    auth_bridge = AuthBridge()
    context.setContextProperty("AuthBridge", auth_bridge)
    context.setContextProperty("HomeBridge", HomeBridge())
    context.setContextProperty("AIBridge", AIBridge())
    context.setContextProperty("TestPageBridge", TestPageBridge(Path(__file__).resolve().parents[2]))
    context.setContextProperty("RunBridge", RunBridge(Path(__file__).resolve().parents[2]))
    context.setContextProperty("ReportBridge", ReportBridge())
    context.setContextProperty("JiraBridge", JiraBridge(auth_bridge))
    FluentUI.registerTypes(engine)
    qml_file = QUrl("qrc:/example/qml/App.qml")
    engine.load(qml_file)
    if not engine.rootObjects():
        sys.exit(-1)
    with event_loop:
        result = event_loop.run_until_complete(app_close_event.wait())
        if result == 931:
            QProcess.startDetached(QGuiApplication.instance().applicationFilePath(), QGuiApplication.instance().arguments())
        sys.exit(result)


if __name__ == "__main__":
    main()
