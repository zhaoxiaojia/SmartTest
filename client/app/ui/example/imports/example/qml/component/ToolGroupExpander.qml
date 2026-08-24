import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

Item {
    id: root
    property alias headerText: header.headerText
    property alias expand: header.expand
    property var toolGroup: ({"available": false, "tools": []})
    signal toolActivated(string groupId, int toolIndex)

    implicitHeight: header.height + (expand && toolGroup.available ? toolContent.implicitHeight : 0)

    FluExpander {
        id: header
        width: parent.width
        height: 45
        contentHeight: 0
    }

    Rectangle {
        id: toolContent
        y: header.height - 1
        width: parent.width
        height: root.expand && root.toolGroup.available ? implicitHeight : 0
        visible: height > 0
        clip: true
        radius: 4
        color: FluTheme.frameColor
        border.color: FluTheme.dividerColor
        implicitHeight: toolItems.implicitHeight + 12

        ColumnLayout {
            id: toolItems
            x: 6
            y: 6
            width: parent.width - 12
            spacing: 4

            Repeater {
                model: root.toolGroup.available ? root.toolGroup.tools : []

                FluButton {
                    Layout.fillWidth: true
                    text: modelData.title
                    contentItem: FluText {
                        text: parent.text
                        horizontalAlignment: Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        font: parent.font
                        color: parent.textColor
                    }
                    onClicked: root.toolActivated(root.toolGroup.id, index)
                }
            }
        }
    }
}
