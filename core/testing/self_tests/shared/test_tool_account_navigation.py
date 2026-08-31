from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]


SETUP = '''
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example import tool_main
from example.context_registry import register_context_objects
app = QGuiApplication([])
engine = QQmlApplicationEngine()
objects = tool_main.create_context_objects(engine)
objects["AuthBridge"]._authenticated = True
register_context_objects(engine, objects)
FluentUI.registerTypes(engine)
'''


def _run_source(probe, tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", APPDATA=str(tmp_path), LOCALAPPDATA=str(tmp_path))
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(ROOT / "client/app"), str(ROOT / "client/app/ui")))
    result = subprocess.run([sys.executable, "-X", "faulthandler", "-c", SETUP + probe], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_portable_source_jira_workspace_can_be_instantiated(tmp_path):
    # Keep the standalone component probe separate from the routed window engine.
    _run_source('''
jira_component = QQmlComponent(engine, QUrl("qrc:/example/qml/component/issue/JiraIssueBrowserLayout.qml"))
assert jira_component.isReady(), [error.toString() for error in jira_component.errors()]
jira_workspace = jira_component.create()
assert jira_workspace is not None and jira_workspace.objectName() == "jiraIssueBrowserLayout"
objects["RedmineBridge"].close()
''', tmp_path)


def test_portable_source_account_navigation_creates_login_window(tmp_path):
    _run_source('''
component = QQmlComponent(engine, QUrl("qrc:/example/qml/window/LoginWindow.qml"))
assert component.isReady(), [error.toString() for error in component.errors()]
engine.load(QUrl("qrc:/example/qml/tool/ToolApp.qml"))
QTest.qWait(300)
account = next(item for window in app.allWindows()
               for item in window.findChildren(QObject)
               if item.objectName() == "toolAccountPaneItem")
account.tap.emit()
QTest.qWait(250)
assert any(window.objectName() == "toolLoginWindow" and window.isVisible()
           for window in app.allWindows())
objects["RedmineBridge"].close()
''', tmp_path)
