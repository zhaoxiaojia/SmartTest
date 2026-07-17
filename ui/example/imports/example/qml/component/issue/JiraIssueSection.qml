import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

ColumnLayout {
    id: root
    property string title: ""
    property bool expanded: true
    default property alias content: body.data
    spacing: 7

    RowLayout {
        Layout.fillWidth: true
        spacing: 5

        Rectangle {
            Layout.preferredWidth: 13
            Layout.preferredHeight: 13
            radius: 3
            color: FluTheme.dark ? "#263241" : "#EBECF0"
            border.color: FluTheme.dark ? "#3F4B5B" : "#DFE1E6"

            FluIcon {
                anchors.centerIn: parent
                iconSource: root.expanded ? FluentIcons.ChevronDown : FluentIcons.ChevronRight
                iconSize: 8
                color: FluTheme.fontSecondaryColor
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.expanded = !root.expanded
            }
        }

        FluText {
            text: root.title
            font: FluTextStyle.BodyStrong
            color: FluTheme.fontPrimaryColor
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.expanded = !root.expanded
            }
        }
    }

    ColumnLayout {
        id: body
        Layout.fillWidth: true
        visible: root.expanded
        spacing: 7
    }
}
