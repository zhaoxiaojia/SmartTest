from __future__ import annotations

import json
import gc
import os
import subprocess
import sys
import weakref
import xml.etree.ElementTree as ET
import importlib.util
import zipfile
from pathlib import Path

import pytest

from ui.example.bridge.ToolBridge import build_tool_groups, load_tool_access
from ui.example.bridge.ToolBridge import ToolBridge
from ui.example.bridge.ScheduleBridge import ScheduleBridge
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Property, Signal, Slot
from PySide6.QtQml import QQmlEngine


ROOT = Path(__file__).resolve().parents[3]
PERSONNEL_PATH = ROOT / "config" / "personnel.json"


def test_tool_portable_entry_has_an_independent_minimal_context_contract():
    sys.path.insert(0, str(ROOT / "ui"))
    from example import tool_main

    assert set(tool_main.TOOL_CONTEXT_NAMES) == {
        "AppInfo", "TranslateHelper",
        "AISettingsBridge", "AuthBridge", "ToolBridge", "RedmineBridge",
        "JiraAuditBridge", "ConfluenceAuditBridge", "DailyReportBridge",
        "ScheduleBridge",
    }


def test_tool_portable_runtime_root_prefers_ondir_executable_payload(
    tmp_path, monkeypatch,
):
    sys.path.insert(0, str(ROOT / "ui"))
    from example import tool_main

    app_dir = tmp_path / "SmartTestTool"
    for relative in ("config/personnel.json", "build/generated/build_manifest.json"):
        target = app_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(tool_main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tool_main.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(tool_main.sys, "executable", str(app_dir / "SmartTestTool.exe"))

    assert tool_main.runtime_root() == app_dir


def test_tool_portable_runtime_root_rejects_incomplete_frozen_payload(
    tmp_path, monkeypatch,
):
    sys.path.insert(0, str(ROOT / "ui"))
    from example import tool_main

    app_dir = tmp_path / "SmartTestTool"
    (app_dir / "config").mkdir(parents=True)
    (app_dir / "config/personnel.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(tool_main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tool_main.sys, "_MEIPASS", str(tmp_path / "empty"), raising=False)
    monkeypatch.setattr(tool_main.sys, "executable", str(app_dir / "SmartTestTool.exe"))

    with pytest.raises(RuntimeError) as caught:
        tool_main.runtime_root()

    message = str(caught.value)
    assert "build/generated/build_manifest.json" in message
    assert "complete SmartTestTool directory" in message


def test_tool_runtime_resource_manifest_is_single_packaging_source():
    from support.packaging.tool_runtime_resources import (
        TOOL_RUNTIME_RESOURCES, pyinstaller_datas,
    )

    assert [(item.source, item.target, item.required) for item in TOOL_RUNTIME_RESOURCES] == [
        ("config/personnel.json", "config/personnel.json", True),
        ("build/generated/build_manifest.json", "build/generated/build_manifest.json", True),
    ]
    assert pyinstaller_datas(ROOT) == [
        (str(ROOT / "config/personnel.json"), "config"),
        (str(ROOT / "build/generated/build_manifest.json"), str(Path("build/generated"))),
    ]
    spec_source = (ROOT / "support/packaging/pyinstaller/tool.spec").read_text("utf-8")
    assert "datas=pyinstaller_datas(repo_root)" in spec_source
    assert '"config", "personnel.json"' not in spec_source
    assert '"build", "generated", "build_manifest.json"' not in spec_source


def test_tool_portable_qrc_contains_only_the_approved_shell_and_pages():
    qrc = ROOT / "ui/example/imports/tool_resource.qrc"
    resources = {
        node.attrib.get("alias", node.text).replace("\\", "/")
        for node in ET.parse(qrc).iterfind(".//file")
    }
    assert {
        "example/qml/tool/ToolApp.qml",
        "example/qml/tool/ToolWindow.qml",
        "example/qml/page/T_Tool.qml",
        "example/qml/page/T_Settings.qml",
        "example/qml/window/LoginWindow.qml",
        "example/qml/window/AboutWindow.qml",
    } <= resources
    forbidden = ("T_Home.qml", "T_TestConfig.qml", "T_Run.qml", "T_Report.qml",
                 "T_AI.qml", "T_Jira.qml", "T_Debug.qml", "T_BootVideo.qml")
    assert not any(path.endswith(forbidden) for path in resources)


def test_tool_portable_build_helpers_validate_and_zip_a_real_tree(tmp_path):
    script = ROOT / "support/scripts/script-build-tool-portable.py"
    spec = importlib.util.spec_from_file_location("tool_portable_build", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    app_dir = tmp_path / "SmartTestTool"
    app_dir.mkdir()
    (app_dir / "SmartTestTool.exe").write_bytes(b"exe")
    (app_dir / "payload.txt").write_text("tool", encoding="utf-8")
    for relative in ("config/personnel.json", "build/generated/build_manifest.json"):
        target = app_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")
    module.validate_distribution(app_dir)
    archive = module.create_portable_zip(app_dir, "1.2.3", tmp_path)
    assert archive.name == "SmartTestTool-1.2.3-windows-x64.zip"
    with zipfile.ZipFile(archive) as package:
        assert sorted(package.namelist()) == [
            "SmartTestTool/SmartTestTool.exe",
            "SmartTestTool/build/generated/build_manifest.json",
            "SmartTestTool/config/personnel.json",
            "SmartTestTool/payload.txt",
        ]

    (app_dir / "testing-runtime.dll").write_bytes(b"forbidden")
    try:
        module.validate_distribution(app_dir)
    except RuntimeError as exc:
        assert "testing" in str(exc).lower()
    else:
        raise AssertionError("forbidden runtime was not rejected")


def test_tool_distribution_validation_lists_missing_required_resources(tmp_path):
    module = _load_tool_portable_build_module()
    app_dir = tmp_path / "SmartTestTool"
    app_dir.mkdir()
    (app_dir / "SmartTestTool.exe").write_bytes(b"exe")

    with pytest.raises(RuntimeError) as caught:
        module.validate_distribution(app_dir)

    assert "config/personnel.json" in str(caught.value)
    assert "build/generated/build_manifest.json" in str(caught.value)


def test_tool_context_smoke_uses_real_context_factory_and_loaded_personnel(monkeypatch):
    sys.path.insert(0, str(ROOT / "ui"))
    from example import tool_main

    auth = type("Auth", (), {"_personnel": {"amlogic": {}}})()
    monkeypatch.setattr(
        tool_main, "create_context_objects",
        lambda engine: {"AuthBridge": auth, "engine": engine},
    )

    tool_main.portable_context_smoke(object())


def test_tool_build_context_smoke_runs_portable_executable_from_its_directory(
    tmp_path, monkeypatch,
):
    module = _load_tool_portable_build_module()
    app_dir = tmp_path / "SmartTestTool"
    executable = app_dir / "SmartTestTool.exe"
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: (
        calls.append((args, kwargs)) or
        subprocess.CompletedProcess(args[0], 0, "SmartTestTool portable context: PASS\n", "")
    ))

    module.validate_context_smoke(executable)

    assert calls[0][0][0] == [str(executable), "--portable-smoke-context"]
    assert calls[0][1]["cwd"] == app_dir


def _load_tool_portable_build_module():
    script = ROOT / "support/scripts/script-build-tool-portable.py"
    spec = importlib.util.spec_from_file_location("tool_portable_build", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_tool_archive_validation_matches_module_names_not_substrings():
    script = ROOT / "support/scripts/script-build-tool-portable.py"
    spec = importlib.util.spec_from_file_location("tool_portable_build", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.find_forbidden_archive_modules("""
 example.bridge.DailyReportBridge
 pygments.lexers.testing
""") == []


def test_tool_archive_validation_rejects_forbidden_module_trees():
    script = ROOT / "support/scripts/script-build-tool-portable.py"
    spec = importlib.util.spec_from_file_location("tool_portable_build", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.find_forbidden_archive_modules("""
 example.bridge.ReportBridge
 testing.params.options
""") == ["example.bridge.ReportBridge", "testing"]


def test_tool_portable_restarts_only_for_exit_code_931():
    sys.path.insert(0, str(ROOT / "ui"))
    from example import tool_main

    calls = []
    assert tool_main.restart_for_exit_code(
        931, "tool.exe", ["tool.exe", "--probe"],
        lambda executable, arguments: calls.append((executable, arguments)),
    ) is True
    assert calls == [("tool.exe", ["tool.exe", "--probe"])]
    assert tool_main.restart_for_exit_code(
        0, "tool.exe", ["tool.exe"],
        lambda executable, arguments: calls.append((executable, arguments)),
    ) is False
    assert len(calls) == 1


def test_tool_portable_metrics_include_elapsed_payload_and_zip_bytes(tmp_path):
    script = ROOT / "support/scripts/script-build-tool-portable.py"
    spec = importlib.util.spec_from_file_location("tool_portable_metrics", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    archive = tmp_path / "tool.zip"
    archive.write_bytes(b"zip-data")

    assert module.build_metrics(
        {"files": 12, "bytes": 3456}, archive, elapsed_seconds=7.25,
    ) == {
        "files": 12, "bytes": 3456, "zip_bytes": 8,
        "build_seconds": 7.25,
    }


def test_tool_portable_real_navigation_loads_settings_about_and_login_without_warnings():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}"); sys.path.insert(0, r"{ROOT}")
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example import tool_main
from example.context_registry import register_context_objects
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
objects=tool_main.create_context_objects(engine); objects["AuthBridge"]._authenticated=True
register_context_objects(engine, objects); FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import FluentUI 1.0; QtObject {{ Component.onCompleted: FluRouter.routes={{"/login":"qrc:/example/qml/window/LoginWindow.qml","/about":"qrc:/example/qml/window/AboutWindow.qml"}} }}')
engine.load(QUrl("qrc:/example/qml/tool/ToolWindow.qml")); QTest.qWait(400)
def find(name):
    for root in engine.rootObjects()+app.allWindows():
        if root.objectName()==name: return root
        result=root.findChild(QObject,name)
        if result: return result
def click(control):
    point=control.mapToScene(QPointF(control.width()/2,control.height()/2))
    QTest.mouseClick(control.window(),Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
    QTest.qWait(250); app.processEvents()
find("toolSettingsPaneItem").tap.emit(); QTest.qWait(250); app.processEvents()
settings=bool(find("toolSettingsPage"))
click(find("toolAboutButton")); about=bool(find("toolAboutWindow"))
find("toolAboutWindow").close(); QTest.qWait(100)
find("toolAccountPaneItem").tap.emit(); QTest.qWait(250); app.processEvents()
login=bool(find("toolLoginWindow")); objects["RedmineBridge"].close()
print(settings, about, login, len(warnings), warnings)
'''
    result = subprocess.run(
        [str(ROOT / ".venv/Scripts/python.exe"), "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "True True True 0 []" in result.stdout


def test_tool_portable_source_smoke_imports_required_dynamic_dependencies():
    result = subprocess.run(
        [
            str(ROOT / ".venv/Scripts/python.exe"),
            str(ROOT / "ui/example/tool_main.py"),
            "--portable-smoke-imports",
        ],
        cwd=ROOT,
        env=dict(
            os.environ,
            PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / "ui"))),
        ),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "SmartTestTool portable smoke imports: PASS" in result.stdout


class RuntimeAuth(QObject):
    authChanged = Signal()
    username = Property(str, lambda self: "chen.chen", notify=authChanged)


class ScheduleProvider(QObject):
    scheduleRowsChanged = Signal()

    def __init__(self, rows=()):
        super().__init__()
        self._rows = list(rows)
        self.actions = []

    scheduleRows = Property(
        "QVariantList", lambda self: list(self._rows), notify=scheduleRowsChanged,
    )

    def replace(self, rows):
        self._rows = list(rows)
        self.scheduleRowsChanged.emit()

    @Slot()
    def refreshPlans(self):
        self.actions.append(("refresh",))

    @Slot(str, bool)
    def setPlanEnabled(self, plan_id, enabled):
        self.actions.append(("enabled", plan_id, enabled))
        self._rows = [
            {**row, "enabled": enabled} if row["planId"] == plan_id else row
            for row in self._rows
        ]
        self.scheduleRowsChanged.emit()

    @Slot(str)
    def runPlanNow(self, plan_id):
        self.actions.append(("run", plan_id))

    @Slot(str)
    def deletePlan(self, plan_id):
        self.actions.append(("delete", plan_id))


def schedule_row(plan_id="weekly-a", *, enabled=True):
    return {
        "provider": "confluence", "planId": plan_id,
        "businessTitle": "Project Weekly Audit", "title": "Weekly A",
        "enabled": enabled, "registered": True,
        "reconciliation": "ok",
        "nextRunAt": "2026-08-10T09:00:00+08:00",
        "lastRunAt": "2026-08-03T09:00:00+08:00", "lastResultCode": 0,
        "targetToolId": "confluence_audit",
        "taskTypeText": "Daily Report", "contentText": "Demo",
        "planText": "Daily 11:30",
    }


def test_schedule_bridge_maps_read_only_status_and_tracks_provider_updates():
    provider = ScheduleProvider((schedule_row(enabled=False),))
    bridge = ScheduleBridge({"confluence": provider})
    assert bridge.rows[0]["statusText"] == "Disabled"

    provider.replace((schedule_row(),))

    assert bridge.rows[0]["statusText"] == "Ready"
    assert bridge.rows[0]["nextRunText"] == "Next run: 2026-08-10 09:00"
    assert bridge.rows[0]["taskTypeText"] == "Daily Report"
    assert bridge.rows[0]["contentText"] == "Demo"
    assert bridge.rows[0]["planText"] == "Daily 11:30"

    provider.replace(({
        key: value for key, value in schedule_row().items()
        if key not in {"taskTypeText", "contentText", "planText"}
    },))
    assert bridge.rows[0]["taskTypeText"] == ""
    assert bridge.rows[0]["contentText"] == ""
    assert bridge.rows[0]["planText"] == ""


def test_schedule_bridge_dispatches_management_to_existing_provider_owner():
    provider = ScheduleProvider((
        schedule_row("missing") | {"registered": False},
        schedule_row("error") | {"reconciliation": "invalid_task"},
    ))
    bridge = ScheduleBridge({"confluence": provider})

    bridge.refresh()
    bridge.setPlanEnabled("confluence", "missing", False)
    bridge.runNow("confluence", "missing")
    bridge.deletePlan("confluence", "missing")

    assert provider.actions == [
        ("refresh",), ("enabled", "missing", False),
        ("run", "missing"), ("delete", "missing"),
    ]
    assert [row["statusText"] for row in bridge.rows] == [
        "Disabled", "Needs attention",
    ]
    assert not hasattr(bridge, "openPlan")


def test_tool_bridge_survives_runtime_context_registration_and_exposes_redmine():
    from ui.example.context_registry import register_context_objects

    app = QCoreApplication.instance() or QCoreApplication([])
    engine = QQmlEngine()
    context = engine.rootContext()
    register_context_objects(engine, {"ToolBridge": ToolBridge()})
    gc.collect()

    bridge = context.contextProperty("ToolBridge")
    assert bridge is not None
    smart_home = next(group for group in bridge.groups if group["id"] == "SmartHome")
    assert smart_home["available"] is True
    assert smart_home["tools"][0]["id"] == "redmine"
    assert smart_home["tools"][0]["title"] == "redmine"


def test_confluence_tool_visible_title_is_project_weekly_audit():
    class ManagerAuth(RuntimeAuth):
        username = Property(str, lambda self: "chao.li", notify=RuntimeAuth.authChanged)
    bridge = ToolBridge()
    common = next(group for group in bridge.groups if group["id"] == "common")
    tool = next(item for item in common["tools"] if item["id"] == "confluence_audit")
    assert bridge.groups[0]["id"] == "common"
    assert tool["title"] == "Project Weekly Audit"


def test_production_context_ownership_survives_gc_and_tool_dialogs_are_warning_free(
    tmp_path,
):
    probe = f'''
import gc, sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, QPointF, Property, Signal, Slot, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.JiraAuditBridge import JiraAuditBridge
from example.bridge.ScheduleBridge import ScheduleBridge
from example.bridge.ToolBridge import ToolBridge
from example.context_registry import register_context_objects
class Auth(QObject):
    authChanged = Signal()
    username = Property(str, lambda self: "chao.li", notify=authChanged)
    def currentUsername(self): return self.username
class Redmine(QObject):
    changed = Signal(); credentialsRequired = Signal(); verificationRequired = Signal()
    state = Property(str, lambda self: "idle", notify=changed)
    statusText = Property(str, lambda self: "ready", notify=changed)
    loading = Property(bool, lambda self: False, notify=changed)
    calls = 0
    @Slot()
    def startLogin(self): self.calls += 1
    @Slot(str, str)
    def submitCredentials(self, _u, _p): pass
    @Slot(str)
    def submitVerification(self, _c): pass
    @Slot()
    def cancelLogin(self): pass
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]; engine.warnings.connect(lambda rows: warnings.extend(rows))
auth=Auth(); redmine=Redmine(); daily=QObject()
register_context_objects(engine, {{"AuthBridge": auth, "ToolBridge": ToolBridge(), "ScheduleBridge": ScheduleBridge({{}}), "RedmineBridge": redmine, "JiraAuditBridge": JiraAuditBridge(auth), "DailyReportBridge": daily}})
del auth; gc.collect()
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible: true; width: 1200; height: 800; Loader {{ anchors.fill: parent; source: "qrc:/example/qml/page/T_Tool.qml" }} }}')
app.processEvents(); gc.collect(); app.processEvents(); window=engine.rootObjects()[0]; root=window.contentItem().childItems()[0].property("item")
def find_by(prop, value):
    pending=[root]
    while pending:
        item=pending.pop()
        if item.property(prop)==value: return item
        pending.extend(item.children())
        if hasattr(item, "childItems"): pending.extend(item.childItems())
smart_home=find_by("headerText", "SmartHome"); p=smart_home.mapToScene(QPointF(smart_home.width()/2,22)); QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(p.x()),round(p.y()))); QTest.qWait(250); app.processEvents()
entry=find_by("text", "redmine"); p=entry.mapToScene(QPointF(entry.width()/2,entry.height()/2)); QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(p.x()),round(p.y()))); app.processEvents()
button=root.findChild(QObject,"redmineLoginButton"); p=button.mapToScene(QPointF(button.width()/2,button.height()/2)); QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(p.x()),round(p.y()))); app.processEvents()
redmine.credentialsRequired.emit(); app.processEvents(); redmine.verificationRequired.emit(); app.processEvents()
selected=root.property("selectedTool"); selected=selected.toVariant() if hasattr(selected,"toVariant") else selected
bad=[str(item) for item in warnings]
print(selected.get("id"), redmine.calls, len(engine._context_objects), len(bad), bad)
engine.deleteLater(); app.processEvents(); app.quit()
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "redmine 1 6 0 []" in result.stdout


def test_context_registry_releases_objects_when_engine_is_destroyed():
    from ui.example.context_registry import register_context_objects

    app = QCoreApplication.instance() or QCoreApplication([])
    engine = QQmlEngine()
    instance = QObject()
    reference = weakref.ref(instance)
    retained = register_context_objects(engine, {"TemporaryBridge": instance})
    del instance
    gc.collect()
    assert reference() is not None

    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()

    assert retained == {}
    assert reference() is None


def run_tool_qml_interaction_probe(account: str) -> str:
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, QPointF, Property, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.ScheduleBridge import ScheduleBridge
from example.bridge.ToolBridge import ToolBridge
class Auth(QObject):
    authChanged = Signal()
    username = Property(str, lambda self: "{account}", notify=authChanged)
class Redmine(QObject):
    changed = Signal(); credentialsRequired = Signal(); verificationRequired = Signal()
    state = Property(str, lambda self: "idle", notify=changed)
    statusText = Property(str, lambda self: "ready", notify=changed)
    loading = Property(bool, lambda self: False, notify=changed)
    calls = 0
    @Slot()
    def startLogin(self): self.calls += 1
    @Slot(str, str)
    def submitCredentials(self, _u, _p): pass
    @Slot(str)
    def submitVerification(self, _c): pass
    @Slot()
    def cancelLogin(self): pass
class JiraAudit(QObject):
    changed = Signal()
    viewState = Property("QVariantMap", lambda self: {{"state":"idle","statusText":"","inputError":"","progressValue":0.0,"processedCount":0,"totalCount":0,"ruleRows":[],"resultSummary":{{}},"violationRows":[],"violationRowCount":0,"violationPage":0,"violationPageCount":0,"aiReviewText":"","exportPath":"","canStart":True,"canConfirm":False,"canExport":False}}, notify=changed)
    @Slot(str)
    def startAudit(self, _text): pass
    @Slot()
    def confirmAudit(self): pass
    @Slot()
    def exportReport(self): pass
    @Slot()
    def previousViolationPage(self): pass
    @Slot()
    def nextViolationPage(self): pass
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]; engine.warnings.connect(lambda rows: warnings.extend(rows))
auth=Auth(); tools=ToolBridge(); schedule=ScheduleBridge({{}}); redmine=Redmine(); jira=JiraAudit()
engine.rootContext().setContextProperty("ToolBridge", tools); engine.rootContext().setContextProperty("ScheduleBridge", schedule); engine.rootContext().setContextProperty("RedmineBridge", redmine); engine.rootContext().setContextProperty("JiraAuditBridge", jira)
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible: true; width: 1200; height: 800; Loader {{ anchors.fill: parent; source: "qrc:/example/qml/page/T_Tool.qml" }} }}')
app.processEvents(); window=engine.rootObjects()[0]; root=window.contentItem().childItems()[0].property("item")
def find_by(prop, value):
    pending=[root]
    while pending:
        item=pending.pop()
        if item.property(prop)==value: return item
        pending.extend(item.children())
        if hasattr(item, "childItems"): pending.extend(child for child in item.childItems() if child not in pending)
smart_home=find_by("headerText", "SmartHome")
header_point=smart_home.mapToScene(QPointF(smart_home.width()/2, 22))
QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(header_point.x()), round(header_point.y()))); QTest.qWait(250); app.processEvents()
entry=find_by("text", "redmine")
entry_visible=entry is not None and entry.property("visible") and entry.property("height") > 0
if entry_visible:
    entry_point=entry.mapToScene(QPointF(entry.width()/2, entry.height()/2))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(entry_point.x()), round(entry_point.y()))); app.processEvents()
selected=root.property("selectedTool"); selected=selected.toVariant() if hasattr(selected,"toVariant") else selected; button=root.findChild(QObject, "redmineLoginButton")
workspace_visible=button is not None and button.property("visible")
if workspace_visible:
    button_point=button.mapToScene(QPointF(button.width()/2, button.height()/2))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(button_point.x()), round(button_point.y()))); app.processEvents()
bad=[str(item) for item in warnings if "ToolBridge" in str(item) or "undefined" in str(item) or "null" in str(item)]
print(smart_home.property("expand"), entry_visible, selected.get("id"), workspace_visible, redmine.calls, len(bad))
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_tool_qml_runtime_expands_and_activates_visible_redmine_entry():
    assert "True True redmine False 1 0" in run_tool_qml_interaction_probe("chen.chen")


def test_tool_qml_runtime_exposes_redmine_to_every_account():
    assert "True True redmine False 1 0" in run_tool_qml_interaction_probe(
        "unknown.account"
    )


def test_personnel_declares_product_line_and_technical_center_owners():
    payload = json.loads(PERSONNEL_PATH.read_text(encoding="utf-8"))

    assert {item["id"]: item["owner_account"] for item in payload["amlogic"]["product_lines"]} == {
        "STB": "junjie.li",
        "TV": "jianfan.ai",
        "SmartHome": "fred.chen",
        "IPTV": "lingling.yu",
    }
    assert payload["amlogic"]["technical_centers"] == [
        {
            "id": "Wi-Fi",
            "name": "Wi-Fi",
            "owner_account": "zijie.chen",
            "active": True,
        }
    ]


def test_tool_groups_are_complete_and_identical_for_every_account():
    groups = build_tool_groups()

    assert [group["id"] for group in groups] == [
        "common", "STB", "TV", "SmartHome", "IPTV", "Wi-Fi"
    ]
    assert all(group["available"] for group in groups)
    assert groups[0] == {
        "id": "common", "available": True,
        "tools": [
            {"id": "jira_audit"}, {"id": "confluence_audit"},
            {"id": "daily_report"},
        ],
    }
    assert next(group for group in groups if group["id"] == "SmartHome")["tools"] == [
        {"id": "redmine"}
    ]
    assert all(
        not group["tools"] for group in groups
        if group["id"] not in {"common", "SmartHome"}
    )


def test_personnel_uses_three_explicit_fae_departments_and_fred_owns_smarthome():
    from ui.example.bridge.ToolBridge import amlogic_employees, employee_department

    personnel = load_tool_access(PERSONNEL_PATH)

    assert set(personnel["amlogic"]["departments"]) == {"FAE-QA", "FAE-SW", "FAE-HW"}
    fred = next(item for item in amlogic_employees(personnel) if item["account"] == "fred.chen")
    assert fred["grade"] == "M5"
    assert fred["organization"]["department"] == "FAE-SW"
    assert employee_department(personnel, "fred.chen") == "FAE-SW"
    assert employee_department(personnel, "FRED.CHEN") == ""
    assert employee_department(personnel, "missing.account") == ""
    assert any(
        item["product_line_id"] == "SmartHome" and item["primary"]
        for item in fred["assignments"]
    )


def test_tool_navigation_and_page_layout_contract():
    items = (ROOT / "ui/example/imports/example/qml/global/ItemsOriginal.qml").read_text(
        encoding="utf-8"
    )
    page = (ROOT / "ui/example/imports/example/qml/page/T_Tool.qml").read_text(encoding="utf-8")

    assert "id: item_tool" in items
    assert 'title: qsTr("Tool")' in items
    assert "isProtectedRoute(item, item_tool)" in items
    assert 'url: "qrc:/example/qml/page/T_Tool.qml"' in items
    assert "icon: FluentIcons.Repair" in items
    assert "icon: FluentIcons.DeveloperTools" not in items[items.index("id: item_tool"):]
    assert "FluentIcons.Toolbox" not in items
    assert "ListView" not in page
    assert "ToolBridge.groups" in page
    assert 'objectName: "toolScheduleArea"' in page
    assert "property bool scheduleExpanded: false" in page
    assert 'objectName: "toolScheduleToggle"' in page
    assert "visible: scheduleExpanded &&" in page
    assert "model: ScheduleBridge.rows" in page
    assert "model: ToolBridge.groups" in page
    assert "ScheduleBridge.setPlanEnabled(" in page
    assert 'self.tr("Common Tools")' in (ROOT / "ui/example/bridge/ToolBridge.py").read_text(encoding="utf-8")
    assert 'qsTr("Custom Tools")' in page
    assert 'text: qsTr("Tools")' not in page
    assert "Layout.preferredWidth: 216" in page
    assert "toolGroup: modelData" in page
    assert "headerText: toolGroup.title" in page
    assert 'objectName: "toolWorkspaceTitle"' in page
    assert "font.pixelSize: 20" in page
    assert "selectedTool.description" not in page
    assert 'objectName: "redmineWorkspaceScroll"' in page
    assert "ScrollBar.vertical: FluScrollBar" in page
    assert "onToolActivated: (groupId, toolIndex) => selectTool(groupId, toolIndex)" in page
    assert "sourceComponent: tool_group_content" not in page
    assert "Component {\n        id: tool_group_content" not in page
    component = (ROOT / "ui/example/imports/example/qml/component/ToolGroupExpander.qml").read_text(encoding="utf-8")
    assert "model: root.toolGroup.available ? root.toolGroup.tools : []" in component
    assert "root.expand && root.toolGroup.available" in component
    assert "horizontalAlignment: Text.AlignLeft" in component
    assert "AuthBridge.productLines" not in page
    assert "AuthBridge.displayName" not in page
    assert "selectedToolIndex = model.index" not in page


def test_redmine_clone_editor_covers_the_scrollable_workspace_viewport():
    page = (ROOT / "ui/example/imports/example/qml/page/T_Tool.qml").read_text(encoding="utf-8")

    assert 'objectName: "redmineWorkspaceHost"' in page
    assert "id: cloneBatchOverlay" in page
    assert "anchors.fill: parent" in page[page.index("id: cloneBatchOverlay"):]
    assert "z: 1000" in page[page.index("id: cloneBatchOverlay"):]
    assert "interactive: !cloneBatchOverlay.active" in page
    assert "visible: !cloneBatchOverlay.active" in page
    assert "contentHeight: Math.max(height, 840)" in page
    assert "contentHeight: cloneBatchActive" not in page


def test_schedule_qml_shows_read_only_status_and_next_run():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, QPointF, Property, Signal, Slot, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
class Tools(QObject):
    changed = Signal()
    groups = Property("QVariantList", lambda self:[{{"id":"common", "title":"Common Tools", "available":True, "tools":[{{"id":"other_tool", "title":"Other", "description":""}}, {{"id":"future_tool", "title":"Future", "description":""}}]}}], notify=changed)
class Schedule(QObject):
    rowsChanged = Signal()
    def __init__(self):
        super().__init__(); self.actions=[]; self._rows=[{{"provider":"future", "planId":"weekly-a", "businessTitle":"Future Audit", "title":"Weekly A", "enabled":True, "registered":True, "statusText":"Ready", "nextRunText":"Next run: 2026-08-06 19:00", "taskTypeText":"Daily Report", "contentText":"Demo", "planText":"Daily 11:30", "manageable":True, "operationRunning":False, "operationText":""}}]
    rows = Property("QVariantList", lambda self:list(self._rows), notify=rowsChanged)
    @Slot()
    def refresh(self): self.actions.append(("refresh",))
class Redmine(QObject):
    changed = Signal(); state = Property(str, lambda self:"idle", notify=changed)
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]
engine.warnings.connect(lambda rows:warnings.extend(str(row) for row in rows))
tools=Tools(); schedule=Schedule(); redmine=Redmine()
engine.rootContext().setContextProperty("ToolBridge", tools); engine.rootContext().setContextProperty("ScheduleBridge", schedule); engine.rootContext().setContextProperty("RedmineBridge", redmine)
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible:true; width:1200; height:800; Loader {{ anchors.fill:parent; source:"qrc:/example/qml/page/T_Tool.qml" }} }}')
app.processEvents(); window=engine.rootObjects()[0]; root=window.contentItem().childItems()[0].property("item")
def item(name):
    pending=[root]
    while pending:
        current=pending.pop()
        if current.objectName()==name: return current
        pending.extend(current.children())
        if hasattr(current, "childItems"): pending.extend(current.childItems())
def click(control):
    point=control.mapToScene(QPointF(control.width()/2, control.height()/2)); QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y()))); app.processEvents()
click(item("toolScheduleToggle"))
status=item("toolScheduleStatus_weekly-a"); next_run=item("toolScheduleNextRun_weekly-a")
task_type=item("toolScheduleType_weekly-a"); content=item("toolScheduleContent_weekly-a"); plan=item("toolSchedulePlan_weekly-a")
controls=[item("toolScheduleToggle_weekly-a"), item("toolScheduleRunNow_weekly-a"), item("toolScheduleDelete_weekly-a")]
print(status.property("text"), next_run.property("text"), task_type.property("text"), content.property("text"), plan.property("text"), all(controls), schedule.actions, len(warnings), warnings)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Ready Next run: 2026-08-06 19:00 Type: Daily Report Content: Demo Plan: Daily 11:30 True [('refresh',)] 0 []" in result.stdout


def test_redmine_workspace_reuses_issue_detail_and_exposes_layout_signals():
    component_root = ROOT / "ui/example/imports/example/qml/component/redmine"
    issue_root = ROOT / "ui/example/imports/example/qml/component/issue"
    login = (component_root / "RedmineLoginView.qml").read_text(encoding="utf-8")
    workspace = (component_root / "RedmineWorkspace.qml").read_text(encoding="utf-8")
    browser = (issue_root / "JiraIssueBrowserLayout.qml").read_text(encoding="utf-8")
    detail = (issue_root / "JiraIssueDetailLayout.qml").read_text(encoding="utf-8")
    page = (ROOT / "ui/example/imports/example/qml/page/T_Tool.qml").read_text(encoding="utf-8")

    assert "Tool workspace" not in page
    assert "RedmineLoginView" in page
    assert "RedmineWorkspace" in page
    assert "RedmineBridge.state === \"authenticated\"" in page
    assert page.count("visible: active") >= 2
    assert "maybeStartRedmineLogin" in page
    assert "RedmineBridge.startLogin()" in page
    assert 'visible: root.state === "failed"' in login
    assert 'root.state === "idle" || root.state === "failed"' not in login
    for state in ("idle", "signing_in", "credentials_required", "verification_required", "failed"):
        assert f'\"{state}\"' in login
    for signal in (
        "startLoginRequested", "credentialsSubmitRequested",
        "verificationSubmitRequested", "cancelRequested",
    ):
        assert f"signal {signal}" in login
    assert "JiraIssueBrowserLayout" in workspace
    assert "FluFrame" not in workspace
    for label in ("All projects", "All statuses", "All types", "Contains text", "Search"):
        assert f'qsTr("{label}")' in browser
    assert 'typeFilters: [qsTr("All types"), "Bug", "Support"]' in workspace
    assert 'statusFilters: [qsTr("All statuses"), "Open", "Closed"]' in workspace
    assert "typeFilters: RedmineBridge.typeFilterLabels" not in page
    assert "JiraIssueDetailLayout" in browser
    assert "signal searchRequested" in browser
    assert "signal quickViewRequested" in browser
    assert "signal cancelSearchRequested" in browser
    assert "property var projectOptions" in browser
    assert "!root.projectsReady" in browser
    assert 'valueRole: safeCount(root.projectOptions) ? "id" : ""' in browser
    assert "projectFilter.currentValue" in browser
    assert browser.count("id: projectFilter") == 1
    assert "popup.width: Math.max(width, 640)" in browser
    assert "ToolTip.text: displayText" in browser
    assert "selectedProjectId()" in browser
    assert "signal issueSelected" in browser
    assert "positionText" in detail
    assert "previousIssueRequested" in detail
    assert "nextIssueRequested" in detail
    assert "toggleIssueListRequested" in detail
    assert "RedmineBridge.issueRows" in page
    assert "RedmineBridge.selectedIssue" in page
    assert "RedmineBridge.filters" in page
    assert "RedmineBridge.dataLoaded" in page
    assert "RedmineBridge.dataTotal" in page
    assert "RedmineBridge.applyFilters" in page
    assert "RedmineBridge.quickViews" in page
    assert "RedmineBridge.projectOptions" in page
    assert "RedmineBridge.cancelSearch()" in page
    assert "RedmineBridge.activateQuickView(quickViewId)" in page
    assert "FluProgressBar" in browser
    assert "RedmineBridge.selectIssue" in page


def test_redmine_workspace_qrc_loads_without_qml_warnings():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible: true; width: 1280; height: 820; Loader {{ anchors.fill: parent; source: "qrc:/example/qml/component/redmine/RedmineWorkspace.qml" }} }}')
app.processEvents()
print(len(engine.rootObjects()), len(warnings), warnings)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "1 0 []" in result.stdout


def test_jira_audit_workspace_qrc_persists_input_and_loads_without_warnings(
    tmp_path,
):
    probe = f'''
import sys, time
sys.path.insert(0, r"{ROOT / 'ui'}")
sys.path.insert(0, r"{ROOT}")
from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject, Property, QSettings, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
class Auth(QObject):
    authChanged = Signal()
    authenticated = Property(bool, lambda self: True, notify=authChanged)
    pageStateAccount = Property(str, lambda self: "alice", notify=authChanged)
class JiraAudit(QObject):
    changed = Signal()
    def __init__(self):
        super().__init__()
        self._view = {{
        "state": "awaiting_confirmation", "statusText": "ready", "inputError": "",
        "progressValue": 1.0, "processedCount": 1, "totalCount": 1,
        "ruleRows": [], "resultSummary": {{"totalCount": 1, "passedCount": 0, "failedCount": 1, "violationCount": 1}},
        "violationRows": [{{"issueKey": "SH-123", "issueUrl": "https://jira.example.com/browse/SH-123", "rule_id": "description-steps", "field": "Description", "observed": "[ACME][T7][V1.1][Video]: Video freezes,2/2", "reason": "Steps are required.", "guidance": "Add steps."}}],
        "violationRowCount": 205, "violationPage": 1, "violationPageCount": 3,
        "aiReviewText": "Character-rule results were retained.",
        "exportPath": "", "canStart": True, "canConfirm": True, "canExport": False,
        }}
    viewState = Property("QVariantMap", lambda self: self._view, notify=changed)
    def setView(self, **changes):
        self._view.update(changes); self.changed.emit()
    @Slot(str)
    def startAudit(self, _text): pass
    @Slot()
    def confirmAudit(self): pass
    @Slot()
    def exportReport(self): pass
    @Slot()
    def previousViolationPage(self):
        self.setView(violationPage=max(1, self._view["violationPage"] - 1))
    @Slot()
    def nextViolationPage(self):
        self.setView(violationPage=min(self._view["violationPageCount"], self._view["violationPage"] + 1))
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, r"{tmp_path}")
app=QGuiApplication([]); app.setOrganizationName("Amlogic"); app.setApplicationName("SmartTest"); engine=QQmlApplicationEngine(); warnings=[]
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
jira=JiraAudit(); engine.rootContext().setContextProperty("JiraAuditBridge", jira)
auth=Auth(); engine.rootContext().setContextProperty("AuthBridge", auth)
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible: true; width: 900; height: 700; Loader {{ objectName: "workspaceLoader"; anchors.fill: parent; source: "qrc:/example/qml/component/jiraaudit/JiraAuditWorkspace.qml" }} }}')
app.processEvents()
window=engine.rootObjects()[0]
def find_by_object_name(name):
    pending=[window.contentItem()]
    while pending:
        item=pending.pop()
        if item.objectName()==name:
            return item
        pending.extend(item.children())
        if hasattr(item, "childItems"):
            pending.extend(item.childItems())
    return None
buttons=[window.findChild(QObject, name) for name in ("confirmAuditButton", "exportAuditButton", "showAuditExportButton")]
assert all(buttons)
page_buttons=[window.findChild(QObject, name) for name in ("previousViolationPageButton", "nextViolationPageButton")]
assert all(page_buttons)
progress=find_by_object_name("jiraAuditDeterminateProgress")
progress_fill=find_by_object_name("jiraAuditProgressFill")
assert progress and progress_fill, (progress, progress_fill)
print(*[button.property("disabled") for button in buttons])
print("progress", progress.property("value"), progress.property("visible"), abs(progress_fill.width()-progress_fill.parentItem().width()) < 0.5)
print("pages", *[button.property("disabled") for button in page_buttons])
jira.nextViolationPage(); app.processEvents()
print("page", jira._view["violationPage"], *[button.property("disabled") for button in page_buttons])
jira.setView(violationPage=3); app.processEvents()
print("page", jira._view["violationPage"], *[button.property("disabled") for button in page_buttons])
jira.setView(canConfirm=False, canExport=True); app.processEvents()
print(*[button.property("disabled") for button in buttons])
jira.setView(exportPath="C:/Users/test/Downloads/audit.xlsx"); app.processEvents()
print(*[button.property("disabled") for button in buttons])
audit_input=window.findChild(QObject, "jiraAuditInput")
audit_input.setProperty("text", "project = TV")
save_timer=window.findChild(QObject, "auditSaveTimer")
QMetaObject.invokeMethod(save_timer, "restart")
deadline=time.monotonic()+0.9
while time.monotonic()<deadline:
    app.processEvents(); time.sleep(0.01)
loader=window.findChild(QObject, "workspaceLoader")
loader.setProperty("active", False)
QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
app.processEvents()
saved=QSettings().value("users/alice/jiraAudit/auditInput", "")
loader.setProperty("active", True)
deadline=time.monotonic()+0.4
while time.monotonic()<deadline:
    app.processEvents(); time.sleep(0.01)
restored=window.findChild(QObject, "jiraAuditInput").property("text")
print("persist", saved, restored)
print(len(warnings), warnings)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "False True True" in result.stdout
    assert "progress 1.0 True True" in result.stdout
    assert "pages True False" in result.stdout
    assert "page 2 False False" in result.stdout
    assert "page 3 False True" in result.stdout
    assert "True False True" in result.stdout
    assert "True False False" in result.stdout
    assert "persist project = TV project = TV" in result.stdout
    assert "0 []" in result.stdout


def test_redmine_failed_login_view_qrc_loads_without_qml_warnings():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; import "qrc:/example/qml/component/redmine"; Window {{ visible: true; width: 800; height: 600; RedmineLoginView {{ anchors.fill: parent; state: "failed"; statusText: "failed" }} }}')
app.processEvents()
print(len(engine.rootObjects()), len(warnings), warnings)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "1 0 []" in result.stdout


def test_tool_fixed_text_is_finished_in_both_catalogs():
    required_contexts = {"ItemsOriginal", "T_Tool", "ToolBridge"}
    for filename in ("example_en_US.ts", "example_zh_CN.ts"):
        root = ET.parse(ROOT / "ui/example" / filename).getroot()
        contexts = {
            name: [context for context in root.findall("context") if context.findtext("name") == name]
            for name in required_contexts
        }
        assert all(contexts.values())
        for named_contexts in contexts.values():
            tool_messages = [
                message
                for context in named_contexts
                for message in context.findall("message")
                if "Tool" in (message.findtext("source") or "")
                or context.findtext("name") == "ToolBridge"
            ]
            assert tool_messages
            for message in tool_messages:
                translation = message.find("translation")
                assert translation is not None
                assert translation.get("type") != "unfinished"
                assert (translation.text or "").strip()


def test_tool_classification_strings_are_finished_in_both_catalogs():
    expected = {
        "example_en_US.ts": {
            "STB": "STB", "TV": "TV", "SmartHome": "SmartHome",
            "IPTV": "IPTV", "Wi-Fi": "Wi-Fi",
        },
        "example_zh_CN.ts": {
            "STB": "STB", "TV": "TV", "SmartHome": "智能家居",
            "IPTV": "IPTV", "Wi-Fi": "Wi-Fi",
        },
    }
    for filename, required in expected.items():
        root = ET.parse(ROOT / "ui/example" / filename).getroot()
        context = next(c for c in root.findall("context") if c.findtext("name") == "T_Tool")
        actual = {
            message.findtext("source"): message.findtext("translation")
            for message in context.findall("message")
        }
        for source, translation in required.items():
            assert actual.get(source) == translation


def test_fae_redmine_rosters_are_unique_additive_and_keep_unknown_default():
    from ui.example.bridge.AuthBridge import load_personnel, match_employee_profile
    personnel = load_personnel(PERSONNEL_PATH)
    from tool.SmartHome.redmine.overdue import load_redmine_people
    roster_a = {"daozai.ye", "xin.wang", "wanqiang.xiao", "defeng.zhai", "qiang.zhang", "zhengshuai.zhu", "long.qiu", "rongqi.wang", "yinlong.ban", "chongzhang.gong", "jeremy.wang", "junchao.li", "fei.zhang", "mingyu.lu", "yong.su", "heping.zhang", "qitao.tang", "chengzhuan.bao", "wendong.she", "zhigang.zou"}
    roster_b = {"zhijun.liu", "yiquan.huang", "yuanyuan.li", "chuanting.xu"}
    from ui.example.bridge.ToolBridge import amlogic_employees
    employees = [item for item in amlogic_employees(personnel) if item.get("account") in roster_a | roster_b]
    assert len(employees) == len(roster_a | roster_b) == 24
    assert {item["account"] for item in employees} == roster_a | roster_b
    for employee in employees:
        assert employee["account"] == employee["account"].lower() and "@" not in employee["account"]
        assert sum(item.get("product_line_id") == "SmartHome" for item in employee.get("assignments", [])) == 1
        smart_home = next(item for item in employee["assignments"] if item.get("product_line_id") == "SmartHome")
        assert smart_home["primary"] is (employee["account"] in roster_a)
    aml_names, departments = load_redmine_people(PERSONNEL_PATH)
    redmine_by_ldap = {item.get("ldap_account"): item for item in personnel["redmine"]["accounts"]["amlogic"]}
    assert {redmine_by_ldap[employee["account"]]["display_name"] for employee in employees} <= aml_names
    assert all(departments[redmine_by_ldap[employee["account"]]["display_name"].casefold()] == "amlogic-fae" for employee in employees)
    assert all(employee["organization"]["department"] == "FAE-HW" for employee in employees if employee["account"] in roster_b)
    qa = next(item for item in amlogic_employees(personnel) if item["account"] == "xiuyue.zhang")
    assert qa["organization"]["department"] == "FAE-QA" and qa["assignments"] == []
    assert match_employee_profile(personnel, "", username="missing.account") == {}


def test_smarthome_assignment_model_remains_additive():
    personnel = {"amlogic": {"departments": {"FAE-SW": {"employees": [{"account": "fae.user", "assignments": [{"product_line_id": "TV"}, {"product_line_id": "SmartHome", "primary": False}], "system_roles": ["user"]}]}}, "product_lines": [{"id": "TV"}, {"id": "SmartHome"}], "technical_centers": []}}
    assignments = personnel["amlogic"]["departments"]["FAE-SW"]["employees"][0]["assignments"]
    assert [item["product_line_id"] for item in assignments] == ["TV", "SmartHome"]


def test_identity_domains_and_subing_smarthome_access_are_explicit():
    personnel = json.loads(PERSONNEL_PATH.read_text(encoding="utf-8"))
    assert "employees" not in personnel
    departments = personnel["amlogic"]["departments"]
    assert set(departments) == {"FAE-QA", "FAE-SW", "FAE-HW"}
    assert {name: len(value["employees"]) for name, value in departments.items()} == {
        "FAE-QA": 75, "FAE-SW": 22, "FAE-HW": 4,
    }
    assert "product_lines" not in personnel and "technical_centers" not in personnel
    employee = next(item for item in departments["FAE-SW"]["employees"] if item["account"] == "subing.xu")
    assert "redmine" not in employee
    smart_home = next(item for item in employee["assignments"] if item["product_line_id"] == "SmartHome")
    assert smart_home["primary"] is False
    accounts = personnel["redmine"]["accounts"]
    assert set(accounts) == {"amlogic", "customer"}
    mappings = {item.get("ldap_account"): item for item in accounts["amlogic"]}
    assert mappings["subing.xu"]["display_name"] == "Subing Xu"
    assert mappings["xin.wang"]["display_name"] == "Xin Wang1-aml"
    assert mappings["qiang.zhang"]["display_name"] == "Qiang Zhang-aml"
    assert all("ldap_account" not in item or item["ldap_account"] for item in accounts["customer"])


def test_shared_issue_browser_exposes_quick_views_project_options_and_search_cancel():
    source = (ROOT / "ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml").read_text(encoding="utf-8")
    for contract in ("quickViews", "activeQuickViewId", "projectOptions", "projectsLoading", "projectsStatusText", "searchLoading", "searchCanCancel"):
        assert f"property " in source and contract in source
    assert "signal quickViewRequested" in source
    assert "signal cancelSearchRequested" in source
    assert 'text: "×"' in source
    assert "onClicked: root.cancelSearchRequested()" in source
    assert "disabled: root.searchLoading || root.projectsLoading || !root.projectsReady" in source


def test_confluence_audit_tool_exposes_collection_plan_and_xlsx_content_contracts():
    workspace = (
        ROOT
        / "ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml"
    ).read_text(encoding="utf-8")
    compact = " ".join(workspace.split())
    for name in (
            "confluenceAuditSourceLabel",
        "confluenceAuditYearFilter",
        "confluenceAuditSupportModeFilter",
        "confluenceAuditProjectStatusFilter",
        "confluenceAuditProductLineFilter",
        "confluenceAuditYearDropDown",
        "confluenceAuditSupportModeDropDown",
        "confluenceAuditProjectStatusDropDown",
        "confluenceAuditProductLineDropDown",
        "confluenceAuditApplyFilterButton",
        "confluenceAuditRefreshCollectionButton",
        "confluenceAuditProjectChecklist",
        "confluenceAuditEnableWeeklyPlanButton",
        "exportConfluenceAuditExcelButton",
        "openConfluenceAuditReportDirectoryButton",
    ):
        assert f'objectName: "{name}"' in workspace
    for text in (
        "Project collection",
        "Source",
        "Years",
        "Support modes",
        "Project statuses",
        "Product lines",
        "Refresh filter options",
        "Apply filters",
        "Select all",
        "Enable weekly plan",
        "Export Excel",
        "Open report directory",
    ):
        assert f'qsTr("{text}")' in workspace
    assert "ConfluenceAuditBridge.startAudit()" in workspace
    assert "ConfluenceAuditBridge.refreshCollection()" in workspace
    assert "ConfluenceAuditBridge.applyCollectionFilter()" in workspace
    assert "root.view.filterApplying" in workspace
    assert 'objectName: "confluenceAuditApplyFilterProgress"' in workspace
    assert 'objectName: "confluenceAuditLoginLauncher"' in workspace
    assert "target: AuthBridge" in workspace
    assert "function onRuntimeCredentialSupplyRequired()" in workspace
    assert "credentialSupply: AuthBridge.authenticated" in workspace
    assert "target: ConfluenceAuditBridge" not in workspace
    assert "filter_submit=" not in (ROOT / "ui/example/main.py").read_text(encoding="utf-8")
    assert "filter_submit=" not in (ROOT / "ui/example/tool_main.py").read_text(encoding="utf-8")
    assert "Component.onCompleted" in workspace
    assert "ConfluenceAuditBridge.refreshPlans()" not in workspace
    assert 'ConfluenceAuditBridge.toggleFilterValue( "years", modelData)' in compact
    assert 'ConfluenceAuditBridge.toggleFilterValue( "supportModes", modelData)' in compact
    assert "ConfluenceAuditBridge.toggleProject(modelData.projectIdentity)" in workspace
    assert "root.view.candidateSections" in workspace
    assert "sectionData.displayName" in workspace
    assert "ConfluenceAuditBridge.selectAllProjectsForLine(sectionData.key)" in workspace
    assert "ConfluenceAuditBridge.clearSelectedProjectsForLine(sectionData.key)" in workspace
    assert "ConfluenceAuditBridge.toggleProductLine(modelData.key)" in workspace
    assert workspace.index('objectName: "confluenceAuditProductLineFilter"') < workspace.index(
        'objectName: "confluenceAuditYearFilter"'
    )
    assert 'readonly property bool catalogBusy: root.view.catalogStatus === "first_loading"' in workspace
    assert '|| root.view.catalogStatus === "refreshing"' in workspace
    assert "FluProgressRing" in workspace
    assert "visible: root.catalogBusy" in workspace
    assert "disabled: root.catalogBusy || root.auditBusy" in workspace
    assert 'readonly property bool auditBusy: root.view.state === "discovering"' in workspace
    assert '|| root.view.state === "reviewing"' in workspace
    assert "visible: root.auditBusy" in workspace
    assert "ConfluenceAuditBridge.enableWeeklyPlan()" in workspace
    assert "ConfluenceAuditBridge.exportExcel()" in workspace
    assert "ConfluenceAuditBridge.openReportDirectory()" in workspace
    assert "root.view.plans" not in workspace
    assert 'qsTr("Configured collection")' not in workspace
    assert "function changedValues" not in workspace
    assert "function setFilterValue" not in workspace
    assert "function setProjectSelected" not in workspace
    assert "loadedPlanId" not in workspace
    assert "confluenceAuditHistory" not in workspace
    assert "selectHistory" not in workspace
    assert 'qsTr("History")' not in workspace
    assert "confluenceAuditCurrentStageFilter" not in workspace
    assert '"currentStages"' not in workspace
    assert workspace.count("FluDropDownButton") == 4
    assert 'qsTr("Export XLSX")' not in workspace
    jira_workspace = (
        ROOT / "ui/example/imports/example/qml/component/jiraaudit/JiraAuditWorkspace.qml"
    ).read_text(encoding="utf-8")
    assert 'qsTr("Export XLSX")' in jira_workspace
    assert "deletePlan" not in workspace
    assert 'qsTr("Delete")' not in workspace
    assert "ConfluenceAuditBridge" in (
        ROOT / "ui/example/main.py"
    ).read_text(encoding="utf-8")


def test_confluence_workspace_declares_responsive_candidate_grid_contract():
    workspace = (
        ROOT / "ui/example/imports/example/qml/component/confluenceaudit/"
        "ConfluenceAuditWorkspace.qml"
    ).read_text(encoding="utf-8")

    assert "id: simplePlanFrame" not in workspace
    assert "flickableDirection: Flickable.VerticalFlick" in workspace
    assert "contentWidth: width" in workspace
    assert "id: candidateGrid" in workspace
    assert "candidateColumnCount" in workspace
    assert "candidateVisibleRowCount" in workspace
    assert "width < 800 ? 1 : (width < 1200 ? 2 : 3)" in workspace
    assert "text: modelData.displayName || modelData.name" in workspace
    assert "modelData.projectId + \")\"" not in workspace
    assert "wrapMode: Text.Wrap" in workspace
    assert "confluenceAuditEnableWeeklyPlanButton" in workspace
    assert "ConfluenceAuditBridge.enableWeeklyPlan()" in workspace
    assert "id: candidateSectionList" in workspace
    assert "id: candidateSectionColumn" in workspace
    assert "id: candidateSectionGrid" in workspace
    assert "columns: 3" in workspace
    assert "ScrollBar.vertical: FluScrollBar" in workspace
    assert "candidateSectionColumn.implicitHeight" in workspace


def test_confluence_audit_workspace_runtime_events_and_wrapped_filters_are_accessible():
    probe = f'''
import sys, shiboken6
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, QPointF, Property, QMetaObject, Signal, Slot, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
class Bridge(QObject):
    changed = Signal()
    def __init__(self):
        super().__init__(); self.calls=[]
        many=[f"MODE-{{i}}" for i in range(18)]
        self._view={{
            "state":"idle", "statusText":"ready", "canStart":True, "canExport":False,
            "sourceLabel":"DOPL + SDPL Project Spaces",
            "filter":{{"years":[2025,2026],
                       "supportModes":many, "projectStatuses":[]}},
            "availableFilterValues":{{"years":[2025,2026], "supportModes":many,
                       "projectStatuses":["Active"]}},
            "candidateProjects":[
                {{"projectId":("M1" if i == 0 else f"M{{i+1}}"),
                  "projectIdentity":f"DOPL:{{i+1}}",
                  "name":f"Project {{i+1}}",
                  "displayName":(
                      "超长中文 English project name for responsive row layout "
                      f"candidate {{i+1}} with complete business title "
                      "and additional long suffix that must remain fully visible"),
                  "year":2026, "matchingYears":[2024,2025,2026]}}
                for i in range(40)
            ],
            "selectedProjectIds":[], "collectionSummary":{{"candidateCount":1}},
            "period":{{}}, "progress":{{}}, "summary":{{}}, "projects":[],
            "selectedProject":"", "findings":[]
        }}
    viewState=Property("QVariantMap",lambda self:self._view,notify=changed)
    def set_view(self, **changes):
        self._view={{**self._view, **changes}}; self.changed.emit()
    @Slot()
    def initializeCollection(self): self.calls.append(("initialize",))
    @Slot()
    def refreshCollection(self):
        self.calls.append(("refresh",))
        options={{**self._view["availableFilterValues"],
                 "supportModes":["A","B","C"]}}
        self.set_view(availableFilterValues=options, catalogStatus="updated")
    @Slot()
    def applyCollectionFilter(self): self.calls.append(("apply",))
    @Slot(str, str)
    @Slot(str, int)
    def toggleFilterValue(self, group, value):
        self.calls.append(("filter", group, value))
    @Slot(str)
    def toggleProject(self, value):
        self.calls.append(("project", value))
    @Slot()
    def selectAllProjects(self):
        self.calls.append(("select_all",)); self.set_view(selectedProjectIds=["M1"])
    @Slot()
    def clearSelectedProjects(self):
        self.calls.append(("clear_selected",)); self.set_view(selectedProjectIds=[])
    @Slot()
    def enableWeeklyPlan(self):
        self.calls.append(("enable_weekly",))
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]; bridge=Bridge()
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
engine.rootContext().setContextProperty("ConfluenceAuditBridge", bridge)
engine.rootContext().setContextProperty("AuthBridge", bridge)
FluentUI.registerTypes(engine)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible: true; width: 1500; height: 1000; Loader {{ anchors.fill: parent; source: "qrc:/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml" }} }}')
app.processEvents(); QTest.qWait(100); app.processEvents(); window=engine.rootObjects()[0]
def item(name):
    direct=window.findChild(QObject,name)
    if direct: return direct
    pending=[window.contentItem()]; seen=set()
    while pending:
        current=pending.pop()
        pointer=shiboken6.getCppPointer(current)[0]
        if pointer in seen: continue
        seen.add(pointer)
        if current.objectName()==name: return current
        pending.extend(current.children())
        if hasattr(current,"childItems"): pending.extend(current.childItems())
def click(control):
    point=control.mapToScene(QPointF(control.width()/2,control.height()/2))
    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,
                     QPoint(round(point.x()),round(point.y())))
    app.processEvents()
refresh=item("confluenceAuditRefreshCollectionButton")
controls={{name:item(name) for name in (
    "confluenceAuditYearDropDown", "confluenceAuditSupportModeDropDown",
    "confluenceAuditProjectStatusDropDown", "confluenceAuditApplyFilterButton",
    "confluenceAuditYearOption_2025", "confluenceAuditProjectOption_DOPL:1",
    "confluenceAuditSelectAllProjectsButton",
    "confluenceAuditClearSelectedProjectsButton",
    "confluenceAuditEnableWeeklyPlanButton")}}
assert refresh, (bool(refresh), warnings)
assert all(controls.values()), {{key:bool(value) for key,value in controls.items()}}
for key in ("confluenceAuditRefreshCollectionButton",):
    click(refresh)
assert item("confluenceAuditSupportModeOption_C")
controls["confluenceAuditYearOption_2025"].triggered.emit()
app.processEvents()
click(controls["confluenceAuditApplyFilterButton"])
click(controls["confluenceAuditProjectOption_DOPL:1"])
click(controls["confluenceAuditSelectAllProjectsButton"])
click(controls["confluenceAuditEnableWeeklyPlanButton"])
click(controls["confluenceAuditClearSelectedProjectsButton"])
widths=[controls[name].width() for name in (
    "confluenceAuditYearDropDown", "confluenceAuditSupportModeDropDown",
    "confluenceAuditProjectStatusDropDown")]
assert min(widths) > 180, widths
checklist=item("confluenceAuditProjectChecklist")
window.setWidth(520); app.processEvents(); QTest.qWait(50); app.processEvents()
narrowWidths=[controls[name].width() for name in (
    "confluenceAuditYearDropDown", "confluenceAuditSupportModeDropDown",
    "confluenceAuditProjectStatusDropDown")]
assert max(narrowWidths) <= 500, narrowWidths
assert controls["confluenceAuditApplyFilterButton"].property("visible") is True
assert checklist.width() <= 520, checklist.width()
candidateControls=[item("confluenceAuditProjectOption_" + f"DOPL:{{i+1}}")
                   for i in range(40)]
assert all(candidateControls), [bool(value) for value in candidateControls]
candidateRows=[item("confluenceAuditProjectRow_" + f"DOPL:{{i+1}}")
               for i in range(40)]
assert all(row.width() <= checklist.width() for row in candidateRows), [
    (row.width(), checklist.width()) for row in candidateRows]
assert max(row.height() for row in candidateRows) > 42, [
    (row.height(),
     item("confluenceAuditProjectName_" + f"DOPL:{{i+1}}").width(),
     item("confluenceAuditProjectName_" + f"DOPL:{{i+1}}").property("contentHeight"),
     item("confluenceAuditProjectName_" + f"DOPL:{{i+1}}").property("text"))
    for i,row in enumerate(candidateRows)]
def assert_grid(width, expected_columns, count):
    window.setWidth(width); app.processEvents(); QTest.qWait(50); app.processEvents()
    assert checklist.property("candidateColumnCount") == expected_columns
    expected_rows=(count + expected_columns - 1) // expected_columns
    assert checklist.property("candidateVisibleRowCount") == min(6, expected_rows)
    rows=[item("confluenceAuditProjectRow_" + f"DOPL:{{i+1}}")
          for i in range(count)]
    rects=[(row.x(), row.y(), row.width(), row.height()) for row in rows]
    assert all(x >= 0 and y >= 0 and x + w <= checklist.width() + 0.5
               for x,y,w,h in rects), rects
    for left_index,left in enumerate(rects):
        lx,ly,lw,lh=left
        for right in rects[left_index+1:]:
            rx,ry,rw,rh=right
            assert lx + lw <= rx or rx + rw <= lx or ly + lh <= ry or ry + rh <= ly
    assert checklist.property("contentWidth") <= checklist.width()
    if expected_rows > 6:
        assert checklist.property("contentHeight") > checklist.height()
    elif count:
        assert checklist.property("contentHeight") <= checklist.height() + 0.5

allCandidates=bridge._view["candidateProjects"]
for count in (0,1,6,18,40):
    bridge.set_view(candidateProjects=allCandidates[:count])
    app.processEvents(); QTest.qWait(30); app.processEvents()
    assert_grid(520,1,count)
    assert_grid(1000,2,count)
    assert_grid(1500,3,count)
print(bridge.calls, widths, narrowWidths, len(warnings), warnings)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    for expected in (
        "('refresh',)", "('filter', 'years', 2025)", "('project', 'DOPL:1')",
        "('apply',)",
        "('select_all',)", "('enable_weekly',)", "('clear_selected',)",
    ):
        assert expected in result.stdout
    assert " 0 []" in result.stdout


def test_confluence_audit_project_names_wrap_instead_of_truncating():
    workspace = (
        ROOT
        / "ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml"
    ).read_text(encoding="utf-8")
    assert 'objectName: "confluenceAuditProjectName"' in workspace
    assert "wrapMode: Text.WrapAnywhere" in workspace
    assert 'objectName: "confluenceAuditProjectStatus"' in workspace


def test_confluence_audit_workspace_labels_follow_up_projection_and_action_fields():
    workspace = (
        ROOT
        / "ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml"
    ).read_text(encoding="utf-8")
    for text in (
        'qsTr("Audit Period (Monday–Thursday)")',
        "root.shortDate(root.view.period.displayEnd)",
        'qsTr("Reviewed")',
        'qsTr("Follow-up")',
        'qsTr("Reason")',
        'qsTr("Open Confluence")',
    ):
        assert text in workspace
    assert "modelData.ruleId" in workspace


def test_confluence_audit_failure_card_has_text_explanation():
    workspace = (
        ROOT
        / "ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml"
    ).read_text(encoding="utf-8")
    assert 'objectName: "confluenceAuditExplanation"' in workspace
    assert "modelData.explanation" in workspace
    assert "evidenceUrl" not in workspace
