pragma ComponentBehavior: Bound

import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

FluFrame {
    id: root
    objectName: "dailyReportWorkspace"
    padding: 16
    property string editingId: ""
    property bool adding: false
    property bool scheduling: false

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        FluText { text: qsTr("%1 projects · %2 enabled").arg(DailyReportBridge.projectCount).arg(DailyReportBridge.enabledProjectCount); color: FluTheme.fontSecondaryColor }
        RowLayout {
            objectName: "dailyReportActionBar"
            FluButton { text: qsTr("New project"); onClicked: { root.editingId = ""; root.adding = true } }
            FluButton { objectName: "dailyReportGeneratePreview"; text: qsTr("Generate previews"); enabled: DailyReportBridge.state !== "running"; onClicked: DailyReportBridge.generatePreview() }
            FluButton { objectName: "dailyReportSendNow"; text: qsTr("Send now"); enabled: DailyReportBridge.previewValid && DailyReportBridge.state !== "running"; onClicked: DailyReportBridge.sendPreview() }
            FluButton { objectName: "dailyReportSchedule"; text: qsTr("Schedule delivery"); onClicked: root.scheduling = !root.scheduling }
        }
        FluText { text: DailyReportBridge.statusText; color: FluTheme.fontSecondaryColor }
        FluProgressBar { visible: DailyReportBridge.state === "running"; indeterminate: true; Layout.fillWidth: true }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: content.implicitHeight
            clip: true
            ColumnLayout {
                id: content
                width: parent.width
                spacing: 10

                FluFrame {
                    visible: root.adding
                    Layout.fillWidth: true
                    padding: 12
                    ColumnLayout {
                        anchors.fill: parent
                        FluTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: newProjectName; Layout.fillWidth: true; placeholderText: qsTr("Project name") }
                        FluTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: newProjectSubject; Layout.fillWidth: true; placeholderText: qsTr("Email subject (optional)") }
                        FluMultilineTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: newProjectJql; Layout.fillWidth: true; placeholderText: qsTr("JQL") }
                        FluMultilineTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: newProjectTo; Layout.fillWidth: true; placeholderText: qsTr("To recipients") }
                        FluMultilineTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: newProjectCc; Layout.fillWidth: true; placeholderText: qsTr("Cc recipients") }
                        FluToggleSwitch { /* persistence-opt-out: owner:DailyReportBridge */ id: newProjectEnabled; text: qsTr("Enabled"); checked: true }
                        RowLayout {
                            FluButton {
                                text: qsTr("Save project")
                                onClicked: {
                                    DailyReportBridge.saveProject({name: newProjectName.text, subject: newProjectSubject.text, jql: newProjectJql.text, to: newProjectTo.text, cc: newProjectCc.text, enabled: newProjectEnabled.checked})
                                    root.adding = false
                                }
                            }
                        }
                    }
                }

                FluFrame {
                    visible: root.scheduling
                    Layout.fillWidth: true
                    padding: 12
                    RowLayout {
                        FluComboBox { /* persistence-opt-out: owner:DailyReportBridge */ id: cadence; model: [qsTr("Daily"), qsTr("Weekly")] }
                        FluSpinBox { /* persistence-opt-out: owner:DailyReportBridge */ id: hour; from: 0; to: 23; value: 18 }
                        FluSpinBox { /* persistence-opt-out: owner:DailyReportBridge */ id: minute; from: 0; to: 59; value: 0 }
                        FluComboBox { /* persistence-opt-out: owner:DailyReportBridge */ id: weekday; visible: cadence.currentIndex === 1; model: [qsTr("Monday"), qsTr("Tuesday"), qsTr("Wednesday"), qsTr("Thursday"), qsTr("Friday"), qsTr("Saturday"), qsTr("Sunday")] }
                        FluButton { text: qsTr("Save schedule"); onClicked: DailyReportBridge.saveSchedule({cadence: cadence.currentIndex === 0 ? "daily" : "weekly", hour: hour.value, minute: minute.value, weekday: weekday.currentIndex}) }
                    }
                }

                Repeater {
                    model: DailyReportBridge.projectRows
                    FluFrame {
                        required property var modelData
                        property bool editing: root.editingId === modelData.projectId
                        Layout.fillWidth: true
                        padding: 12
                        ColumnLayout {
                            anchors.fill: parent
                            RowLayout {
                                FluText { visible: !editing; Layout.fillWidth: true; text: modelData.projectName; font: FluTextStyle.Subtitle }
                                FluTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: editName; visible: editing; Layout.fillWidth: true; text: modelData.projectName }
                                FluToggleSwitch { /* persistence-opt-out: owner:DailyReportBridge */ id: editEnabled; checked: modelData.enabled; onClicked: if (!editing) DailyReportBridge.setProjectEnabled(modelData.projectId, checked) }
                                FluButton {
                                    text: editing ? qsTr("Save project") : qsTr("Edit")
                                    onClicked: {
                                        if (editing) {
                                            DailyReportBridge.saveProject({safe_id: modelData.projectId, name: editName.text, subject: editSubject.text, jql: editJql.text, to: editTo.text, cc: editCc.text, enabled: editEnabled.checked})
                                            root.editingId = ""
                                        } else {
                                            root.adding = false
                                            root.editingId = modelData.projectId
                                        }
                                    }
                                }
                                FluButton { visible: !editing; text: qsTr("Delete"); onClicked: DailyReportBridge.deleteProject(modelData.projectId) }
                            }
                            FluText { visible: !editing; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; text: qsTr("Subject: %1").arg(modelData.subject) }
                            FluTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: editSubject; visible: editing; Layout.fillWidth: true; text: modelData.subject; placeholderText: qsTr("Email subject") }
                            FluText { visible: !editing; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; text: qsTr("JQL: %1").arg(modelData.jql) }
                            FluMultilineTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: editJql; visible: editing; Layout.fillWidth: true; text: modelData.jql }
                            FluText { visible: !editing; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; text: qsTr("To: %1").arg(modelData.to) }
                            FluMultilineTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: editTo; visible: editing; Layout.fillWidth: true; text: modelData.to }
                            FluText { visible: !editing; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; text: qsTr("CC: %1").arg(modelData.cc) }
                            FluMultilineTextBox { /* persistence-opt-out: owner:DailyReportBridge */ id: editCc; visible: editing; Layout.fillWidth: true; text: modelData.cc }
                        }
                    }
                }
                Loader { Layout.fillWidth: true; Layout.preferredHeight: 620; active: DailyReportBridge.previewValid && DailyReportBridge.previewUrl !== ""; source: active ? "DailyReportPreview.qml" : ""; onLoaded: item.previewUrl = Qt.binding(function() { return DailyReportBridge.previewUrl }) }
            }
        }
    }
}
