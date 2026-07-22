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
WORKSPACE_QML = ROOT / "ui/example/imports/example/qml/component/redmine/RedmineWorkspace.qml"


def test_issue_list_clone_mode_and_batch_dialog_contract():
    browser = BROWSER_QML.read_text(encoding="utf-8")
    dialog = BATCH_QML.read_text(encoding="utf-8")
    assert "cloneSelectionMode" in browser and "cloneSelectable" in browser
    assert 'modelData.cloneStatus !== "cloned"' in browser
    assert "Repeater" in dialog and "cloneDrafts" in dialog
    assert "submitCloneBatch" in dialog and "updateCloneDraft" in dialog


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


def test_workspace_connects_selection_and_batch_actions_to_bridge():
    workspace = WORKSPACE_QML.read_text(encoding="utf-8")
    for slot in (
        "beginCloneSelection", "toggleCloneSelection", "cancelCloneSelection",
        "prepareCloneDrafts", "updateCloneDraft", "submitCloneBatch",
        "retryFailedClones", "closeCloneBatch", "searchCloneUsers",
    ):
        assert f"RedmineBridge.{slot}" in workspace


def test_clone_qml_is_registered_and_loads_from_qrc_without_warnings():
    qrc = (ROOT / "ui/example/imports/resource.qrc").read_text(encoding="utf-8")
    for name in ("JiraCreateField.qml", "JiraCreateDraftCard.qml", "JiraCreateBatchDialog.qml"):
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
