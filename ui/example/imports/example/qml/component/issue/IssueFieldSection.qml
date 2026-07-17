import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

ColumnLayout {
    id: root
    property string title: ""
    property var fields: []
    signal externalLinkRequested(string url)
    spacing: 7
    FluText { text: root.title; font: FluTextStyle.BodyStrong }
    Rectangle { Layout.fillWidth: true; height: 1; color: FluTheme.dividerColor }
    Repeater {
        model: root.fields || []
        RowLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            spacing: 10
            FluText { Layout.preferredWidth: 105; text: modelData.label || ""; color: FluTheme.fontSecondaryColor; wrapMode: Text.WordWrap }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
            FluText {
                objectName: modelData.kind === "link" ? "issueFieldLink_" + index : ""
                Layout.fillWidth: true
                visible: ["status", "person", "multiline"].indexOf(modelData.kind) < 0
                text: modelData.kind === "tags" ? (modelData.values || []).join(", ") : (modelData.value || "")
                wrapMode: Text.WrapAnywhere
                color: modelData.kind === "link" ? (FluTheme.dark ? "#6EA8FE" : "#0F62FE") : FluTheme.fontPrimaryColor
                MouseArea { anchors.fill: parent; enabled: modelData.kind === "link" && !!modelData.url; cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: root.externalLinkRequested(modelData.url) }
            }
            Rectangle { objectName: modelData.kind === "status" ? "issueFieldStatus_" + index : ""; visible: modelData.kind === "status"; implicitWidth: statusText.implicitWidth + 16; implicitHeight: statusText.implicitHeight + 6; radius: implicitHeight / 2; color: FluTheme.dark ? "#294A3A" : "#E3FCEF"; border.color: FluTheme.dark ? "#65BA86" : "#36B37E"; FluText { id: statusText; anchors.centerIn: parent; text: modelData.value || ""; font: FluTextStyle.Caption } }
            RowLayout { objectName: modelData.kind === "person" ? "issueFieldPerson_" + index : ""; visible: modelData.kind === "person"; spacing: 6; Image { visible: !!modelData.avatarUrl; source: modelData.avatarUrl || ""; Layout.preferredWidth: 24; Layout.preferredHeight: 24; fillMode: Image.PreserveAspectCrop } Rectangle { visible: !modelData.avatarUrl && !!modelData.value; Layout.preferredWidth: 24; Layout.preferredHeight: 24; radius: 12; color: FluTheme.primaryColor; FluText { anchors.centerIn: parent; text: (modelData.value || "?").charAt(0).toUpperCase(); color: "white"; font: FluTextStyle.Caption } } FluText { text: modelData.value || ""; wrapMode: Text.WordWrap } }
            FluText { objectName: modelData.kind === "multiline" ? "issueFieldMultiline_" + index : ""; visible: modelData.kind === "multiline"; Layout.fillWidth: true; text: modelData.value || ""; wrapMode: Text.WrapAnywhere }
            }
        }
    }
}
