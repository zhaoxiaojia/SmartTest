import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0

FluPopup {
    id: control

    property string imageSource: ""
    property string imageTitle: ""

    width: Math.min(Math.max(720, previewImage.implicitWidth + 16), parent ? parent.width * 0.98 : 1320)
    height: Math.min(Math.max(480, previewImage.implicitHeight + header.height + 16), parent ? parent.height * 0.98 : 860)
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    function showImage(source, title) {
        imageSource = source || ""
        imageTitle = title || ""
        imageFlickable.contentX = 0
        imageFlickable.contentY = 0
        open()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: header
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            color: FluTheme.dark ? Qt.rgba(37 / 255, 37 / 255, 37 / 255, 1) : Qt.rgba(248 / 255, 248 / 255, 248 / 255, 1)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 8
                spacing: 8

                FluText {
                    Layout.fillWidth: true
                    text: imageTitle
                    font: FluTextStyle.BodyStrong
                    elide: Text.ElideRight
                }

                FluText {
                    visible: previewImage.status === Image.Ready
                    text: previewImage.implicitWidth + " x " + previewImage.implicitHeight
                    font: FluTextStyle.Caption
                    color: FluTheme.fontSecondaryColor
                }

                FluIconButton {
                    iconSource: FluentIcons.ChromeClose
                    onClicked: control.close()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: FluTheme.dark ? Qt.rgba(20 / 255, 20 / 255, 20 / 255, 1) : Qt.rgba(250 / 255, 250 / 255, 250 / 255, 1)
            clip: true

            Flickable {
                id: imageFlickable
                anchors.fill: parent
                anchors.margins: 4
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                contentWidth: Math.max(width, previewImage.implicitWidth)
                contentHeight: Math.max(height, previewImage.implicitHeight)
                ScrollBar.horizontal: FluScrollBar {}
                ScrollBar.vertical: FluScrollBar {}

                FluImage {
                    id: previewImage
                    source: control.imageSource
                    cache: false
                    asynchronous: true
                    fillMode: Image.Pad
                    x: Math.max(0, (imageFlickable.width - implicitWidth) / 2)
                    y: Math.max(0, (imageFlickable.height - implicitHeight) / 2)
                }
            }
        }
    }
}
