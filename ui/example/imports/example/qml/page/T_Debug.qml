import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluScrollablePage {
    title: qsTr("Debug")

    FluFrame {
        Layout.fillWidth: true
        Layout.topMargin: 20
        padding: 12

        Column {
            spacing: 10
            FluText {
                text: qsTr("Debug Tools")
                font: FluTextStyle.Subtitle
            }
            FluText {
                text: qsTr("Diagnostics, logs, and utilities go here.")
                font: FluTextStyle.Body
                wrapMode: Text.WordWrap
            }
        }
    }
}

