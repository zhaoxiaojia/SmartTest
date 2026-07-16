import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

Rectangle {
    id: root
    property var attachment: ({})
    signal clicked(var attachment)
    width: 220; height: 72; radius: 5; color: FluTheme.frameColor; border.color: FluTheme.dividerColor
    RowLayout { anchors.fill: parent; anchors.margins: 8; FluIcon { iconSource: FluentIcons.Attach; iconSize: 24; color: FluTheme.primaryColor } ColumnLayout { Layout.fillWidth: true; spacing: 2; FluText { Layout.fillWidth: true; text: root.attachment.name || ""; wrapMode: Text.WrapAnywhere } FluText { Layout.fillWidth: true; text: (root.attachment.time || "") + "  " + (root.attachment.size || ""); font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor; wrapMode: Text.WordWrap } } }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.clicked(root.attachment) }
}
