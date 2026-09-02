from pathlib import Path
import os
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[4]


def test_test_suite_text_is_translated_in_both_catalogs():
    required = {"Test Suites", "My Suites", "Shared Suites", "Loading test suites...",
                "Save Current", "Save a Copy", "Update Test Suite", "Delete Test Suite",
                "Please sign in to use test suites.", "The test suite service is unavailable."}
    for locale in ("en_US", "zh_CN"):
        root = ET.parse(ROOT / f"client/app/ui/example/example_{locale}.ts").getroot()
        context = next(item for item in root.findall("context") if item.findtext("name") == "T_TestConfig")
        messages = {item.findtext("source"): item.findtext("translation") for item in context.findall("message")}
        assert required <= messages.keys()
        assert all(messages[source] for source in required)


def test_tree_component_renders_checked_and_partial_directory_states():
    script = r"""
import os, sys
sys.path.insert(0, os.path.join(os.environ["SMARTTEST_ROOT"], "client", "app", "ui"))
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from FluentUI.imports import resource_rc
app = QGuiApplication([])
engine = QQmlApplicationEngine()
FluentUI.registerTypes(engine)
qml = '''import QtQuick 2.15
import QtQuick.Window 2.15
import FluentUI 1.0
Window { visible: true; width: 500; height: 300
  property bool partialChecked: tree.checkedFor({selectionState:"partial"}, true)
  property bool partialIndeterminate: tree.indeterminateFor({selectionState:"partial"})
  property bool checkedChecked: tree.checkedFor({selectionState:"checked"}, false)
  property bool checkedIndeterminate: tree.indeterminateFor({selectionState:"checked"})
  FluTreeView { id: tree; anchors.fill: parent; checkable: true; checkLeafOnly: false
  }
}'''
engine.loadData(qml.encode())
app.processEvents()
root = engine.rootObjects()[0]
if not root.property("partialIndeterminate") or root.property("partialChecked"):
    raise SystemExit("partial state was not rendered")
if root.property("checkedIndeterminate") or not root.property("checkedChecked"):
    raise SystemExit("checked state was not rendered")
"""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SMARTTEST_ROOT"] = str(ROOT)
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_test_page_suite_panel_preferences_persist_without_business_data(tmp_path):
    script = r"""
import os, sys
from pathlib import Path
from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, os.environ["SETTINGS_ROOT"])
app = QGuiApplication([])
app.setOrganizationName("Amlogic-Test")
app.setApplicationName("SmartTest-Suite-Panel")
engine = QQmlEngine()
url = QUrl.fromLocalFile(str(Path(os.environ["SMARTTEST_ROOT"]) / "client/app/ui/example/imports/example/qml/state/TestPageState.qml"))
component = QQmlComponent(engine, url)
first = component.create()
if first is None: raise SystemExit("create failed: " + repr(component.errors()))
expression = QQmlExpression(engine.rootContext(), first, "updateSuitePanel(true, 315)")
expression.evaluate()
if expression.hasError(): raise SystemExit(repr(expression.error()))
first.deleteLater(); app.processEvents()
QSettings().sync()
second = component.create()
if not second.property("suitePanelExpanded") or second.property("suitePanelHeight") != 315:
    raise SystemExit("suite panel preference was not restored")
for forbidden in ("orderedNodeids", "parameters", "dut", "password", "cookie"):
    if second.property(forbidden) is not None:
        raise SystemExit("business data leaked into display preference owner: " + forbidden)
"""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SMARTTEST_ROOT"] = str(ROOT)
    env["SETTINGS_ROOT"] = str(tmp_path)
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_suite_dialog_uses_page_owned_draft_and_requires_a_name():
    source = (ROOT / "client/app/ui/example/imports/example/qml/page/T_TestConfig.qml").read_text(
        encoding="utf-8"
    )

    assert "property string suiteDraftName" in source
    assert "property string suiteDraftDescription" in source
    assert "property bool suiteDraftShared" in source
    assert "positiveDisabled: suiteDraftName.trim() === \"\"" in source
    assert "suite_name.text =" not in source
    assert "suite_description.text =" not in source
    assert "suite_shared.checked =" not in source


def test_suite_actions_are_disabled_when_the_service_is_unavailable():
    source = (ROOT / "client/app/ui/example/imports/example/qml/page/T_TestConfig.qml").read_text(
        encoding="utf-8"
    )

    assert "property bool suiteServiceAvailable:" in source
    assert source.count("!suiteServiceAvailable") >= 4


def test_content_dialog_can_disable_its_positive_action():
    source = (
        ROOT / "client/app/ui/FluentUI/imports/FluentUI/Controls/FluContentDialog.qml"
    ).read_text(encoding="utf-8")

    assert "property bool positiveDisabled: false" in source
    assert "disabled: control.positiveDisabled" in source
