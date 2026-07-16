import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

Rectangle {
    id: root
    property var attachment: ({})
    signal clicked(var attachment)
    width: 220; height: 72; radius: 5; color: FluTheme.frameColor; border.color: FluTheme.dividerColor
    RowLayout { anchors.fill: parent; anchors.margins: 8; Image { objectName: "issueAttachmentThumbnail"; visible: !!root.attachment.thumbnailUrl; source: root.attachment.thumbnailUrl || ""; Layout.preferredWidth: 48; Layout.preferredHeight: 48; fillMode: Image.PreserveAspectCrop } FluIcon { objectName: "issueAttachmentFallbackIcon"; visible: !root.attachment.thumbnailUrl; iconSource: (root.attachment.kind === "image") ? FluentIcons.Photo : FluentIcons.Document; iconSize: 24; color: FluTheme.primaryColor } ColumnLayout { Layout.fillWidth: true; spacing: 2; FluText { Layout.fillWidth: true; text: root.attachment.name || root.attachment.filename || ""; wrapMode: Text.WrapAnywhere } FluText { Layout.fillWidth: true; text: (root.attachment.time || "") + "  " + (root.attachment.size || ""); font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor; wrapMode: Text.WordWrap } } }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.clicked(root.attachment) }
}
