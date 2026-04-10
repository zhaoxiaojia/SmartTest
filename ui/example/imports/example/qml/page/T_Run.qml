import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluScrollablePage {
    title: qsTr("Run")

    FluFrame {
        Layout.fillWidth: true
        Layout.topMargin: 20
        padding: 12

        Column {
            spacing: 12

            FluText {
                text: qsTr("Run Tests")
                font: FluTextStyle.Subtitle
            }

            Row {
                spacing: 10
                FluFilledButton {
                    text: qsTr("Start")
                }
                FluButton {
                    text: qsTr("Stop")
                }
            }

            FluText {
                text: qsTr("Execution output and progress will appear here.")
                font: FluTextStyle.Body
                wrapMode: Text.WordWrap
            }
        }
    }
}
