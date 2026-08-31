import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

ColumnLayout {
    id: root
    property bool running: true
    property alias value: progress.value
    property alias from: progress.from
    property alias to: progress.to
    property alias indeterminate: progress.indeterminate
    property alias strokeWidth: progress.strokeWidth
    property string text: ""
    property string status: ""
    property string statusText: ""
    property string detail: ""
    property string phase: ""
    property string error: ""
    property string errorText: ""
    spacing: 4

    FluText {
        visible: root.text.length > 0 || root.phase.length > 0
        text: root.text.length > 0 ? root.text : root.phase
        font: FluTextStyle.BodyStrong
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    FluProgressBar {
        id: progress
        visible: root.running
        Layout.fillWidth: true
    }
    FluText {
        visible: root.status.length > 0 || root.statusText.length > 0
        text: root.status.length > 0 ? root.status : root.statusText
        font: FluTextStyle.Caption
        color: FluTheme.fontSecondaryColor
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    FluText {
        visible: root.detail.length > 0
        text: root.detail
        font: FluTextStyle.Caption
        color: FluTheme.fontSecondaryColor
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    FluText {
        readonly property string message: root.error.length > 0 ? root.error : root.errorText
        visible: message.length > 0
        text: message
        font: FluTextStyle.Caption
        color: FluTheme.dark ? "#ff8a80" : "#c62828"
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
}
