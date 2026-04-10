import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluScrollablePage {
    title: qsTr("Report")

    FluFrame {
        Layout.fillWidth: true
        Layout.topMargin: 20
        padding: 12

        Column {
            spacing: 10
            FluText {
                text: qsTr("Reports")
                font: FluTextStyle.Subtitle
            }
            FluText {
                text: qsTr("Browse historical runs and export reports.")
                font: FluTextStyle.Body
                wrapMode: Text.WordWrap
            }
        }
    }
}

