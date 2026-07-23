import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

ColumnLayout {
    id: root
    property var options: []
    property var value: []
    property bool disabled: false
    property string placeholderText: ""
    property bool expanded: false
    signal selectionChanged(var value)
    spacing: 2
    Rectangle {
        Layout.fillWidth: true; Layout.preferredHeight: 34; radius: 4
        color: FluTheme.dark ? "#2B2B2B" : "#FFFFFF"
        border.color: FluTheme.dark ? "#666666" : "#A0A0A0"
        FluText { anchors.left: parent.left; anchors.right: chevron.left; anchors.leftMargin: 10; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; text: root.selectedLabels() || root.placeholderText; elide: Text.ElideRight }
        FluText { id: chevron; anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; text: root.expanded ? "⌃" : "⌄" }
        MouseArea { anchors.fill: parent; enabled: !root.disabled; onClicked: root.expanded = !root.expanded }
    }
    Rectangle {
        visible: root.expanded; Layout.fillWidth: true
        Layout.preferredHeight: Math.min(200, Math.max(36, (root.options || []).length * 34))
        radius: 4; color: FluTheme.dark ? "#252525" : "#FFFFFF"; border.color: FluTheme.dark ? "#666666" : "#C8C8C8"
        ListView {
            anchors.fill: parent; anchors.margins: 2; clip: true; model: root.options || []
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width; height: 34; color: mouse.containsMouse ? (FluTheme.dark ? "#3A3A3A" : "#F1F1F1") : "transparent"
                FluText { anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; text: root.contains(modelData.value) ? "✓" : "" }
                FluText { anchors.left: parent.left; anchors.leftMargin: 30; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: modelData.label || modelData.value || ""; elide: Text.ElideRight }
                MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: root.toggle(modelData.value) }
            }
        }
    }
    function contains(candidate) { return (root.value || []).indexOf(candidate) >= 0 }
    function toggle(candidate) { var result = root.value ? root.value.slice() : []; var index = result.indexOf(candidate); if (index >= 0) result.splice(index, 1); else result.push(candidate); root.selectionChanged(result) }
    function selectedLabels() { var labels = []; for (var i = 0; i < (root.options || []).length; ++i) if (root.contains(root.options[i].value)) labels.push(root.options[i].label || root.options[i].value || ""); return labels.join(", ") }
}
