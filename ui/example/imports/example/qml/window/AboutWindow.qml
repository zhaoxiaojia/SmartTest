import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

FluWindow {
    id: window
    title: qsTr("About")
    width: 620
    height: 560
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
            text: qsTr("Version: %1").arg(AppInfo.version)
            font: FluTextStyle.Body
        }

        FluText {
            text: AppInfo.buildTime ? qsTr("Build time: %1").arg(AppInfo.buildTime) : qsTr("Build time: unavailable")
            font: FluTextStyle.Body
        }

        FluText {
            text: qsTr("Update checks and external links are disabled by default.")
            wrapMode: Text.WordWrap
            color: FluColors.Grey120
        }

        FluText {
            text: qsTr("about.release.v1_1_0.fixes.title")
            font: FluTextStyle.Subtitle
        }

        FluText {
            Layout.fillWidth: true
            text: qsTr("about.release.v1_1_0.fixes.body")
            wrapMode: Text.WordWrap
            font: FluTextStyle.Body
            color: FluTheme.fontSecondaryColor
        }

        FluText {
            text: qsTr("about.release.v1_1_0.new.title")
            font: FluTextStyle.Subtitle
        }

        FluText {
            Layout.fillWidth: true
            text: qsTr("about.release.v1_1_0.new.body")
            wrapMode: Text.WordWrap
            font: FluTextStyle.Body
            color: FluTheme.fontSecondaryColor
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Item { Layout.fillWidth: true }
            FluFilledButton {
                text: qsTr("OK")
                onClicked: window.close()
            }
        }
    }
}
