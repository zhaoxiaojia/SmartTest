import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

FluFrame {
    id: root
    property var draft: ({})
    property bool disabled: false
    property real labelColumnWidth: 180
    signal valueChanged(string issueId, string fieldId, var value)
    signal userSearchRequested(string issueId, string fieldId, string query)
    signal sourceLinkRequested(string url)

    Layout.fillWidth: true
    padding: 14
    implicitHeight: content.implicitHeight + 28

    ColumnLayout {
        id: content
        anchors.left: parent.left; anchors.right: parent.right
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            FluText { text: qsTr("Redmine #%1").arg(root.draft.issueId || ""); font: FluTextStyle.Subtitle }
            FluButton { text: qsTr("Open source"); visible: !!root.draft.sourceUrl; onClicked: root.sourceLinkRequested(root.draft.sourceUrl) }
            Item { Layout.fillWidth: true }
            FluText { text: root.resultText(); color: root.draft.state === "failed" ? "#D13438" : FluTheme.fontSecondaryColor }
        }
        Repeater {
            id: fieldRepeater
            model: root.draft.fields || []
            JiraCreateField {
                Layout.fillWidth: true
                issueId: root.draft.issueId || ""
                field: modelData
                disabled: root.disabled
                labelColumnWidth: root.labelColumnWidth
                onValueChanged: (issueId, fieldId, value) => root.valueChanged(issueId, fieldId, value)
                onUserSearchRequested: (issueId, fieldId, query) => root.userSearchRequested(issueId, fieldId, query)
            }
        }
        FluText { visible: !!root.draft.error; text: root.draft.error || ""; color: "#D13438"; wrapMode: Text.Wrap }
        Repeater {
            model: root.draft.attachmentWarnings || []
            FluText {
                Layout.fillWidth: true
                text: modelData.attachmentWarningText || ""
                color: FluTheme.dark ? "#FCE100" : "#986F0B"
                wrapMode: Text.Wrap
            }
        }
    }

    function resultText() {
        if (root.draft.state === "created") return qsTr("Created: %1").arg(root.draft.key || "")
        if (root.draft.state === "duplicate") return qsTr("Duplicate: %1").arg(root.draft.key || "")
        if (root.draft.state === "failed") return qsTr("Failed")
        return ""
    }
    function focusField(fieldId) {
        for (var i = 0; i < fieldRepeater.count; ++i) {
            var editor = fieldRepeater.itemAt(i)
            if (editor && (editor.field.fieldId || "") === fieldId) {
                editor.focusEditor()
                return true
            }
        }
        return false
    }
}
