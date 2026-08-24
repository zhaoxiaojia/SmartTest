import QtQuick 2.15
import QtQuick.Controls 2.15
import FluentUI 1.0

Item {
    id: control

    property alias model: logList.model
    property int count: logList.count
    property real contentY: logList.contentY

    signal movementStarted(real contentY)
    signal movementEnded(real contentY)

    function positionAtEnd() {
        if (logList.count <= 0) {
            return
        }
        logList.positionViewAtIndex(logList.count - 1, ListView.End)
    }

    clip: true

    ListView {
        id: logList
        anchors.fill: parent
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: logScrollBar
        spacing: 2
        onMovementStarted: control.movementStarted(contentY)
        onMovementEnded: control.movementEnded(contentY)

        delegate: Rectangle {
            function rowValue(key, fallbackValue) {
                if (typeof modelData === "object" && modelData !== null && modelData[key] !== undefined) {
                    return modelData[key]
                }
                if (key === "line" && typeof line !== "undefined") return line
                if (key === "accent_color_light" && typeof accent_color_light !== "undefined") return accent_color_light
                if (key === "accent_color_dark" && typeof accent_color_dark !== "undefined") return accent_color_dark
                if (key === "text_color_light" && typeof text_color_light !== "undefined") return text_color_light
                if (key === "text_color_dark" && typeof text_color_dark !== "undefined") return text_color_dark
                if (key === "background_color_light" && typeof background_color_light !== "undefined") return background_color_light
                if (key === "background_color_dark" && typeof background_color_dark !== "undefined") return background_color_dark
                return fallbackValue
            }

            width: logList.width - 20
            implicitHeight: logText.implicitHeight + 8
            radius: 4
            color: "transparent"

            Rectangle {
                width: 3
                radius: 2
                anchors {
                    left: parent.left
                    top: parent.top
                    bottom: parent.bottom
                    margins: 3
                }
                color: FluTheme.dark ? rowValue("accent_color_dark", FluTheme.primaryColor) : rowValue("accent_color_light", FluTheme.primaryColor)
            }

            TextEdit {
                id: logText
                anchors {
                    left: parent.left
                    right: parent.right
                    top: parent.top
                    margins: 4
                    leftMargin: 10
                }
                readOnly: true
                wrapMode: Text.WrapAnywhere
                text: rowValue("line", "")
                color: FluTheme.dark ? rowValue("text_color_dark", FluTheme.fontPrimaryColor) : rowValue("text_color_light", FluTheme.fontPrimaryColor)
                font: FluTextStyle.Caption
                selectByMouse: true
                renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
                leftPadding: 0
                rightPadding: 0
                topPadding: 0
                bottomPadding: 0
            }
        }
    }

    FluScrollBar {
        id: logScrollBar
        anchors {
            right: parent.right
            rightMargin: 5
            top: parent.top
            bottom: parent.bottom
            topMargin: 3
            bottomMargin: 3
        }
    }
}
