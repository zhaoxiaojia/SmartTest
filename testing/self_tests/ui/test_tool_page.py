from __future__ import annotations

import json
import gc
import os
import subprocess
import sys
import weakref
import xml.etree.ElementTree as ET
from pathlib import Path

from ui.example.bridge.ToolBridge import build_tool_groups, load_tool_access
from ui.example.bridge.ToolBridge import ToolBridge
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Property, Signal
from PySide6.QtQml import QQmlEngine


ROOT = Path(__file__).resolve().parents[3]
PERSONNEL_PATH = ROOT / "config" / "personnel.json"


class RuntimeAuth(QObject):
    authChanged = Signal()
    username = Property(str, lambda self: "chen.chen", notify=authChanged)


def test_tool_bridge_survives_runtime_context_registration_and_exposes_redmine():
    app = QCoreApplication.instance() or QCoreApplication([])
    engine = QQmlEngine()
    auth = RuntimeAuth()
    context = engine.rootContext()
    context.setContextProperty("ToolBridge", ToolBridge(ROOT, auth))
    gc.collect()

    bridge = context.contextProperty("ToolBridge")
    assert bridge is not None
    smart_home = next(group for group in bridge.groups if group["id"] == "SmartHome")
    assert smart_home["available"] is True
    assert smart_home["tools"][0]["id"] == "redmine"
    assert smart_home["tools"][0]["title"] == "redmine"


def test_production_context_ownership_survives_gc_and_tool_dialogs_are_warning_free():
    probe = f'''
import gc, sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, QPointF, Property, Signal, Slot, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.ToolBridge import ToolBridge
from example.context_registry import register_context_objects
class Auth(QObject):
    authChanged = Signal()
    username = Property(str, lambda self: "chao.li", notify=authChanged)
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
auth=Auth(); redmine=Redmine()
register_context_objects(engine, {{"AuthBridge": auth, "ToolBridge": ToolBridge(r"{ROOT}", auth), "RedmineBridge": redmine}})
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
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "redmine 1 3 0 []" in result.stdout


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


def run_tool_qml_interaction_probe(account: str, *, developer: bool = False) -> str:
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, QPointF, Property, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
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
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]; engine.warnings.connect(lambda rows: warnings.extend(rows))
auth=Auth(); tools=ToolBridge(r"{ROOT}", auth); redmine=Redmine()
if {developer!r}:
    next(employee for node in tools._personnel["amlogic"]["departments"].values() for employee in node["employees"] if employee["account"] == "{account}")["system_roles"] = ["Developer"]
engine.rootContext().setContextProperty("ToolBridge", tools); engine.rootContext().setContextProperty("RedmineBridge", redmine)
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


def test_tool_qml_runtime_does_not_expose_redmine_to_unauthorized_account():
    assert "True False None False 0 0" in run_tool_qml_interaction_probe("junjie.li")


def test_tool_qml_runtime_developer_can_open_redmine_independent_of_assignment():
    assert "True True redmine False 1 0" in run_tool_qml_interaction_probe(
        "junjie.li", developer=True
    )


def test_personnel_declares_product_line_and_technical_center_owners():
    payload = json.loads(PERSONNEL_PATH.read_text(encoding="utf-8"))

    assert {item["id"]: item["owner_account"] for item in payload["amlogic"]["product_lines"]} == {
        "STB": "junjie.li",
        "TV": "jianfan.ai",
        "SmartHome": "chen.chen",
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


def test_tool_groups_keep_fixed_layout_and_filter_child_tools_by_account():
    personnel = load_tool_access(PERSONNEL_PATH)

    expected_product_lines = {
        "junjie.li": "STB",
        "jianfan.ai": "TV",
        "chen.chen": "SmartHome",
        "lingling.yu": "IPTV",
    }
    for account, product_line in expected_product_lines.items():
        account_groups = build_tool_groups(personnel, account)
        assert [group["id"] for group in account_groups] == [
            "common", "STB", "TV", "SmartHome", "IPTV", "Wi-Fi"
        ]
        assert [group["available"] for group in account_groups[1:]] == [
            group["id"] == product_line for group in account_groups[1:]
        ]

    tv_groups = build_tool_groups(personnel, "jianfan.ai")
    assert tv_groups[0]["id"] == "common"
    assert tv_groups[0]["tools"] == []
    assert tv_groups[2]["available"] is True

    wifi_groups = build_tool_groups(personnel, "zijie.chen")
    assert wifi_groups[-1]["available"] is True
    assert wifi_groups[-1]["tools"] == []

    unknown_groups = build_tool_groups(personnel, "unknown.account")
    assert len(unknown_groups) == 6
    assert not any(group["available"] for group in unknown_groups[1:])


def test_developer_role_grants_every_tool_group_independent_of_assignments_and_casing():
    personnel = load_tool_access(PERSONNEL_PATH)
    personnel["amlogic"]["departments"]["FAE"]["employees"].extend(
        [
            {
                "account": "developer.zero",
                "assignments": [],
                "expertise_domains": [],
                "system_roles": ["Developer"],
            },
            {
                "account": "developer.one",
                "assignments": [{"product_line_id": "STB"}],
                "expertise_domains": [],
                "system_roles": ["dEvElOpEr"],
            },
        ]
    )

    for account in ("developer.zero", "developer.one"):
        groups = build_tool_groups(personnel, account)
        assert len(groups) == 6
        assert all(group["available"] for group in groups)
        assert next(group for group in groups if group["id"] == "SmartHome")["tools"] == [
            {"id": "redmine"}
        ]

    personnel["amlogic"]["technical_centers"][0]["active"] = False
    inactive_center_groups = build_tool_groups(personnel, "developer.zero")
    assert all(group["available"] for group in inactive_center_groups[:-1])
    assert inactive_center_groups[-1]["available"] is False


def test_configured_chao_li_developer_role_grants_all_active_tool_groups():
    personnel = load_tool_access(PERSONNEL_PATH)
    employee = next(item for node in personnel["amlogic"]["departments"].values() for item in node["employees"] if item["account"] == "chao.li")

    assert employee["system_roles"] == ["user", "developer"]
    groups = build_tool_groups(personnel, "chao.li")
    assert len(groups) == 6
    assert all(group["available"] for group in groups)
    assert next(group for group in groups if group["id"] == "SmartHome")["tools"] == [
        {"id": "redmine"}
    ]


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
    assert 'self.tr("Common Tools")' in (ROOT / "ui/example/bridge/ToolBridge.py").read_text(encoding="utf-8")
    assert 'qsTr("Custom Tools")' in page
    assert 'text: qsTr("Tools")' not in page
    assert "Layout.preferredWidth: 216" in page
    assert "model: ToolBridge.groups" in page
    assert "toolGroup: modelData" in page
    assert "headerText: toolGroup.title" in page
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


def test_runtime_root_is_created_before_tool_bridge_registration():
    source = (ROOT / "ui/example/main.py").read_text(encoding="utf-8")

    assert source.index("runtime_root = _runtime_root()") < source.index(
        '"ToolBridge": ToolBridge(runtime_root, auth_bridge)'
    )
    assert "register_context_objects(" in source
    assert '"runtime_root": str(runtime_root)' in source


def test_tool_bridge_logs_account_and_group_resolution_without_secrets(monkeypatch):
    messages = []
    monkeypatch.setattr(
        "ui.example.bridge.ToolBridge.smart_log",
        lambda message, *args, **kwargs: messages.append(message % args if args else message),
    )
    auth = RuntimeAuth()
    bridge = ToolBridge(ROOT, auth)

    groups = bridge.groups

    assert any("account=chen.chen" in message for message in messages)
    assert any("SmartHome:redmine" in message for message in messages)
    assert not any("password" in message.casefold() for message in messages)


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
        assert next(group for group in build_tool_groups(personnel, employee["account"]) if group["id"] == "SmartHome")["available"] is True
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
    assert [group["id"] for group in build_tool_groups(personnel, "missing.account") if group["available"]] == ["common"]


def test_smarthome_assignment_model_remains_additive():
    personnel = {"amlogic": {"departments": {"FAE": {"employees": [{"account": "fae.user", "assignments": [{"product_line_id": "TV"}, {"product_line_id": "SmartHome", "primary": False}], "system_roles": ["user"]}]}}, "product_lines": [{"id": "TV"}, {"id": "SmartHome"}], "technical_centers": []}}
    available = {group["id"] for group in build_tool_groups(personnel, "fae.user") if group["available"]}
    assert available == {"common", "TV", "SmartHome"}


def test_identity_domains_and_subing_smarthome_access_are_explicit():
    personnel = json.loads(PERSONNEL_PATH.read_text(encoding="utf-8"))
    assert "employees" not in personnel
    departments = personnel["amlogic"]["departments"]
    assert set(departments) == {"FAE-QA", "FAE", "FAE-HW"}
    assert {name: len(value["employees"]) for name, value in departments.items()} == {
        "FAE-QA": 75, "FAE": 21, "FAE-HW": 4,
    }
    assert "product_lines" not in personnel and "technical_centers" not in personnel
    employee = next(item for item in departments["FAE"]["employees"] if item["account"] == "subing.xu")
    assert "redmine" not in employee
    smart_home = next(item for item in employee["assignments"] if item["product_line_id"] == "SmartHome")
    assert smart_home["primary"] is False
    from ui.example.bridge.ToolBridge import load_tool_access
    assert next(group for group in build_tool_groups(load_tool_access(PERSONNEL_PATH), "subing.xu") if group["id"] == "SmartHome")["available"]
    accounts = personnel["redmine"]["accounts"]
    assert set(accounts) == {"amlogic", "customer"}
    mappings = {item.get("ldap_account"): item for item in accounts["amlogic"]}
    assert mappings["subing.xu"]["display_name"] == "Subing Xu"
    assert mappings["xin.wang"]["display_name"] == "Xin Wang1-aml"
    assert mappings["qiang.zhang"]["display_name"] == "Qiang Zhang-aml"
    assert all("ldap_account" not in item or item["ldap_account"] for item in accounts["customer"])


def test_tool_page_invalidates_redmine_selection_when_group_becomes_unavailable():
    source = (ROOT / "ui/example/imports/example/qml/page/T_Tool.qml").read_text(encoding="utf-8")
    assert "function ensureSelectedToolAvailable()" in source
    assert "if (!selectedGroup.available)" in source
    assert "onSelectedGroupChanged: ensureSelectedToolAvailable()" in source


def test_shared_issue_browser_exposes_quick_views_project_options_and_search_cancel():
    source = (ROOT / "ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml").read_text(encoding="utf-8")
    for contract in ("quickViews", "activeQuickViewId", "projectOptions", "projectsLoading", "projectsStatusText", "searchLoading", "searchCanCancel"):
        assert f"property " in source and contract in source
    assert "signal quickViewRequested" in source
    assert "signal cancelSearchRequested" in source
    assert 'text: "×"' in source
    assert "onClicked: root.cancelSearchRequested()" in source
    assert "disabled: root.searchLoading || root.projectsLoading || !root.projectsReady" in source
