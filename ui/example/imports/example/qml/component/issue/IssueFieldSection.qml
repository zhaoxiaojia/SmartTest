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
            FluText {
                objectName: modelData.kind === "link" ? "issueFieldLink_" + index : ""
                Layout.fillWidth: true
                text: modelData.kind === "tags" ? (modelData.values || []).join(", ") : (modelData.value || "-")
                wrapMode: Text.WrapAnywhere
                color: modelData.kind === "link" ? (FluTheme.dark ? "#6EA8FE" : "#0F62FE") : FluTheme.fontPrimaryColor
                MouseArea { anchors.fill: parent; enabled: modelData.kind === "link" && !!modelData.url; cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: root.externalLinkRequested(modelData.url) }
            }
        }
    }
}
