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


def test_portable_clone_form_preserves_draft_edits_and_submit_signal(tmp_path):
    _run_source('''
component = QQmlComponent(engine, QUrl("qrc:/example/qml/component/issue/JiraCreateBatchDialog.qml"))
assert component.isReady(), [error.toString() for error in component.errors()]
dialog = component.createWithInitialProperties({
    "batchState": "editing", "width": 900, "height": 700,
    "cloneDrafts": [{"issueId": "r1", "state": "ready", "fields": [
        {"fieldId": "summary", "name": "Summary", "control": "text", "value": "Imported summary"}
    ]}]
})
assert dialog is not None, [error.toString() for error in component.errors()]
from PySide6.QtQuick import QQuickWindow
window = QQuickWindow()
window.resize(900, 700)
dialog.setParentItem(window.contentItem())
window.show()
QTest.qWait(100)
edits, submissions = [], []
dialog.updateCloneDraft.connect(lambda issue_id, field_id, value: edits.append((issue_id, field_id, value)))
dialog.submitCloneBatch.connect(lambda: submissions.append(True))
def find_visual(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = find_visual(child, name)
        if found is not None:
            return found
editor = find_visual(dialog, "jiraCreateText_summary")
assert editor is not None and editor.property("text") == "Imported summary"
editor.setProperty("text", "Updated summary")
editor.editingFinished.emit()
assert edits == [("r1", "summary", "Updated summary")]
button = dialog.findChild(QObject, "jiraCloneBatchCreateButton")
assert button is not None and button.property("visible") and not button.property("disabled")
button.clicked.emit()
assert submissions == [True]
objects["RedmineBridge"].close()
''', tmp_path)
