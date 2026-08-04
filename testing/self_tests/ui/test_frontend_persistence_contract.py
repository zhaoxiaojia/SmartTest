from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QSettings

from ui import page_state_migration
from ui.page_state_migration import migrate_frontend_state


ROOT = Path(__file__).resolve().parents[3]
QML = ROOT / "ui/example/imports/example/qml"


def test_responsive_metrics_and_login_scroll_react_at_runtime():
    probe = f"""
import os, sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.AuthBridge import AuthBridge
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
engine.rootContext().setContextProperty("AuthBridge", AuthBridge(project_root=r"{ROOT}"))
FluentUI.registerTypes(engine); engine.load(QUrl("qrc:/example/qml/window/LoginWindow.qml")); app.processEvents()
window=engine.rootObjects()[0]; window.setWidth(360); window.setHeight(300); app.processEvents()
scroll=window.findChild(QObject,"loginScroll"); content=window.findChild(QObject,"loginContent")
size=QQmlExpression(engine.rootContext(),window,"fittedSizeForGeometry(Qt.rect(1920,0,500,400), true)").evaluate()[0]
print(bool(scroll), scroll.property("contentHeight") >= scroll.property("height"),
      scroll.property("contentWidth") <= scroll.property("width"),
      content.property("width") <= scroll.property("width"), size.width(), size.height(), len(warnings))
"""
    result = subprocess.run(
        [str(ROOT / ".venv/Scripts/python.exe"), "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), capture_output=True,
        text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "True True True True 460.0 368.0 0" in result.stdout


def test_actual_qml_layout_families_resize_at_supported_widths():
    probe = f"""
import json, sys
from pathlib import Path
sys.path.insert(0, r"{ROOT / 'ui'}"); sys.path.insert(0, r"{ROOT}")
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.HomeBridge import HomeBridge
from example.bridge.RunBridge import RunBridge
from example.bridge.DebugBridge import DebugBridge
from example.bridge.TestPageBridge import TestPageBridge
from example import tool_main
from example.context_registry import register_context_objects
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
objects=tool_main.create_context_objects(engine)
objects.update({{"HomeBridge":HomeBridge(),"RunBridge":RunBridge(Path(r"{ROOT}")),"DebugBridge":DebugBridge(Path(r"{ROOT}")),"TestPageBridge":TestPageBridge(Path(r"{ROOT}"))}})
register_context_objects(engine,objects); FluentUI.registerTypes(engine)
widths=[960,1024,1366,1920]
def probe(source, prop):
 c=QQmlComponent(engine,QUrl(source)); item=c.create(); assert item is not None,[x.toString() for x in c.errors()]
 rows=[]
 for width in widths:
  item.setWidth(width); item.setHeight(640); app.processEvents(); rows.append(item.property(prop))
 item.deleteLater(); app.processEvents(); return rows
result={{
 "cards":probe("qrc:/example/qml/page/T_Home.qml","responsiveMetricColumns"),
 "testconfig":probe("qrc:/example/qml/page/T_TestConfig.qml","responsiveOrientation"),
 "master":probe("qrc:/example/qml/component/issue/JiraIssueBrowserLayout.qml","responsiveOrientation"),
 "log":probe("qrc:/example/qml/page/T_Run.qml","responsiveHeaderColumns"),
 "panels":probe("qrc:/example/qml/page/T_Debug.qml","responsivePanelColumns"),
 "audit":probe("qrc:/example/qml/component/jiraaudit/JiraAuditWorkspace.qml","responsiveLayout"),
 "dialog":probe("qrc:/example/qml/component/issue/JiraCreateBatchDialog.qml","responsivePanelWidth")}}
objects["RedmineBridge"].close(); print(json.dumps(result),len(warnings),warnings)
"""
    result = subprocess.run(
        [str(ROOT / ".venv/Scripts/python.exe"), "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), capture_output=True,
        text=True, timeout=40,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout.splitlines()[-1].rsplit(" ", 2)[0])
    assert payload == {
        "cards": [2, 2, 4, 4],
        "testconfig": [1, 1, 1, 1],
        "master": [1, 1, 1, 1],
        "log": [5, 5, 5, 5],
        "panels": [2, 2, 2, 2],
        "audit": [1, 1, 2, 2],
        "dialog": [864.0, 921.6, 1229.4, 1728.0],
    }
    assert " 0 []" in result.stdout.splitlines()[-1]


def test_adaptive_window_selects_saved_screen_and_clamps_oversized_geometry():
    probe = f"""
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
app=QGuiApplication([]); engine=QQmlApplicationEngine(); FluentUI.registerTypes(engine)
engine.loadData(b'''import QtQuick 2.15; import QtQuick.Window 2.15; import "qrc:/example/qml/global";
Window {{ id:w; width:1000; height:700; visible:false
 AdaptiveWindow {{ id:a; target:w; availableRatio:0.8 }}
 property rect primary: a.selectGeometry([Qt.rect(0,0,1920,1080),Qt.rect(1920,0,2560,1440)],100,100,900,600,Qt.rect(0,0,1920,1080))
 property rect external: a.selectGeometry([Qt.rect(0,0,1920,1080),Qt.rect(1920,0,2560,1440)],2100,100,1200,800,Qt.rect(0,0,1920,1080))
 property rect disconnected: a.selectGeometry([Qt.rect(0,0,1920,1080)],2500,100,1200,800,Qt.rect(0,0,1920,1080))
 property size oversized: a.boundedSize(4000,3000,Qt.rect(1920,0,1000,600))
}}''')
root=engine.rootObjects()[0]
print(root.property("primary").x(), root.property("external").x(),
      root.property("disconnected").x(), root.property("oversized").width(),
      root.property("oversized").height())
"""
    result = subprocess.run(
        [str(ROOT / ".venv/Scripts/python.exe"), "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), capture_output=True,
        text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "0.0 1920.0 0.0 800.0 480.0" in result.stdout


class MemorySettings:
    def __init__(
        self, values=None, *, fail_sync=False, corrupt_readback=False,
        fail_rollback=False, bool_as_string=False, list_as_string=False,
    ):
        self.values = dict(values or {})
        self.fail_sync = fail_sync
        self.corrupt_readback = corrupt_readback
        self.fail_rollback = fail_rollback
        self.bool_as_string = bool_as_string
        self.list_as_string = list_as_string
        self.synced = False
        self.sync_calls = 0

    def contains(self, key):
        return key in self.values

    def value(self, key):
        value = self.values.get(key)
        if self.corrupt_readback and self.synced and key.endswith("/darkMode"):
            self.corrupt_readback = False
            return -1
        if self.bool_as_string and self.synced and type(value) is bool:
            return "true" if value else "false"
        if self.list_as_string and self.synced and isinstance(value, list):
            return ",".join(map(str, value))
        return value

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        self.sync_calls += 1
        if self.fail_rollback and self.sync_calls >= 2:
            raise OSError("rollback sync failed")
        self.synced = True

    def status(self):
        if self.fail_sync:
            self.fail_sync = False
            return QSettings.Status.AccessError
        return QSettings.Status.NoError


def _global_fixture(path):
    path.write_bytes(b'{"version":1,"users":{"global":{"global":{"darkMode":{"type":"int","value":2},"language":{"type":"string","value":"zh_CN"}}}}}')


def test_explicit_qml_schemas_have_stable_business_keys():
    jira = (QML / "state/JiraPageState.qml").read_text(encoding="utf-8")
    assert 'category: "users/" + account + "/jira"' in jira
    assert "selectedBoardId" in jira and "selectedTimeframeId" in jira
    assert "currentIndex" not in jira and "objectName" not in jira


def test_user_settings_are_lifecycle_guarded_and_logout_clears_ui():
    jira = (QML / "page/T_Jira.qml").read_text(encoding="utf-8")
    assert "active: AuthBridge.authenticated" in jira
    assert 'pageStateAccount || ""' in jira
    assert "onActiveChanged" in jira and "clearFilterState()" in jira
    assert "users/anonymous" not in jira and "FrontendStateBridge" not in jira


def test_legacy_migration_covers_users_and_converts_indices_to_ids(tmp_path):
    source = tmp_path / "frontend_state.json"
    source.write_text(json.dumps({"version": 1, "users": {
        "global": {"global": {
            "darkMode": {"type": "int", "value": 2},
            "windowState": {"type": "object", "value": {"tourShown": True}},
        }},
        "Alice@example.com": {"jira": {"filterState": {"type": "object", "value": {
            "boardIndex": 1, "timeframeIndex": 2, "projects": ["tv"],
        }}}},
        "BOB": {"jiraAudit": {"jiraAuditInput": {"type": "string", "value": "project = TV"}}},
    }}), encoding="utf-8")
    settings = QSettings(str(tmp_path / "state.ini"), QSettings.Format.IniFormat)
    report = migrate_frontend_state(source, settings)
    assert report.deleted and report.users == 2 and not source.exists()
    assert settings.value("users/alice/jira/selectedBoardId") == "ready_for_test"
    assert settings.value("users/alice/jira/selectedTimeframeId") == "last_90_days"
    assert settings.value("users/bob/jiraAudit/auditInput") == "project = TV"


def test_unknown_scope_preserves_legacy_bytes(tmp_path):
    source = tmp_path / "frontend_state.json"
    original = b'{"version":1,"users":{"alice":{"unknown":{"x":{"type":"string","value":"x"}}}}}'
    source.write_bytes(original)
    report = migrate_frontend_state(source, QSettings(str(tmp_path / "state.ini"), QSettings.Format.IniFormat))
    assert report.attempted and report.status == "failed"
    assert report.failure_reason == "transform_failed"
    assert not report.deleted and source.read_bytes() == original


def test_unmappable_index_preserves_legacy_bytes(tmp_path):
    source = tmp_path / "frontend_state.json"
    original = json.dumps({"version": 1, "users": {"alice": {"jira": {"filterState": {
        "type": "object", "value": {"boardIndex": 99},
    }}}}}).encode()
    source.write_bytes(original)
    report = migrate_frontend_state(source, QSettings(str(tmp_path / "state.ini"), QSettings.Format.IniFormat))
    assert not report.deleted and source.read_bytes() == original


def test_production_migration_covers_both_application_namespaces_before_delete(tmp_path, monkeypatch):
    source = tmp_path / "frontend_state.json"
    _global_fixture(source)
    desktop = QSettings(str(tmp_path / "SmartTest.ini"), QSettings.Format.IniFormat)
    tool = QSettings(str(tmp_path / "SmartTestTool.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(page_state_migration, "_production_targets", lambda: (desktop, tool))
    report = migrate_frontend_state(source)
    assert report.deleted and report.verified == 4 and not source.exists()
    for target in (desktop, tool):
        assert target.value("global/application/darkMode") == 2
        assert target.value("global/application/language") == "zh_CN"


def test_sync_failure_rolls_back_all_targets_and_preserves_source(tmp_path):
    source = tmp_path / "frontend_state.json"
    _global_fixture(source)
    original = source.read_bytes()
    existing = {"global/application/darkMode": 1}
    desktop = MemorySettings(existing)
    tool = MemorySettings(existing, fail_sync=True)
    report = migrate_frontend_state(source, settings_targets=(desktop, tool))
    assert not report.deleted and source.read_bytes() == original
    assert desktop.values == existing and tool.values == existing


def test_readback_failure_restores_preexisting_values_and_removes_new_keys(tmp_path):
    source = tmp_path / "frontend_state.json"
    _global_fixture(source)
    original = source.read_bytes()
    existing = {"global/application/darkMode": 0}
    target = MemorySettings(existing, corrupt_readback=True)
    report = migrate_frontend_state(source, settings_targets=(target,))
    assert not report.deleted and source.read_bytes() == original
    assert target.values == existing


def test_no_source_is_distinct_from_attempted_failure(tmp_path):
    report = migrate_frontend_state(tmp_path / "missing.json", settings_targets=(MemorySettings(),))
    assert not report.attempted
    assert report.status == "not_needed" and report.failure_reason == ""


def test_failure_log_contains_only_fixed_status_and_counts(tmp_path, monkeypatch):
    source = tmp_path / "frontend_state.json"
    secret_value = "do-not-log-this-value"
    source.write_text(secret_value, encoding="utf-8")
    records = []
    monkeypatch.setattr(page_state_migration, "smart_log", lambda message, **kwargs: records.append((message, kwargs)))
    report = migrate_frontend_state(source, settings_targets=(MemorySettings(),))
    rendered = repr(records)
    assert report.failure_reason == "parse_failed"
    assert records and secret_value not in rendered
    assert "parse_failed" in rendered and "failed" in rendered


def test_rollback_failure_has_distinct_status_and_preserves_source(tmp_path):
    source = tmp_path / "frontend_state.json"
    _global_fixture(source)
    original = source.read_bytes()
    target = MemorySettings(corrupt_readback=True, fail_rollback=True)
    report = migrate_frontend_state(source, settings_targets=(target,))
    assert report.failure_reason == "rollback_failed"
    assert report.rollback_clean is False
    assert source.read_bytes() == original


def test_anonymous_legacy_state_is_not_written(tmp_path):
    source = tmp_path / "frontend_state.json"
    source.write_text(json.dumps({"version": 1, "users": {"anonymous": {"jiraAudit": {
        "jiraAuditInput": {"type": "string", "value": "project = SECRET"},
    }}}}), encoding="utf-8")
    target = MemorySettings()
    report = migrate_frontend_state(source, settings_targets=(target,))
    assert report.deleted and report.skipped == 1
    assert target.values == {}
    assert not any(key.startswith("users/anonymous/") for key in target.values)


def test_windows_bool_string_readback_verifies_tour_shown_migration(tmp_path):
    source = tmp_path / "frontend_state.json"
    source.write_text(json.dumps({"version": 1, "users": {"global": {"global": {
        "windowState": {"type": "object", "value": {"tourShown": True}},
    }}}}), encoding="utf-8")
    target = MemorySettings(bool_as_string=True)

    report = migrate_frontend_state(source, settings_targets=(target,))

    assert report.status == "success" and report.deleted
    assert target.values["global/window/tourShown"] is True
    assert not source.exists()


def test_qt_bool_compatibility_does_not_weaken_list_verification(tmp_path):
    source = tmp_path / "frontend_state.json"
    original = json.dumps({"version": 1, "users": {"alice": {"jira": {"filterState": {
        "type": "object", "value": {"projects": ["tv", "ott"]},
    }}}}}).encode()
    source.write_bytes(original)
    target = MemorySettings(list_as_string=True)

    report = migrate_frontend_state(source, settings_targets=(target,))

    assert report.failure_reason == "readback_failed"
    assert source.read_bytes() == original
    assert target.values == {}


def test_main_window_lazy_load_reads_the_persisted_tour_owner_directly():
    source = (QML / "window/MainWindow.qml").read_text(encoding="utf-8")

    assert "property bool tourShown" not in source
    assert "if (lazyLoaded && !windowState.tourShown)" in source
    assert "windowState.tourShown = true" in source
    assert "tourShown = windowState.tourShown" not in source
