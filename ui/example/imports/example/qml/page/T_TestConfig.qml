import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluScrollablePage {
    title: qsTr("TestConfig")

    FluFrame {
        Layout.fillWidth: true
        Layout.topMargin: 20
        padding: 12
        Column {
            spacing: 10
            FluText {
                text: qsTr("Test Configuration")
                font: FluTextStyle.Subtitle
            }
            FluText {
                text: qsTr("Configure test targets, environments, and parameters here.")
                font: FluTextStyle.Body
                wrapMode: Text.WordWrap
            }
        }
    }
}

