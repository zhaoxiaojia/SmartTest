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
        Image { objectName: "issueTypeIcon"; visible: !!root.issue.typeIcon; source: root.issue.typeIcon || ""; sourceSize.width: 18; sourceSize.height: 18; fillMode: Image.PreserveAspectFit }
        FluIcon { visible: !root.issue.typeIcon; iconSource: FluentIcons.Document; iconSize: 18; color: FluTheme.primaryColor }
        Flow {
            Layout.fillWidth: true
            spacing: 6
        Repeater {
            model: (root.issue.projectPath && root.issue.projectPath.length) ? root.issue.projectPath : (root.issue.projectName ? [{"label": root.issue.projectName, "url": root.issue.projectUrl || ""}] : [])
            Row {
                spacing: 6
                FluText { visible: index > 0; text: "/"; color: FluTheme.fontSecondaryColor }
                FluText {
                    objectName: "issueProjectPath_" + index
                    text: modelData.label || modelData.value || ""
                    color: modelData.url ? (FluTheme.dark ? "#6EA8FE" : "#0F62FE") : FluTheme.fontSecondaryColor
                    MouseArea { anchors.fill: parent; enabled: !!modelData.url; cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: root.externalLinkRequested(modelData.url) }
                }
            }
        }
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
