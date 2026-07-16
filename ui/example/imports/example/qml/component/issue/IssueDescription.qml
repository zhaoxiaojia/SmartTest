import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

ColumnLayout {
    property string description: ""
    spacing: 7
    FluText { text: qsTr("Description"); font: FluTextStyle.BodyStrong }
    Rectangle { Layout.fillWidth: true; height: 1; color: FluTheme.dividerColor }
    FluText { objectName: "issueDescription"; Layout.fillWidth: true; text: description || qsTr("No description."); wrapMode: Text.WrapAnywhere; color: description ? FluTheme.fontPrimaryColor : FluTheme.fontSecondaryColor }
}
