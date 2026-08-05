from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]


def _run_probe(body: str) -> subprocess.CompletedProcess[str]:
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from FluentUI.imports import resource_rc as fluent_resource_rc
from example.imports import resource_rc as example_resource_rc
app = QGuiApplication([])
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
FluentUI.registerTypes(engine)
{body}
'''
    return subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_standalone_flu_page_keeps_its_title_header_by_default():
    result = _run_probe(
        r'''
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; import FluentUI 1.0; Window { visible: true; width: 600; height: 400; FluPage { id: page; objectName: "standalonePage"; anchors.fill: parent; title: "Test" } }')
QTest.qWait(100)
roots = engine.rootObjects()
if not roots:
    print("NO_ROOT", len(warnings), warnings)
    raise SystemExit(2)
root = roots[0]
page = root.findChild(QObject, "standalonePage")
header = page.property("header")
print(page.property("title"), round(header.height()), len(warnings), warnings)
'''
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Test 40 0 []" in result.stdout


def test_navigation_hides_hosted_header_and_exposes_selected_page_title():
    result = _run_probe(
        r"""
engine.loadData(b'''import QtQuick 2.15
import QtQuick.Window 2.15
import FluentUI 1.0
Window {
    visible: true
    width: 900
    height: 700
    FluNavigationView {
        id: navigation
        objectName: "navigation"
        anchors.fill: parent
        showPageTitleHeaders: false
        pageMode: FluNavigationViewType.Stack
        items: FluObject {
            FluPaneItem { title: "Home"; url: "qrc:/example/qml/page/T_Badge.qml" }
            FluPaneItem { title: "Test"; url: "qrc:/example/qml/page/T_Buttons.qml" }
        }
        Component.onCompleted: navigateByItem(getItems()[1])
    }
}''')
QTest.qWait(200)
roots = engine.rootObjects()
if not roots:
    print("NO_ROOT", len(warnings), warnings)
    raise SystemExit(2)
root = roots[0]
navigation = root.findChild(QObject, "navigation")
def find_titled_page(obj, wanted):
    if obj.property("title") == wanted and obj.metaObject().indexOfProperty("launchMode") >= 0:
        return obj
    for child in obj.children():
        found = find_titled_page(child, wanted)
        if found is not None:
            return found
    return None
page = find_titled_page(root, "Buttons")
if page is None:
    print("PAGE_NOT_FOUND", navigation.property("currentPageTitle"), navigation.getCurrentUrl(), len(warnings), warnings)
    raise SystemExit(3)
header = page.property("header")
print(navigation.property("currentPageTitle"), page.property("title"), page.property("showTitleHeader"), round(header.height()), len(warnings), warnings)
"""
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Test Buttons False 0 0 []" in result.stdout


def test_main_window_moves_primary_page_identity_into_application_title():
    result = _run_probe(
        f'''
import os
import tempfile
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlExpression
sys.path.insert(0, r"{ROOT}")
os.environ["SMARTTEST_LOG_DIR"] = tempfile.mkdtemp(prefix="smarttest-title-")
from example.context_registry import register_context_objects
from example.component.Callback import Callback
from example.component.CircularReveal import CircularReveal
from example.component.FileWatcher import FileWatcher
from example.component.OpenGLItem import OpenGLItem
from PySide6.QtQml import qmlRegisterType
qmlRegisterType(Callback, "example", 1, 0, "Callback")
qmlRegisterType(CircularReveal, "example", 1, 0, "CircularReveal")
qmlRegisterType(FileWatcher, "example", 1, 0, "FileWatcher")
qmlRegisterType(OpenGLItem, "example", 1, 0, "OpenGLItem")
class Auth(QObject):
    changed = Signal()
    authenticated = Property(bool, lambda self: True, notify=changed)
    username = Property(str, lambda self: "tester", notify=changed)
    displayName = Property(str, lambda self: "Tester", notify=changed)
    initials = Property(str, lambda self: "T", notify=changed)
    roleText = Property(str, lambda self: "", notify=changed)
    avatarUrl = Property(str, lambda self: "", notify=changed)
class Home(QObject):
    changed = Signal()
    wallpaperUrl = Property(str, lambda self: "", notify=changed)
    wallpaperCopyright = Property(str, lambda self: "", notify=changed)
    @Slot()
    def refreshWallpaper(self): pass
class Run(QObject):
    runFinished = Signal("QVariant")
class AppInfoStub(QObject):
    changed = Signal()
    version = Property(str, lambda self: "1.0.0", notify=changed)
    updateDownloadUrl = Property(str, lambda self: "", notify=changed)
    @Slot(QObject)
    def checkUpdate(self, _callback): pass
objects = {{
    "AuthBridge": Auth(),
    "HomeBridge": Home(),
    "RunBridge": Run(),
    "AppInfo": AppInfoStub(),
}}
register_context_objects(engine, objects)
engine.load(QUrl("qrc:/example/qml/window/MainWindow.qml"))
QTest.qWait(500)
roots = engine.rootObjects()
if not roots:
    print("NO_MAIN_WINDOW", len(warnings), warnings)
    raise SystemExit(2)
window = roots[-1]
navigation = window.findChild(QObject, "mainNavigationView")
if navigation is None:
    print("MAIN_NAVIGATION_NOT_FOUND", window.property("title"), len(warnings))
    raise SystemExit(3)
def navigate(title):
    expression = QQmlExpression(
        engine.rootContext(), navigation,
        '(function() {{ var rows=getItems(); for(var i=0;i<rows.length;i++) '
        '{{ if(rows[i] && rows[i].title === "' + title + '") '
        '{{ navigateByItem(rows[i]); return true; }} }} return false; }})()'
    )
    value = expression.evaluate()
    if expression.hasError():
        raise RuntimeError(str(expression.error()))
    QTest.qWait(250)
    app.processEvents()
    return value
titles = [window.property("title")]
headers = []
for page_title in ("Buttons",):
    if not navigate(page_title):
        print("NAVIGATION_FAILED", page_title)
        raise SystemExit(4)
    titles.append(window.property("title"))
    page = None
    pending = [window]
    while pending:
        candidate = pending.pop()
        if candidate.property("title") == page_title and candidate.metaObject().indexOfProperty("launchMode") >= 0:
            page = candidate
            break
        pending.extend(candidate.children())
    headers.append(round(page.property("header").height()) if page is not None else -1)
print(titles, headers, window.property("applicationDisplayTitle"), len(warnings), warnings)
'''
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "['SmartTest', 'SmartTest.Buttons']" in result.stdout
    assert "[0] SmartTest.Buttons" in result.stdout
