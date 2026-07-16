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
    assert "issueAttachmentDropSurface" in combined
    assert "setLineDash" in combined
    assert "projectPath" in combined and "typeIcon" in combined
    assert "thumbnailUrl" in combined and "avatarUrl" in combined
    assert "isLocalFileUrl" in combined
    for hook in ("issueFieldStatus_", "issueFieldPerson_", "issueFieldMultiline_", "issueCommentAvatarPlaceholder_"):
        assert hook in combined
    assert "onDropBorderColorChanged" in combined


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
engine.loadData('import QtQuick 2.15; import QtQuick.Window 2.15; import FluentUI 1.0; Window {{ visible:true; width:1200; height:850; function useDark(){{FluTheme.darkMode=FluThemeType.Dark}} function useLight(){{FluTheme.darkMode=FluThemeType.Light}} Loader {{ id:l; anchors.fill:parent; source:"qrc:/example/qml/component/issue/IssueDetailView.qml"; onLoaded: {{ item.issue={{"key":"ST-42","title":"Long issue title 中文 raw","webUrl":"https://issue/42","typeIcon":"qrc:/example/res/svg/jira-software-icon.svg","projectPath":[{{"label":"QA","url":"https://project"}},{{"label":"Smart Home","url":""}}],"detailsFields":[{{"label":"Status","value":"Open","kind":"status"}},{{"label":"Spec","value":"原始字段","kind":"link","url":"https://field"}}],"peopleFields":[{{"label":"Assignee","value":"Coco","kind":"person"}}],"dateFields":[{{"label":"Created","value":"2026-07-16","kind":"text"}}],"extraSections":[],"description":"raw description 中文"}}; item.comments=[{{"author":"Atlas","avatarUrl":"qrc:/example/res/svg/avatar_1.svg","time":"now","body":"raw comment"}}]; item.attachments=[{{"name":"screen.png","kind":"image","thumbnailUrl":"qrc:/example/res/image/image_1.jpg","time":"now","size":"12 KB","url":"file:///screen.png"}}] }} }} }}'.encode('utf-8'))
app.processEvents(); window=engine.rootObjects()[0]; detail=next((child.property('item') for child in window.contentItem().childItems() if child.property('item') is not None), None)
if detail is None: print([str(x) for x in warnings]); raise SystemExit(4)
issue=detail.property('issue').toVariant(); issue['projectPath']=[{{'label':'Very long quality organization path segment','url':'https://project/exact'}},{{'label':'Another long Smart Home component segment','url':''}}]; issue['detailsFields'] += [{{'label':'Owner','value':'Coco','kind':'person'}},{{'label':'Notes','value':'multiline long value 中文 /very/long/path','kind':'multiline'}},{{'label':'Tags','kind':'tags','values':['one','two']}}]; detail.setProperty('issue',issue); detail.setProperty('comments',[{{'author':'Atlas','avatarUrl':'qrc:/example/res/svg/avatar_1.svg','time':'now','body':'raw comment'}},{{'author':'Coco','avatarUrl':'','time':'later','body':'fallback avatar'}}]); app.processEvents()
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
detail.attachmentOpenRequested.connect(lambda key,row: events.append(('attachment',key,variant(row))))
left=find('issueDetailLeftColumn'); right=find('issueDetailRightColumn'); root=find('issueDetailRoot')
ratio=left.property('width')/(left.property('width')+right.property('width'))
def click(obj):
 if obj is None: raise RuntimeError('missing click target')
 p=obj.mapToScene(QPointF(obj.property('width')/2,obj.property('height')/2)); QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(p.x()),round(p.y()))); app.processEvents()
field_hooks=all(find(name) is not None and find(name).property('visible') for name in ('issueFieldStatus_0','issueFieldPerson_2','issueFieldMultiline_3'))
click(find('issueKeyLink')); click(find('issueTitleLink')); click(find('issueProjectPath_0')); click(find('issueFieldLink_1'))
click(find('issueCommentButton')); editor=find('issueCommentEditor'); editor.setProperty('text','draft text'); click(find('issueCommentSubmit')); detail.setProperty('commentSubmitting',True); click(find('issueCommentSubmit')); detail.setProperty('commentSubmitting',False)
draft_before=editor.property('text'); detail.clearCommentDraft(); draft_after=editor.property('text')
detail.selectAttachmentFiles(['file:///C:/one.png','file://server/share/two.txt','https://bad','file:broken']); app.processEvents()
detail.stageDroppedFiles(['file:///C:/upload.png','file://server/share/upload.txt','https://bad','file:broken']); app.processEvents(); before=len([e for e in events if e[0]=='upload']); QMetaObject.invokeMethod(find('issueUploadConfirmDialog'),'positiveClicked',Qt.DirectConnection); app.processEvents(); after=len([e for e in events if e[0]=='upload'])
detail.stageDroppedFiles(['file:///cancel.txt']); QMetaObject.invokeMethod(find('issueUploadConfirmDialog'),'negativeClicked',Qt.DirectConnection); app.processEvents(); canceled=len([e for e in events if e[0]=='upload'])
card=find('issueAttachmentCard_0'); root.setProperty('contentY',max(0,card.mapToItem(root,QPointF(0,0)).y()-300)); app.processEvents(); click(card)
visible_hooks=all(find(name) is not None and find(name).property('visible') for name in ('issueAttachmentDropSurface','issueTypeIcon','issueProjectPath_0','issueAttachmentThumbnail','issueCommentAvatar_0','issueCommentAvatarPlaceholder_1'))
border=find('issueAttachmentDashedBorder'); light_color=str(border.property('renderedBorderColor')); QMetaObject.invokeMethod(window,'useDark',Qt.DirectConnection); app.processEvents(); dark_color=str(border.property('renderedBorderColor')); QMetaObject.invokeMethod(window,'useLight',Qt.DirectConnection); app.processEvents(); light_again=str(border.property('renderedBorderColor')); theme_changed=light_color!=dark_color and light_color==light_again
bad=[str(x) for x in warnings]
window.setWidth(760); app.processEvents(); narrow_ratio=left.property('width')/(left.property('width')+right.property('width'))
bounded=left.property('x')>=0 and right.property('x')+right.property('width')<=root.property('width')
path=find('issueProjectPath_0'); path_pos=path.mapToItem(root,QPointF(0,0)); header_bounded=path_pos.x()>=0 and path_pos.x()+path.property('width')<=root.property('width')
print(round(ratio,3), round(narrow_ratio,3), left.property('y')==right.property('y'), root.property('contentWidth')<=root.property('width'), bounded, header_bounded, visible_hooks, field_hooks, theme_changed, events, draft_before, draft_after, before, after, canceled, len(bad))
'''
    result = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "0.68 0.68 True True True True True True True" in result.stdout
    assert "('open', 'ST-42', 'https://issue/42')" in result.stdout
    assert result.stdout.count("('link', 'https://project/exact')") == 1
    assert result.stdout.count("('link', 'https://field')") == 1
    assert result.stdout.count("('open', 'ST-42', 'https://issue/42')") == 2
    assert "('select', 'ST-42', ['file:///C:/one.png', 'file://server/share/two.txt'])" in result.stdout
    assert result.stdout.count("('comment', 'ST-42', 'draft text')") == 1
    assert "('upload', 'ST-42', ['file:///C:/upload.png', 'file://server/share/upload.txt'])" in result.stdout
    assert "'thumbnailUrl': 'qrc:/example/res/image/image_1.jpg'" in result.stdout
    assert result.stdout.count("('attachment', 'ST-42'") == 1
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
