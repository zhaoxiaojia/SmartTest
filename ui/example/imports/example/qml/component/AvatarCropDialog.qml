import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

FluPopup {
    id: cropDialog
    objectName: "avatarCropDialog"
    anchors.centerIn: Overlay.overlay
    width: 380
    height: 490
    modal: true
    focus: true
    leftPadding: 20
    rightPadding: 20
    topPadding: 20
    bottomPadding: 28
    closePolicy: Popup.NoAutoClose
    property url sourceUrl: ""
    signal cropAccepted(url source, real horizontalPosition, real verticalPosition, real cropScale)

    function clampImage(){
        cropImage.x = Math.min(0, Math.max(cropViewport.width - cropImage.width, cropImage.x))
        cropImage.y = Math.min(0, Math.max(cropViewport.height - cropImage.height, cropImage.y))
    }

    function centerImage(){
        cropImage.x = (cropViewport.width - cropImage.width) / 2
        cropImage.y = (cropViewport.height - cropImage.height) / 2
        clampImage()
    }

    function openForSource(source){
        sourceUrl = source
        zoomSlider.value = 1
        open()
        Qt.callLater(centerImage)
    }

    function cancelCrop(){
        close()
    }

    background: Rectangle {
        radius: 12
        color: FluTheme.dark ? "#25272B" : "#FFFFFF"
        border.width: 1
        border.color: FluTheme.dark ? "#454A52" : "#DDE2E8"
    }

    contentItem: Item {
        id: cropContent
        objectName: "avatarCropContent"
        clip: true
        FluText {
            id: cropTitle
            objectName: "avatarCropTitle"
            text: qsTr("Crop Avatar")
            font: FluTextStyle.Title
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 24
        }
        Item {
            id: cropViewport
            objectName: "avatarCropViewport"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: cropTitle.bottom
            anchors.topMargin: 14
            width: 300
            height: 300
            clip: true
            layer.enabled: true
            Rectangle { anchors.fill: parent; color: FluTheme.dark ? "#15171A" : "#EEF1F5" }
            Image {
                id: cropImage
                objectName: "avatarCropImage"
                source: cropDialog.sourceUrl
                asynchronous: false
                cache: false
                property real baseScale: sourceSize.width > 0 && sourceSize.height > 0
                                         ? Math.max(cropViewport.width / sourceSize.width,
                                                    cropViewport.height / sourceSize.height)
                                         : 1
                width: Math.max(cropViewport.width, sourceSize.width * baseScale * zoomSlider.value)
                height: Math.max(cropViewport.height, sourceSize.height * baseScale * zoomSlider.value)
                fillMode: Image.Stretch
                onStatusChanged: if(status === Image.Ready) Qt.callLater(cropDialog.centerImage)
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.SizeAllCursor
                drag.target: cropImage
                drag.minimumX: cropViewport.width - cropImage.width
                drag.maximumX: 0
                drag.minimumY: cropViewport.height - cropImage.height
                drag.maximumY: 0
                onReleased: cropDialog.clampImage()
            }
            Rectangle {
                anchors.fill: parent
                color: "transparent"
                border.width: 2
                border.color: FluTheme.dark ? "#FFFFFF" : "#1677FF"
                radius: 4
            }
        }
        RowLayout {
            id: zoomControls
            objectName: "avatarCropZoomControls"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: cropViewport.bottom
            anchors.topMargin: 12
            height: 30
            FluIcon { iconSource: FluentIcons.ZoomOut; iconSize: 14 }
            FluSlider {
                id: zoomSlider
                objectName: "avatarCropZoomSlider"
                Layout.fillWidth: true
                from: 1
                to: 4
                value: 1
                stepSize: 0.05
                onMoved: Qt.callLater(cropDialog.centerImage)
            }
            FluIcon { iconSource: FluentIcons.ZoomIn; iconSize: 14 }
        }
        RowLayout {
            id: cropActions
            objectName: "avatarCropActions"
            anchors.right: parent.right
            anchors.top: zoomControls.bottom
            anchors.topMargin: 10
            height: 34
            FluButton {
                objectName: "avatarCropCancelButton"
                text: qsTr("Cancel")
                onClicked: cropDialog.cancelCrop()
            }
            FluFilledButton {
                objectName: "avatarCropApplyButton"
                text: qsTr("Apply")
                enabled: cropImage.status === Image.Ready
                onClicked: {
                    var horizontalRange = Math.max(1, cropImage.width - cropViewport.width)
                    var verticalRange = Math.max(1, cropImage.height - cropViewport.height)
                    cropDialog.cropAccepted(
                        cropDialog.sourceUrl,
                        Math.min(1, Math.max(0, -cropImage.x / horizontalRange)),
                        Math.min(1, Math.max(0, -cropImage.y / verticalRange)),
                        1 / zoomSlider.value
                    )
                    cropDialog.close()
                }
            }
        }
    }
}
