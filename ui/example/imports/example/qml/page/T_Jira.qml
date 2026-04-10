import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluScrollablePage {
    title: qsTr("Jira")

    FluFrame {
        Layout.fillWidth: true
        Layout.topMargin: 20
        padding: 12

        Column {
            spacing: 10
            FluText {
                text: qsTr("Jira Integration")
                font: FluTextStyle.Subtitle
            }
            FluText {
                text: qsTr("Configure Jira connection and link test runs to issues.")
                font: FluTextStyle.Body
                wrapMode: Text.WordWrap
            }
        }
    }
}

