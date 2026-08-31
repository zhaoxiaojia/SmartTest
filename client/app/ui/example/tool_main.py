from __future__ import annotations

import asyncio
import importlib
import os
import sys
import uuid
from pathlib import Path

from core.logging import configure_platform
from example.imports import tool_resource_rc as _tool_resource_rc
from client.packaging.tool_runtime_dependencies import TOOL_SMOKE_MODULES
from client.packaging.tool_runtime_resources import missing_required


configure_platform("tool")


TOOL_CONTEXT_NAMES = (
    "AppInfo", "TranslateHelper", "AISettingsBridge",
    "AuthBridge", "ToolBridge", "RedmineBridge",
)

PORTABLE_SMOKE_MODULES = TOOL_SMOKE_MODULES


def portable_smoke_imports() -> None:
    for module_name in PORTABLE_SMOKE_MODULES:
        importlib.import_module(module_name)
    if any(
        name == "matplotlib" or name.startswith("matplotlib.")
        for name in sys.modules
    ):
        raise RuntimeError("portable smoke unexpectedly loaded matplotlib")
    print("SmartTestTool portable smoke imports: PASS")


def portable_credential_smoke(*, store=None, credential_ref: str | None = None) -> None:
    from core.credentials.windows import (
        CredentialNotFoundError,
        WindowsCredentialStore,
    )

    credential_ref = credential_ref or uuid.uuid4().hex
    store = store or WindowsCredentialStore(
        target_prefix=f"SmartTest/PortableSmoke/{os.getpid()}/{uuid.uuid4().hex}/",
    )
    failure: Exception | None = None
    try:
        store.write(
            credential_ref, "portable-smoke-user", "portable-smoke-secret",
        )
        actual = store.read(credential_ref)
        if actual != ("portable-smoke-user", "portable-smoke-secret"):
            raise RuntimeError("Credential Manager smoke read did not match its write")
    except Exception as exc:
        failure = exc
        raise
    finally:
        try:
            store.delete(credential_ref)
        except CredentialNotFoundError:
            if failure is None:
                raise
        except Exception:
            if failure is None:
                raise
    print("SmartTestTool portable credentials: PASS")


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        executable_root = Path(sys.executable).resolve().parent
        packaged_value = getattr(sys, "_MEIPASS", "")
        candidates = [executable_root]
        if packaged_value:
            packaged_root = Path(packaged_value).resolve()
            if packaged_root not in candidates:
                candidates.append(packaged_root)
        for candidate in candidates:
            if not missing_required(candidate):
                return candidate
        missing = missing_required(executable_root)
        raise RuntimeError(
            "SmartTestTool portable runtime resources are incomplete; missing: "
            + ", ".join(missing)
            + ". Run the executable from the complete SmartTestTool directory."
        )
    return Path(__file__).resolve().parents[4]


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
    from example.bridge.RedmineBridge import RedmineBridge
    from example.bridge.ToolBridge import ToolBridge
    from example.helper.TranslateHelper import TranslateHelper
    from core.config.jsonTool import app_data_dir
    from client.app.ui.page_state_migration import migrate_frontend_state

    from PySide6.QtCore import QCoreApplication
    if not QCoreApplication.organizationName():
        QCoreApplication.setOrganizationName("Amlogic")
    if not QCoreApplication.applicationName():
        QCoreApplication.setApplicationName("SmartTest")

    root = runtime_root()
    auth = AuthBridge(project_root=root)
    migrate_frontend_state(app_data_dir() / "frontend_state.json")
    translate = TranslateHelper()
    translate.init(engine)
    return {
        "AppInfo": AppInfo(),
        "TranslateHelper": translate,
        "AISettingsBridge": AISettingsBridge(),
        "AuthBridge": auth,
        "ToolBridge": ToolBridge(),
        "RedmineBridge": RedmineBridge(auth),
    }


def portable_context_smoke(engine) -> None:
    objects = create_context_objects(engine)
    auth = objects.get("AuthBridge")
    if not isinstance(getattr(auth, "_personnel", None), dict):
        raise RuntimeError("SmartTestTool AuthBridge personnel resource was not loaded")
    redmine = objects.get("RedmineBridge")
    if getattr(redmine, "_auth", None) is not auth:
        raise RuntimeError("SmartTestTool Redmine credential boundary is not shared with AuthBridge")
    print("SmartTestTool portable context: PASS")


def main() -> None:
    if "--portable-smoke-imports" in sys.argv:
        portable_smoke_imports()
        return
    if "--portable-smoke-credentials" in sys.argv:
        try:
            portable_credential_smoke()
        except Exception as exc:
            print(
                "SmartTestTool portable credentials: FAIL "
                f"({type(exc).__name__})",
                file=sys.stderr,
            )
            raise SystemExit(1) from None
        return
    if "--portable-smoke-context" in sys.argv:
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtQml import QQmlEngine
        app = QCoreApplication(sys.argv)
        portable_context_smoke(QQmlEngine())
        return
    from qasync import QEventLoop
    from PySide6.QtCore import QProcess, QUrl
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    from FluentUI import FluentUI
    from FluentUI.FluLogger import LogSetup
    from example.context_registry import register_context_objects, start_context_services
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
    start_context_services(engine)
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
