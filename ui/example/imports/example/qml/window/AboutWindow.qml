import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

FluWindow {
    id: window
    title: "About"
    width: 520
    height: 260
    fixSize: true
    launchMode: FluWindowType.SingleTask

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        FluText {
            text: "SmartTest"
            font: FluTextStyle.Title
        }

        FluText {
            text: "Version: %1".arg(AppInfo.version)
            font: FluTextStyle.Body
        }

        FluText {
            text: "Update checks and external links are disabled by default."
            wrapMode: Text.WordWrap
            color: FluColors.Grey120
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Item { Layout.fillWidth: true }
            FluFilledButton {
                text: "OK"
                onClicked: window.close()
            }
        }
    }
}
