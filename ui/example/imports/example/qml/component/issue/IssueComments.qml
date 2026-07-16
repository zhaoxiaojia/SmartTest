import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

ColumnLayout {
    id: root
    property string issueKey: ""
    property var comments: []
    property bool loading: false
    property bool submitting: false
    property string error: ""
    signal submitRequested(string issueKey, string content)
    spacing: 8
    function clearDraft() { editor.text = "" }

    RowLayout { Layout.fillWidth: true; FluText { text: qsTr("Comments"); font: FluTextStyle.BodyStrong } Item { Layout.fillWidth: true } FluButton { objectName: "issueCommentButton"; text: qsTr("Comment"); disabled: root.submitting; onClicked: editorArea.visible = true } }
    Rectangle { Layout.fillWidth: true; height: 1; color: FluTheme.dividerColor }
    FluText { visible: root.loading; text: qsTr("Loading comments..."); color: FluTheme.fontSecondaryColor }
    FluText { visible: !root.loading && (root.comments || []).length === 0; text: qsTr("No comments yet."); color: FluTheme.fontSecondaryColor }
    Repeater { model: root.comments || []; Rectangle { Layout.fillWidth: true; implicitHeight: commentRow.implicitHeight + 16; radius: 5; color: FluTheme.frameColor; RowLayout { id: commentRow; anchors.fill: parent; anchors.margins: 8; Image { objectName: "issueCommentAvatar_" + index; visible: !!modelData.avatarUrl; source: modelData.avatarUrl || ""; Layout.preferredWidth: 32; Layout.preferredHeight: 32; fillMode: Image.PreserveAspectCrop } Rectangle { visible: !modelData.avatarUrl; Layout.preferredWidth: 32; Layout.preferredHeight: 32; radius: 16; color: FluTheme.primaryColor; FluText { anchors.centerIn: parent; text: (modelData.author || "?").charAt(0).toUpperCase(); color: "white" } } ColumnLayout { Layout.fillWidth: true; FluText { text: (modelData.author || "") + "  " + (modelData.time || ""); font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor } FluText { Layout.fillWidth: true; text: modelData.body || ""; wrapMode: Text.WrapAnywhere } } } } }
    FluText { visible: !!root.error; text: root.error; color: FluTheme.dark ? "#FF8A80" : "#C62828"; wrapMode: Text.WrapAnywhere }
    ColumnLayout {
        id: editorArea; visible: false; Layout.fillWidth: true
        FluMultilineTextBox { id: editor; objectName: "issueCommentEditor"; Layout.fillWidth: true; placeholderText: qsTr("Add a comment"); disabled: root.submitting }
        RowLayout { FluButton { objectName: "issueCommentSubmit"; text: root.submitting ? qsTr("Submitting...") : qsTr("Submit"); disabled: root.submitting || editor.text.trim().length === 0; onClicked: if (!disabled) root.submitRequested(root.issueKey, editor.text.trim()) } FluButton { text: qsTr("Cancel"); disabled: root.submitting; onClicked: editorArea.visible = false } }
    }
}
