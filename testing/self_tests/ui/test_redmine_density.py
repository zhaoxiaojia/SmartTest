from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
REDMINE_QML_DIR = ROOT / "ui/example/imports/example/qml/component/redmine"


def _run_qml_probe(source: str) -> subprocess.CompletedProcess[str]:
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from example.imports import resource_rc
app = QGuiApplication([])
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
engine.loadData({source!r}.encode("utf-8"))
app.processEvents()
roots = engine.rootObjects()
if not roots:
    print("NO_ROOT", warnings)
    raise SystemExit(2)
root = roots[0]
print(root.property("densityScale"), root.property("scaledSpacing"), root.property("controlHeight"), len(warnings), warnings)
'''
    return subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_redmine_density_runtime_scales_spacing_and_preserves_control_floor():
    qml_dir = REDMINE_QML_DIR.as_uri()
    source = f'''
import QtQuick 2.15
import "{qml_dir}" as Redmine
QtObject {{
    property real densityScale: Redmine.RedmineDensity.scale
    property real scaledSpacing: Redmine.RedmineDensity.metric(12, 0)
    property real controlHeight: Redmine.RedmineDensity.controlHeight(36)
}}
'''

    result = _run_qml_probe(source)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "0.7 8.0 28.0 0 []" in result.stdout


def test_tool_shell_compacts_only_when_redmine_is_selected():
    tool_page = (ROOT / "ui/example/imports/example/qml/page/T_Tool.qml").as_uri()
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
class Tools(QObject):
    changed = Signal()
    groups = Property("QVariantList", lambda self: [{{
        "id": "common", "title": "Common Tools", "available": True,
        "tools": [
            {{"id": "redmine", "title": "redmine", "description": "Redmine"}},
            {{"id": "other", "title": "Other", "description": "Other"}},
        ],
    }}], notify=changed)
class Schedule(QObject):
    rowsChanged = Signal()
    toolOpenRequested = Signal(str)
    rows = Property("QVariantList", lambda self: [], notify=rowsChanged)
    @Slot()
    def refresh(self): pass
class Redmine(QObject):
    changed = Signal()
    state = Property(str, lambda self: "idle", notify=changed)
    statusText = Property(str, lambda self: "", notify=changed)
    @Slot()
    def startLogin(self): pass
    @Slot(str, str)
    def submitCredentials(self, _username, _password): pass
    @Slot(str)
    def submitVerification(self, _code): pass
    @Slot()
    def cancelLogin(self): pass
app = QGuiApplication([])
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
tools = Tools()
schedule_bridge = Schedule()
redmine_bridge = Redmine()
engine.rootContext().setContextProperty("ToolBridge", tools)
engine.rootContext().setContextProperty("ScheduleBridge", schedule_bridge)
engine.rootContext().setContextProperty("RedmineBridge", redmine_bridge)
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible: true; width: 1200; height: 800; Loader {{ id: loader; anchors.fill: parent; source: "{tool_page}" }} }}')
app.processEvents()
window = engine.rootObjects()[0]
page = window.contentItem().childItems()[0].property("item")
schedule = page.findChild(QObject, "toolScheduleArea")
sidebar = page.findChild(QObject, "toolSidebar")
app.processEvents()
redmine_sizes = (round(schedule.height()), round(sidebar.width()))
QQmlExpression(engine.rootContext(), page, "selectTool('common', 1)").evaluate()
QTest.qWait(100)
app.processEvents()
default_sizes = (round(schedule.height()), round(sidebar.width()))
selected = page.property("selectedTool")
selected = selected.toVariant() if hasattr(selected, "toVariant") else selected
print(redmine_sizes, default_sizes, page.property("selectedToolIndex"), selected.get("id"), page.property("activeDensity"), len(warnings), warnings)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    # The compact sidebar must retain enough width for expander titles and chevrons.
    assert "(83, 180) (118, 216) 1 other 1.0 0 []" in result.stdout


def test_issue_workspace_defaults_to_normal_density_and_accepts_redmine_density():
    issue_browser = (
        ROOT / "ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml"
    ).as_uri()
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
app = QGuiApplication([])
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible: true; width: 1280; height: 820; Loader {{ anchors.fill: parent; source: "{issue_browser}" }} }}')
app.processEvents()
window = engine.rootObjects()[0]
browser = window.contentItem().childItems()[0].property("item")
filter_frame = browser.findChild(QObject, "issueFilterFrame")
project_filter = browser.findChild(QObject, "issueProjectFilter")
normal = (browser.property("densityScale"), filter_frame.property("padding"), round(project_filter.height()))
browser.setProperty("densityScale", 0.70)
QTest.qWait(100)
app.processEvents()
compact = (browser.property("densityScale"), filter_frame.property("padding"), round(project_filter.height()))
print(normal, compact, len(warnings), warnings)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "(1.0, 12.0, 36) (0.7, 8.0, 28) 0 []" in result.stdout


def test_redmine_quick_view_buttons_share_one_row_at_medium_width():
    issue_browser = (
        ROOT / "ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml"
    ).as_uri()
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
app = QGuiApplication([])
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible: true; width: 1000; height: 760; Loader {{ anchors.fill: parent; source: "{issue_browser}" }} }}')
app.processEvents()
window = engine.rootObjects()[0]
browser = window.contentItem().childItems()[0].property("item")
browser.setProperty("densityScale", 0.70)
expression = QQmlExpression(engine.rootContext(), browser, 'quickViews = [{{"id":"assigned","label":"Issues assigned to me"}}, {{"id":"watched","label":"Watched issues"}}]')
expression.evaluate()
if expression.hasError():
    print("QUICK_VIEW_EXPRESSION_ERROR", expression.error())
    raise SystemExit(4)
QTest.qWait(100)
app.processEvents()
def find_item(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = find_item(child, name)
        if found is not None:
            return found
    return None
assigned = find_item(browser, "issueQuickViewButton_0")
watched = find_item(browser, "issueQuickViewButton_1")
search = find_item(browser, "issueSearchButton")
if assigned is None or watched is None or search is None:
    print("QUICK_VIEW_BUTTONS_NOT_FOUND", len(warnings), warnings)
    raise SystemExit(3)
assigned_pos = assigned.mapToItem(browser, 0, 0)
watched_pos = watched.mapToItem(browser, 0, 0)
search_pos = search.mapToItem(browser, 0, 0)
search_fits = search_pos.x() + search.width() <= browser.width()
print(round(assigned_pos.y()), round(watched_pos.y()), search_fits, len(warnings), warnings)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    rows = result.stdout.strip().split()
    assert rows[0] == rows[1], result.stdout
    assert rows[2] == "True", result.stdout
    assert rows[-2:] == ["0", "[]"], result.stdout
