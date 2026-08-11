import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ISSUE_ROOT = ROOT / "ui/example/imports/example/qml/component/issue"
BROWSER_QML = ISSUE_ROOT / "JiraIssueBrowserLayout.qml"
FIELD_QML = ISSUE_ROOT / "JiraCreateField.qml"
CARD_QML = ISSUE_ROOT / "JiraCreateDraftCard.qml"
BATCH_QML = ISSUE_ROOT / "JiraCreateBatchDialog.qml"
MULTI_PICKER_QML = ISSUE_ROOT / "JiraOptionMultiPicker.qml"
WORKSPACE_QML = ROOT / "ui/example/imports/example/qml/component/redmine/RedmineWorkspace.qml"
BRIDGE_ATTACHMENT_WARNING_SOURCES = {
    "Attachment %1 is %2 bytes; Jira limit is %3 bytes.",
    "Jira attachments are disabled for %1.",
    "Attachment source URL is unavailable for %1.",
    "Attachment download failed for %1 (HTTP %2).",
    "Attachment download failed for %1: %2",
    "Attachment source is invalid for %1.",
    "Jira already has %1 with a different size.",
    "Could not check Jira attachments for %1: %2",
    "Attachment upload failed for %1: %2",
    "Attachment upload was cancelled for %1.",
    "Attachment downloader is unavailable for %1.",
    "Jira attachment synchronization failed for %1: %2",
    "Temporary attachment cleanup failed: %1",
}


def test_issue_list_clone_mode_and_batch_dialog_contract():
    browser = BROWSER_QML.read_text(encoding="utf-8")
    dialog = BATCH_QML.read_text(encoding="utf-8")
    assert "cloneSelectionMode" in browser and "cloneSelectable" in browser
    assert 'modelData.cloneStatus !== "cloned"' in browser
    assert "Repeater" in dialog and "cloneDrafts" in dialog
    assert "submitCloneBatch" in dialog and "updateCloneDraft" in dialog
    browser = BROWSER_QML.read_text(encoding="utf-8")
    assert 'placeholderText: qsTr("Subject")' in browser
    assert 'activeQuickViewId === "watched"' in browser
    assert "watchedIssueIdsSaved" in browser


def test_schema_controls_are_rendered_without_business_mapping_or_payload():
    field = FIELD_QML.read_text(encoding="utf-8")
    card = CARD_QML.read_text(encoding="utf-8")
    for control in ("text", "multiline", "single", "multi", "cascade", "user"):
        assert f'"{control}"' in field
    assert "field.control" in field
    assert "field.options" in field
    assert "valueChanged" in field
    assert "fieldId" in card and "issueId" in card
    for forbidden in ("customfield_", "CreateIssueRequest", "extra_fields", "fields: {"):
        assert forbidden not in field + card
    assert "FluCheckBox" not in field
    assert "toggledValues" not in field and "containsValue" not in field
    assert "FluAutoSuggestBox" in field


def test_clone_card_keeps_created_key_visible_with_attachment_warning():
    card = CARD_QML.read_text(encoding="utf-8")
    assert 'root.draft.state === "created"' in card
    assert "root.draft.attachmentWarnings" in card
    assert "modelData.attachmentWarningText" in card
    assert "reasonCode" not in card
    assert "function attachmentWarningText" not in card
    assert "FluTheme.dark ?" in card
    assert 'color: "#B8860B"' not in card


def test_multi_fields_have_one_bounded_schema_option_picker_owner():
    field = FIELD_QML.read_text(encoding="utf-8")
    picker = MULTI_PICKER_QML.read_text(encoding="utf-8")
    assert "JiraOptionMultiPicker" in field
    assert "id: multiEditor" not in field
    assert "Flow {" not in field
    assert field.count("FluAutoSuggestBox") == 1  # Jira user lookup only
    assert "FluAutoSuggestBox" not in picker and "FluTextBox" not in picker
    assert "model: root.options" in picker
    assert "clip: true" in picker
    assert "Layout.preferredHeight: Math.min(200" in picker
    assert "visible: root.expanded" in picker


def test_batch_uses_full_width_horizontal_draft_cards():
    dialog = BATCH_QML.read_text(encoding="utf-8")
    assert "RowLayout" in dialog
    assert "draftCardWidth" in dialog
    assert "draftScroll.availableWidth" in dialog
    assert "Layout.alignment: Qt.AlignTop" in dialog
    assert "1040" not in dialog
    assert "Math.max(240, (draftScroll.availableWidth - 12) / 2)" in dialog


def test_create_field_uses_native_left_label_right_control_rows():
    field = FIELD_QML.read_text(encoding="utf-8")
    card = CARD_QML.read_text(encoding="utf-8")
    assert "property real labelColumnWidth" in field
    assert "id: fieldRow" in field
    assert "Layout.preferredWidth: root.labelColumnWidth" in field
    assert "Layout.fillWidth: true" in field
    assert "labelColumnWidth: root.labelColumnWidth" in card
    cascade = field[field.index("id: cascadeEditor"):field.index("id: userEditor")]
    assert cascade.count("Layout.fillWidth: true") == 2
    assert "childrenFor(root.field.options, parent.parentValue)" in cascade
    assert "Channel of Reporter" not in cascade and '"None"' not in cascade
    assert "visible: root.hasVisibleLabel" in field
    assert "active: root.hasVisibleLabel" in field


def test_user_editor_accepts_account_identity_but_rejects_display_name():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
app=QGuiApplication([]); engine=QQmlApplicationEngine()
FluentUI.registerTypes(engine)
engine.loadData(b"""import QtQuick 2.15; import QtQuick.Window 2.15; import "file:///{ISSUE_ROOT.as_posix()}"
Window {{ id: root; visible: true
    property string identities: ""
    JiraCreateField {{
        id: editor
        field: ({{fieldId: "coworker", name: "FAE Coworker", control: "user",
            options: [{{value: "fred.chen", label: "Fred Chen"}},
                      {{value: "single.name", label: "Fred"}}],
            value: "", error: ""}})
        Component.onCompleted: root.identities = [
            userAccountInput(field.options, "fred.chen"),
            userAccountInput(field.options, "Fred Chen"),
            userAccountInput(field.options, "Fred"),
            userAccountInput(field.options, "manual.account")
        ].join("|")
    }}
}}""")
app.processEvents()
print(engine.rootObjects()[0].property("identities"))
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == "fred.chen|||manual.account"


def test_auto_suggest_async_items_refresh_and_click_returns_account_value():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
app=QGuiApplication([]); engine=QQmlApplicationEngine()
FluentUI.registerTypes(engine)
engine.loadData(b"""import QtQuick 2.15; import QtQuick.Window 2.15; import FluentUI 1.0
Window {{ id: root; visible: true; width: 400; height: 240
    property string selectedAccount: ""
    FluAutoSuggestBox {{
        objectName: "asyncUserPicker"; x: 20; y: 20; width: 300
        items: []
        onItemClicked: data => root.selectedAccount = data.value || ""
    }}
}}""")
app.processEvents()
QTest.qWait(100)
app.processEvents()
window=engine.rootObjects()[0]
picker=window.findChild(QObject, "asyncUserPicker")
picker.setProperty("text", "fr")
app.processEvents()
picker.setProperty("items", [
    {{"title": "Fred Chen", "value": "fred.chen"}},
    {{"title": "Freddy Zhang", "value": "freddy.zhang"}},
])
app.processEvents()
QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(100, 75))
app.processEvents()
print(window.property("selectedAccount"))
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == "fred.chen"


def test_narrow_field_patch_keeps_unrelated_editor_instance():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
app=QGuiApplication([]); engine=QQmlApplicationEngine()
FluentUI.registerTypes(engine)
engine.loadData(b"""import QtQuick 2.15; import QtQuick.Window 2.15; import "file:///{ISSUE_ROOT.as_posix()}"
Window {{ visible: true; width: 900; height: 600
    JiraCreateDraftCard {{
        id: card
        objectName: "draftCard"
        anchors.fill: parent
        Component.onCompleted: draft = ({{issueId: "1", sourceUrl: "", state: "editing",
            fields: [
                {{fieldId: "summary", name: "Summary", required: true, control: "text", options: [], value: "before", error: ""}},
                {{fieldId: "priority", name: "Priority", required: false, control: "single",
                  options: [{{value: "1", label: "P1"}}, {{value: "2", label: "P2"}}], value: "1", error: ""}}
            ], errors: [], attachmentWarnings: [], error: ""}})
    }}
}}""")
app.processEvents()
QTest.qWait(100)
app.processEvents()
window=engine.rootObjects()[0]
card=window.findChild(QObject, "draftCard")
summary_editor_before=card.fieldEditor("summary")
priority_editor_before=card.fieldEditor("priority")
assert summary_editor_before is not None and priority_editor_before is not None
updated=card.updateField({{
    "fieldId": "priority", "name": "Priority", "required": False, "control": "single",
    "options": [{{"value": "1", "label": "P1"}}, {{"value": "2", "label": "P2"}}],
    "value": "2", "error": ""
}})
app.processEvents()
summary_editor_after=card.fieldEditor("summary")
priority_editor_after=card.fieldEditor("priority")
print(updated, summary_editor_before == summary_editor_after, priority_editor_before == priority_editor_after)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == "True True True"


def test_clone_card_renders_reporter_assignee_manager_in_projected_order():
    probe = f"""
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
app=QGuiApplication([]); engine=QQmlApplicationEngine(); FluentUI.registerTypes(engine)
engine.loadData(b'''import QtQuick 2.15; import QtQuick.Window 2.15; import "file:///{ISSUE_ROOT.as_posix()}";
Window {{ visible:true; width:800; height:600
 JiraCreateDraftCard {{ id:card; objectName:"peopleOrderCard"; anchors.fill:parent
  draft: ({{issueId:"1", state:"editing", fields:[
   {{fieldId:"reporter",name:"Reporter",control:"user",required:true,value:"alice",options:[],error:""}},
   {{fieldId:"assignee",name:"Assignee",control:"user",required:false,value:"bob",options:[],error:""}},
   {{fieldId:"manager",name:"Manager",control:"user",required:true,value:"fred",options:[],error:""}}
  ]}})
 }}
}}'''); app.processEvents(); QTest.qWait(100); app.processEvents()
window=engine.rootObjects()[0]
def item(name):
 pending=[window.contentItem()]; seen=set()
 while pending:
  current=pending.pop()
  if id(current) in seen: continue
  seen.add(id(current))
  if current.objectName()==name: return current
  pending.extend(current.children())
  if hasattr(current,"childItems"): pending.extend(current.childItems())
editors=[item("jiraCreateField_" + name) for name in ("reporter","assignee","manager")]
print(all(editors), [editor.y() for editor in editors])
"""
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    marker, positions = result.stdout.strip().split(" ", 1)
    assert marker == "True"
    assert eval(positions) == sorted(eval(positions))


def test_combo_popup_limits_long_model_and_first_option_clicks():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
app=QGuiApplication([]); engine=QQmlApplicationEngine()
FluentUI.registerTypes(engine)
engine.loadData(b"""import QtQuick 2.15; import QtQuick.Window 2.15; import FluentUI 1.0
Window {{ id: root; visible: true; width: 420; height: 640
    property real openedHeight: 0
    property string selectedValue: ""
    ListModel {{ id: rowsModel }}
    FluComboBox {{
        id: combo; objectName: "longCombo"; x: 20; y: 20; width: 300
        popupMaximumVisibleItems: 8
        textRole: "label"; valueRole: "value"
        model: rowsModel
        popup.onOpened: {{
            root.openedHeight = popup.height
        }}
        onActivated: root.selectedValue = currentValue
        Component.onCompleted: {{
            var rows = []
            for (var i = 0; i < 40; ++i)
                rows.push({{
                    value: i === 0 ? "14747" : String(i),
                    label: i === 0 ? "Android 15" : "Option " + i
                }})
            for (var j = 0; j < rows.length; ++j)
                rowsModel.append(rows[j])
        }}
    }}
        Timer {{ interval: 10; running: true; onTriggered: {{
            combo.popup.contentItem.forceLayout()
            root.openedHeight = combo.popup.height
            combo.currentIndex = 0
            combo.activated(0)
        }} }}
}}""")
app.processEvents()
window=engine.rootObjects()[0]
QTest.qWait(30)
app.processEvents()
print(window.property("openedHeight"), window.property("selectedValue"))
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    height, value = result.stdout.strip().split()
    assert 200 <= float(height) <= 360
    assert value == "14747"


def test_workspace_connects_selection_and_batch_actions_to_bridge():
    workspace = WORKSPACE_QML.read_text(encoding="utf-8")
    for slot in (
        "beginCloneSelection", "toggleCloneSelection", "cancelCloneSelection",
        "prepareCloneDrafts", "updateCloneDraft", "submitCloneBatch",
        "retryFailedClones", "closeCloneBatch", "searchCloneUsers",
    ):
        assert f"RedmineBridge.{slot}" in workspace


def test_workspace_loads_independent_batch_editor_only_for_active_batch():
    workspace = WORKSPACE_QML.read_text(encoding="utf-8")
    assert "Loader" in workspace
    assert 'source: active ? "../issue/JiraCreateBatchDialog.qml" : ""' in workspace
    assert '"prepare_failed"' in workspace
    batch = BATCH_QML.read_text(encoding="utf-8")
    assert "retryPrepareCloneDrafts" in batch
    assert 'visible: root.batchState === "editing" || root.batchState === "validating"' in batch


def test_clone_qml_is_registered_and_loads_from_qrc_without_warnings():
    qrc = (ROOT / "ui/example/imports/resource.qrc").read_text(encoding="utf-8")
    for name in ("JiraCreateField.qml", "JiraOptionMultiPicker.qml", "JiraCreateDraftCard.qml", "JiraCreateBatchDialog.qml"):
        assert f"example/qml/component/issue/{name}" in qrc

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
qml = b"""import QtQuick 2.15; import QtQuick.Window 2.15; import "qrc:/example/qml/component/issue"
Window {{ visible: true; width: 900; height: 700
    JiraCreateBatchDialog {{ anchors.fill: parent; batchState: "editing"
        cloneDrafts: [
            {{issueId: "1", fields: [
                {{fieldId: "summary", name: "Summary", required: true, control: "text", options: [], value: "One", error: ""}},
                {{fieldId: "description", name: "Description", required: false, control: "multiline", options: [], value: "Text", error: ""}},
                {{fieldId: "priority", name: "Priority", required: true, control: "single", options: [{{value: "P1", label: "P1"}}], value: "P1", error: ""}}
            ], state: "draft"}},
            {{issueId: "2", fields: [
                {{fieldId: "components", name: "Components", required: false, control: "multi", options: [{{value: "UI", label: "UI"}}], value: ["UI"], error: ""}},
                {{fieldId: "product", name: "Product", required: false, control: "cascade", options: [{{value: "TV", label: "TV", children: [{{value: "A", label: "A"}}]}}], value: {{parent: "TV", child: "A"}}, error: ""}},
                {{fieldId: "assignee", name: "Assignee", required: false, control: "user", options: [{{value: "fred.chen", label: "Fred Chen"}}], value: "fred.chen", error: ""}}
            ], state: "draft"}}
        ]
    }}
}}"""
engine.loadData(qml)
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


def test_batch_editor_has_one_cancel_action_and_no_close_action():
    batch = BATCH_QML.read_text(encoding="utf-8")
    assert 'qsTr("Close")' not in batch
    assert batch.count('qsTr("Cancel")') == 1


def test_jira_batch_error_wraps_long_unbroken_server_responses():
    batch = BATCH_QML.read_text(encoding="utf-8")
    card = CARD_QML.read_text(encoding="utf-8")
    assert 'objectName: "jiraCloneBatchErrorScroll"' in batch
    assert 'objectName: "jiraCloneBatchErrorText"' in batch
    assert "wrapMode: Text.WrapAnywhere" in batch
    assert "ScrollBar.horizontal.policy: ScrollBar.AlwaysOff" in batch
    assert 'objectName: "jiraCloneDraftErrorText"' in card
    assert "Layout.fillWidth: true" in card
    assert "wrapMode: Text.WrapAnywhere" in card


def test_issue_filters_use_two_fixed_rows_so_search_stays_visible():
    browser = BROWSER_QML.read_text(encoding="utf-8")
    assert "id: primaryFilterRow" in browser
    assert "id: secondaryFilterRow" in browser
    assert browser.index("id: projectFilter") < browser.index("id: secondaryFilterRow")
    assert browser.index("id: subjectFilter") > browser.index("id: secondaryFilterRow")


def test_shared_text_styles_are_reduced_by_three_pixels():
    source = (ROOT / "ui/FluentUI/FluTextStyle.py").read_text(encoding="utf-8")
    for setter in (
        "caption.setPixelSize(10)",
        "body.setPixelSize(11)",
        "bodyStrong.setPixelSize(11)",
        "subtitle.setPixelSize(18)",
        "title.setPixelSize(26)",
        "titleLarge.setPixelSize(38)",
        "display.setPixelSize(66)",
    ):
        assert setter in source


def test_shared_scrollbar_is_mouse_draggable():
    source = (
        ROOT / "ui/FluentUI/imports/FluentUI/Controls/FluScrollBar.qml"
    ).read_text(encoding="utf-8")
    assert "interactive: true" in source
    assert "property int  maxLine : 8" in source

    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from FluentUI.imports import resource_rc
app = QGuiApplication([])
engine = QQmlApplicationEngine()
FluentUI.registerTypes(engine)
engine.loadData(b"""import QtQuick 2.15; import QtQuick.Window 2.15; import QtQuick.Controls 2.15; import FluentUI 1.0
Window {{ visible: true; width: 240; height: 240
    Flickable {{ id: flick; objectName: "flick"; anchors.fill: parent; contentHeight: 1000
        ScrollBar.vertical: FluScrollBar {{ objectName: "bar"; policy: ScrollBar.AlwaysOn }}
    }}
}}""")
app.processEvents()
window = engine.rootObjects()[0]
bar = window.findChild(QObject, "bar")
flick = window.findChild(QObject, "flick")
start = bar.mapToScene(QPointF(bar.width() / 2, 40))
end = bar.mapToScene(QPointF(bar.width() / 2, 150))
QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(start.x()), round(start.y())))
QTest.mouseMove(window, QPoint(round(end.x()), round(end.y())), 50)
QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(end.x()), round(end.y())))
app.processEvents()
print(bar.property("interactive"), bar.width(), flick.property("contentY"))
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    interactive, width, content_y = result.stdout.strip().split()
    assert interactive == "True"
    assert float(width) >= 8
    assert float(content_y) > 0


def test_combo_popup_uses_the_draggable_shared_scrollbar():
    source = (ROOT / "ui/FluentUI/imports/FluentUI/Controls/FluComboBox.qml").read_text(encoding="utf-8")
    assert "ScrollBar.vertical: FluScrollBar" in source
    assert "interactive: true" in source
    assert "T.ScrollIndicator.vertical" not in source


def test_clone_fixed_text_is_finished_in_both_catalogs():
    contexts = {"JiraCreateField", "JiraCreateDraftCard", "JiraCreateBatchDialog"}
    warning_sources = BRIDGE_ATTACHMENT_WARNING_SOURCES | {
        "Attachment warning for %1.",
    }
    for filename in ("example_en_US.ts", "example_zh_CN.ts"):
        root = ET.parse(ROOT / "ui/example" / filename).getroot()
        available = {node.findtext("name"): node for node in root.findall("context")}
        for name in contexts:
            assert name in available
            for message in available[name].findall("message"):
                translation = message.find("translation")
                assert translation is not None
                assert translation.get("type") != "unfinished"
                assert (translation.text or "").strip()
        bridge_messages = {
            message.findtext("source"): message.find("translation")
            for message in available["RedmineBridge"].findall("message")
        }
        assert warning_sources <= bridge_messages.keys()
        for source in warning_sources:
            translation = bridge_messages[source]
            assert translation is not None
            assert translation.get("type") != "unfinished"
            assert (translation.text or "").strip()


def test_lupdate_extracts_all_bridge_attachment_warning_sources(tmp_path):
    output = tmp_path / "redmine_bridge.ts"
    executable = (
        ROOT / ".venv/Scripts/pyside6-lupdate.exe"
        if os.name == "nt"
        else ROOT / ".venv/bin/pyside6-lupdate"
    )
    result = subprocess.run(
        [
            str(executable),
            str(ROOT / "ui/example/bridge/RedmineBridge.py"),
            "-ts",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    root = ET.parse(output).getroot()
    context = next(
        item
        for item in root.findall("context")
        if item.findtext("name") == "RedmineBridge"
    )
    extracted = {
        message.findtext("source") for message in context.findall("message")
    }
    assert BRIDGE_ATTACHMENT_WARNING_SOURCES <= extracted


def test_embedded_qm_translates_bridge_attachment_warning_in_both_locales():
    source = "Attachment upload failed for %1: %2"
    expected = {
        "example_en_US.qm": source,
        "example_zh_CN.qm": "附件 %1 上传失败：%2",
    }
    for catalog, translation in expected.items():
        probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QCoreApplication, QTranslator
from example.imports import resource_rc
app = QCoreApplication([])
translator = QTranslator()
loaded = translator.load(":/example/i18n/{catalog}")
app.installTranslator(translator)
sys.stdout.write(
    str(loaded) + " "
    + QCoreApplication.translate("RedmineBridge", {source!r})
)
'''
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=ROOT,
            env=dict(os.environ, PYTHONIOENCODING="utf-8"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=15,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        assert result.stdout.strip() == f"True {translation}"


def test_redmine_workspace_loader_activates_batch_module_from_qrc():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, Property, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
class Bridge(QObject):
    changed = Signal()
    cloneSelectionMode = Property(bool, lambda self: False, notify=changed)
    cloneSelectedIds = Property('QVariantList', lambda self: [], notify=changed)
    cloneDrafts = Property('QVariantList', lambda self: [], notify=changed)
    cloneBatchState = Property(str, lambda self: 'prepare_failed', notify=changed)
    cloneBatchLoaded = Property(int, lambda self: 0, notify=changed)
    cloneBatchTotal = Property(int, lambda self: 0, notify=changed)
    cloneBatchError = Property(str, lambda self: 'Jira identity unavailable', notify=changed)
    firstInvalidIssueId = Property(str, lambda self: '', notify=changed)
    firstInvalidFieldId = Property(str, lambda self: '', notify=changed)
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
FluentUI.registerTypes(engine); bridge=Bridge(); engine.rootContext().setContextProperty('RedmineBridge', bridge)
engine.loadData(b'import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible: true; width: 1000; height: 720; Loader {{ anchors.fill: parent; source: "qrc:/example/qml/component/redmine/RedmineWorkspace.qml" }} }}')
app.processEvents(); app.processEvents()
button=engine.rootObjects()[0].findChild(QObject, 'jiraCloneBatchCreateButton')
retry=engine.rootObjects()[0].findChild(QObject, 'jiraCloneRetryPrepareButton')
print(len(engine.rootObjects()), len(warnings), button is not None, retry is not None, warnings)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "1 0 True True []" in result.stdout


def test_real_qml_field_events_emit_transport_values_for_required_controls():
    probe = f'''
import json
import sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine, QQmlExpression
from FluentUI import FluentUI
from example.imports import resource_rc
app = QGuiApplication([])
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
FluentUI.registerTypes(engine)
engine.loadData(b"""
import QtQuick 2.15
import QtQuick.Window 2.15
import "qrc:/example/qml/component/issue"
Window {{
    visible: true
    width: 900
    height: 700
    Column {{
        JiraCreateField {{
            issueId: "1"
            field: ({{"fieldId": "channel", "name": "Channel",
                "control": "cascade", "required": true, "error": "required",
                "value": {{"parent": "p", "child": ""}},
                "options": [{{"label": "Parent", "value": "p",
                    "children": [{{"label": "Child", "value": "c"}}]}}]}})
            onValueChanged: (issueId, fieldId, value) =>
                console.log("FIELD_EVENT", fieldId, JSON.stringify(value))
        }}
        JiraCreateField {{
            issueId: "1"
            field: ({{"fieldId": "release", "name": "Release Choice",
                "control": "single", "required": true, "error": "required",
                "value": "", "options": [{{"label": "R", "value": "r"}}]}})
            onValueChanged: (issueId, fieldId, value) =>
                console.log("FIELD_EVENT", fieldId, JSON.stringify(value))
        }}
        JiraCreateField {{
            issueId: "1"
            field: ({{"fieldId": "compare", "name": "Compare Status",
                "control": "single", "required": true, "error": "required",
                "value": "", "options": [{{"label": "Same", "value": "same"}}]}})
            onValueChanged: (issueId, fieldId, value) =>
                console.log("FIELD_EVENT", fieldId, JSON.stringify(value))
        }}
        JiraCreateField {{
            issueId: "1"
            field: ({{"fieldId": "coworker", "name": "FAE Coworker",
                "control": "user", "required": true, "error": "required",
                "value": "", "options": [{{"label": "User", "value": "user"}}]}})
            onValueChanged: (issueId, fieldId, value) =>
                console.log("FIELD_EVENT", fieldId, JSON.stringify(value))
        }}
    }}
}}
""")
app.processEvents()
root = engine.rootObjects()[0]
captured = []
def capture(_issue_id, field_id, value):
    if hasattr(value, "toVariant"):
        value = value.toVariant()
    captured.append((field_id, value))
events = (
    ("jiraCreateCascadeChild_channel", "activated(0)"),
    ("jiraCreateSingle_release", "activated(0)"),
    ("jiraCreateSingle_compare", "activated(0)"),
    ("jiraCreateUser_coworker",
     'itemClicked({{"title": "User", "value": "user"}})'),
)
for object_name, expression in events:
    target = root.findChild(QObject, object_name)
    assert target is not None, object_name
    owner = target
    while owner is not None and not hasattr(owner, "valueChanged"):
        owner = owner.parent()
    assert owner is not None, object_name
    owner.valueChanged.connect(capture)
    qml_expression = QQmlExpression(
        QQmlEngine.contextForObject(target), target, expression
    )
    qml_expression.evaluate()
    assert not qml_expression.hasError(), qml_expression.error()
    app.processEvents()
print("CAPTURED", json.dumps(captured, separators=(",", ":")))
'''
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=15,
    )
    output = result.stderr + result.stdout
    assert result.returncode == 0, output
    assert (
        'CAPTURED [["channel",{"child":"c","parent":"p"}],'
        '["release","r"],["compare","same"],["coworker","user"]]'
    ) in output


def test_real_workspace_receives_bridge_field_map_and_clears_visible_errors():
    probe = f'''
import sys
sys.path.insert(0, r"{ROOT}")
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
from support.jira_integration.core.create_schema import (
    CreateFieldControl, CreateFieldOption, CreateFieldSchema,
)
from testing.self_tests.ui.test_redmine_bridge import (
    CLONE_SCHEMA, clone_bridge, wait_for,
)

channel = CreateFieldSchema(
    "customfield_channel", "Channel of Reporter", True,
    CreateFieldControl.CASCADE,
    options=(CreateFieldOption(
        "parent", "Parent",
        (CreateFieldOption("child", "Child"),),
    ),),
    value={{"parent": "parent", "child": ""}},
    child_required=True,
)
release = CreateFieldSchema(
    "customfield_release", "Release Choice", True,
    CreateFieldControl.SINGLE,
    options=(CreateFieldOption("release", "Release"),),
)
compare = CreateFieldSchema(
    "customfield_compare", "Compare Status", True,
    CreateFieldControl.SINGLE,
    options=(CreateFieldOption("same", "Same"),),
)
app = QGuiApplication([])
bridge = clone_bridge(schema=CLONE_SCHEMA + (channel, release, compare))
bridge.prepareCloneDrafts()
wait_for(lambda: bridge.cloneBatchState == "editing")
bridge._batch_controller.update_draft("1", "customfield_10409", "")

engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
FluentUI.registerTypes(engine)
engine.rootContext().setContextProperty("RedmineBridge", bridge)
engine.loadData(b"""
import QtQuick 2.15
import QtQuick.Window 2.15
Window {{
    visible: true
    width: 1100
    height: 760
    Loader {{
        anchors.fill: parent
        source: "qrc:/example/qml/component/redmine/RedmineWorkspace.qml"
    }}
}}
""")
bridge.changed.emit()
for _ in range(10):
    app.processEvents()
root = engine.rootObjects()[0]
button = root.findChild(QObject, "jiraCloneBatchCreateButton")
assert button is not None, warnings
dialog = button
while dialog is not None and not hasattr(dialog, "fieldState"):
    dialog = dialog.parent()
assert dialog is not None, warnings
field_ids = (
    "customfield_channel",
    "customfield_release",
    "customfield_compare",
    "customfield_10409",
)
for field_id in field_ids:
    assert dialog.fieldState("1", field_id).toVariant()["error"]

bridge.updateCloneDraft(
    "1", "customfield_channel",
    {{"parent": "parent", "child": "child"}},
)
bridge.updateCloneDraft("1", "customfield_release", "release")
bridge.updateCloneDraft("1", "customfield_compare", "same")
bridge.updateCloneDraft("1", "customfield_10409", "selected.user")
app.processEvents()
app.processEvents()

for field_id in field_ids:
    field = dialog.fieldState("1", field_id).toVariant()
    assert field["error"] == "", (field_id, field)
print("WORKSPACE_FIELD_PATCH_OK")
bridge.close()
'''
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=20,
    )
    output = result.stderr + result.stdout
    assert result.returncode == 0, output
    assert "WORKSPACE_FIELD_PATCH_OK" in output
