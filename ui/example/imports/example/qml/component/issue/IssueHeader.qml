import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

ColumnLayout {
    id: root
    property var issue: ({})
    signal openRequested(string issueKey, string webUrl)
    signal externalLinkRequested(string url)
    spacing: 6

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        FluIcon { iconSource: FluentIcons.Document; iconSize: 18; color: FluTheme.primaryColor }
        FluText { text: root.issue.projectName || ""; color: FluTheme.fontSecondaryColor }
        FluText {
            visible: !!root.issue.projectUrl
            text: qsTr("Open project")
            color: FluTheme.dark ? "#6EA8FE" : "#0F62FE"
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.externalLinkRequested(root.issue.projectUrl || "") }
        }
    }
    FluText {
        objectName: "issueKeyLink"
        text: root.issue.key || ""
        font: FluTextStyle.BodyStrong
        color: FluTheme.dark ? "#6EA8FE" : "#0F62FE"
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.openRequested(root.issue.key || "", root.issue.webUrl || "") }
    }
    FluText {
        objectName: "issueTitleLink"
        Layout.fillWidth: true
        text: root.issue.title || ""
        font: FluTextStyle.Title
        wrapMode: Text.WrapAnywhere
        color: FluTheme.dark ? "#6EA8FE" : "#0F62FE"
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.openRequested(root.issue.key || "", root.issue.webUrl || "") }
    }
}
