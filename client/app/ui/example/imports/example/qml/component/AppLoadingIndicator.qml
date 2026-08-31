import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

Item {
    id: root
    property bool running: true
    property string text: ""
    property string detail: ""
    property bool blocking: false
    property bool compact: true
    property bool indeterminate: true

    implicitWidth: compact ? compactContent.implicitWidth : Math.max(160, regularContent.implicitWidth)
    implicitHeight: compact ? compactContent.implicitHeight : regularContent.implicitHeight

    Rectangle {
        anchors.fill: parent
        visible: root.blocking
        color: FluTheme.dark ? "#99000000" : "#99ffffff"
        radius: 6
    }
    RowLayout {
        id: compactContent
        anchors.centerIn: parent
        visible: root.compact
        spacing: 8
        FluProgressRing {
            visible: root.running
            indeterminate: root.indeterminate
            Layout.preferredWidth: 16
            Layout.preferredHeight: 16
        }
        FluText { visible: root.text.length > 0; text: root.text; elide: Text.ElideRight }
    }
    ColumnLayout {
        id: regularContent
        anchors.centerIn: parent
        visible: !root.compact
        spacing: 5
        FluProgressRing {
            visible: root.running
            indeterminate: root.indeterminate
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
            Layout.alignment: Qt.AlignHCenter
        }
        FluText {
            visible: root.text.length > 0
            text: root.text
            font: FluTextStyle.BodyStrong
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        FluText {
            visible: root.detail.length > 0
            text: root.detail
            font: FluTextStyle.Caption
            color: FluTheme.fontSecondaryColor
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}
