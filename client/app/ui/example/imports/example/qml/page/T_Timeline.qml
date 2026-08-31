import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

FluScrollablePage {
    title: qsTr("Timeline")

    ListModel {
        id: model
        ListElement { date: "2023-02-28"; text: "Project started" }
        ListElement { date: "2023-03-28"; text: "First public build" }
    }

    ColumnLayout {
        spacing: 10
        Repeater {
            model: model
            delegate: ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                FluText { text: model.date; font.bold: true }
                FluText { text: model.text; wrapMode: Text.WordWrap; color: FluColors.Grey120 }
                FluDivider { Layout.fillWidth: true }
            }
        }
    }
}
