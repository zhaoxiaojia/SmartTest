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
    assert "Flow" not in field
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


def test_user_suggestions_do_not_open_during_initial_model_render():
    field = FIELD_QML.read_text(encoding="utf-8")
    user = field[field.index("id: userEditor"):field.index("function optionIndex")]
    assert 'text: ""' in user
    assert "Component.onCompleted: updateText" in user
    dialog = BATCH_QML.read_text(encoding="utf-8")
    assert "function onContentYChanged() { draftScroll.forceActiveFocus() }" in dialog


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


def test_clone_fixed_text_is_finished_in_both_catalogs():
    contexts = {"JiraCreateField", "JiraCreateDraftCard", "JiraCreateBatchDialog"}
    warning_sources = BRIDGE_ATTACHMENT_WARNING_SOURCES | {
        "Attachment warning for %1."
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
