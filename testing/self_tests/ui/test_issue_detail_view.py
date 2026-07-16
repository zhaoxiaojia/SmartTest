from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ISSUE_DIR = ROOT / "ui/example/imports/example/qml/component/issue"
ISSUE_FILES = [
    "IssueDetailView.qml",
    "IssueHeader.qml",
    "IssueFieldSection.qml",
    "IssueDescription.qml",
    "IssueComments.qml",
    "IssueAttachments.qml",
    "IssueAttachmentCard.qml",
]


def test_issue_detail_component_contract_and_resources():
    for filename in ISSUE_FILES:
        assert (ISSUE_DIR / filename).is_file()
    qrc = (ROOT / "ui/example/imports/resource.qrc").read_text(encoding="utf-8")
    for filename in ISSUE_FILES:
        assert f"example/qml/component/issue/{filename}" in qrc

    detail = (ISSUE_DIR / "IssueDetailView.qml").read_text(encoding="utf-8")
    for declaration in (
        "property var issue", "property var comments", "property var attachments",
        "property bool commentsLoading", "property bool commentSubmitting",
        "property bool attachmentsLoading", "property bool attachmentUploading",
        "property string commentError", "property string attachmentError",
        "signal openIssueRequested", "signal externalLinkRequested",
        "signal commentSubmitRequested", "signal attachmentFilesSelected",
        "signal attachmentUploadConfirmed", "signal attachmentOpenRequested",
        "function clearCommentDraft()",
    ):
        assert declaration in detail
    combined = "\n".join(path.read_text(encoding="utf-8") for path in ISSUE_DIR.glob("*.qml"))
    for forbidden in ("Qt.openUrlExternally", "JiraBridge", "RedmineBridge", "Activity", "Work Log", "Set Due Date", "Resolve", "Export"):
        assert forbidden not in combined


def test_issue_detail_runtime_geometry_and_interactions():
    probe = f'''
import os, sys
sys.path.insert(0, r"{ROOT / 'ui'}")
from PySide6.QtCore import QObject, QPoint, QPointF, QMetaObject, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from FluentUI import FluentUI
from example.imports import resource_rc
app=QGuiApplication([]); engine=QQmlApplicationEngine(); warnings=[]; engine.warnings.connect(lambda rows: warnings.extend(rows))
FluentUI.registerTypes(engine)
engine.loadData('import QtQuick 2.15; import QtQuick.Window 2.15; Window {{ visible:true; width:1200; height:850; Loader {{ id:l; anchors.fill:parent; source:"qrc:/example/qml/component/issue/IssueDetailView.qml"; onLoaded: {{ item.issue={{"key":"ST-42","title":"Long issue title 中文 raw","webUrl":"https://issue/42","projectName":"Smart Home","projectUrl":"https://project","detailsFields":[{{"label":"Status","value":"Open","kind":"status"}},{{"label":"Spec","value":"原始字段","kind":"link","url":"https://field"}}],"peopleFields":[{{"label":"Assignee","value":"Coco","kind":"person"}}],"dateFields":[{{"label":"Created","value":"2026-07-16","kind":"text"}}],"extraSections":[],"description":"raw description 中文"}}; item.comments=[{{"author":"Atlas","time":"now","body":"raw comment"}}]; item.attachments=[{{"name":"screen.png","time":"now","size":"12 KB","url":"file:///screen.png"}}] }} }} }}'.encode('utf-8'))
app.processEvents(); window=engine.rootObjects()[0]; detail=next((child.property('item') for child in window.contentItem().childItems() if child.property('item') is not None), None)
if detail is None: print([str(x) for x in warnings]); raise SystemExit(4)
def find(name):
 pending=[detail]
 while pending:
  item=pending.pop()
  if item.objectName()==name: return item
  pending.extend(item.children())
  if hasattr(item,'childItems'): pending.extend(item.childItems())
events=[]
def variant(value): return value.toVariant() if hasattr(value,'toVariant') else value
detail.openIssueRequested.connect(lambda key,url: events.append(('open',key,url)))
detail.externalLinkRequested.connect(lambda url: events.append(('link',url)))
detail.commentSubmitRequested.connect(lambda key,text: events.append(('comment',key,text)))
detail.attachmentFilesSelected.connect(lambda key,urls: events.append(('select',key,[str(x) for x in variant(urls)])))
detail.attachmentUploadConfirmed.connect(lambda key,urls: events.append(('upload',key,[str(x) for x in variant(urls)])))
detail.attachmentOpenRequested.connect(lambda key,row: events.append(('attachment',key,variant(row).get('name'))))
left=find('issueDetailLeftColumn'); right=find('issueDetailRightColumn'); root=find('issueDetailRoot')
ratio=left.property('width')/(left.property('width')+right.property('width'))
def click(obj):
 if obj is None: raise RuntimeError('missing click target')
 p=obj.mapToScene(QPointF(obj.property('width')/2,obj.property('height')/2)); QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(p.x()),round(p.y()))); app.processEvents()
click(find('issueKeyLink')); click(find('issueTitleLink')); click(find('issueFieldLink_1'))
click(find('issueCommentButton')); editor=find('issueCommentEditor'); editor.setProperty('text','draft text'); click(find('issueCommentSubmit')); detail.setProperty('commentSubmitting',True); click(find('issueCommentSubmit')); detail.setProperty('commentSubmitting',False)
draft_before=editor.property('text'); detail.clearCommentDraft(); draft_after=editor.property('text')
detail.selectAttachmentFiles(['file:///one.png','file:///two.txt']); app.processEvents()
detail.stageDroppedFiles(['file:///a.png','https://bad']); app.processEvents(); before=len([e for e in events if e[0]=='upload']); QMetaObject.invokeMethod(find('issueUploadConfirmDialog'),'positiveClicked',Qt.DirectConnection); app.processEvents(); after=len([e for e in events if e[0]=='upload'])
detail.stageDroppedFiles(['file:///cancel.txt']); QMetaObject.invokeMethod(find('issueUploadConfirmDialog'),'negativeClicked',Qt.DirectConnection); app.processEvents(); canceled=len([e for e in events if e[0]=='upload'])
click(find('issueAttachmentCard_0'))
bad=[str(x) for x in warnings]
window.setWidth(760); app.processEvents(); narrow_ratio=left.property('width')/(left.property('width')+right.property('width'))
print(round(ratio,3), round(narrow_ratio,3), left.property('y')==right.property('y'), root.property('contentWidth')<=root.property('width'), events, draft_before, draft_after, before, after, canceled, len(bad))
'''
    result = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "0.68 0.68 True True" in result.stdout
    assert "('open', 'ST-42', 'https://issue/42')" in result.stdout
    assert "('link', 'https://field')" in result.stdout
    assert "('select', 'ST-42', ['file:///one.png', 'file:///two.txt'])" in result.stdout
    assert result.stdout.count("('comment', 'ST-42', 'draft text')") == 1
    assert "draft text  0 1 1 0" in result.stdout


def test_issue_detail_fixed_text_translations_are_complete():
    sources = set()
    for path in ISSUE_DIR.glob("*.qml"):
        text = path.read_text(encoding="utf-8")
        import re
        sources.update(re.findall(r'qsTr\("([^"]+)"\)', text))
    assert sources
    for catalog in ("example_en_US.ts", "example_zh_CN.ts"):
        root = ET.parse(ROOT / "ui/example" / catalog).getroot()
        messages = {m.findtext("source"): m.find("translation") for m in root.findall(".//message")}
        for source in sources:
            translation = messages.get(source)
            assert translation is not None
            assert translation.get("type") not in {"unfinished", "vanished"}
            assert (translation.text or "").strip()
