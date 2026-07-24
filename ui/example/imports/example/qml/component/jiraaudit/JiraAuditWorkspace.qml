import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

Item {
    id: root

    Flickable {
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: contentColumn.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: FluScrollBar {}

        ColumnLayout {
            id: contentColumn
            width: parent.width
            spacing: 14

            FluText {
                text: qsTr("JQL or Jira URL")
                font: FluTextStyle.BodyStrong
            }

            FluMultilineTextBox {
                id: auditInput
                objectName: "jiraAuditInput"
                Layout.fillWidth: true
                Layout.preferredHeight: 92
                placeholderText: qsTr("Paste JQL or a Jira issue, filter, or search URL.")
                enabled: JiraAuditBridge.canStart
            }

            RowLayout {
                Layout.fillWidth: true

                FluFilledButton {
                    objectName: "jiraAuditStart"
                    text: qsTr("Start Audit")
                    disabled: !JiraAuditBridge.canStart
                    onClicked: JiraAuditBridge.startAudit(auditInput.text)
                }

                FluText {
                    Layout.fillWidth: true
                    visible: JiraAuditBridge.inputError.length > 0
                    text: JiraAuditBridge.inputError
                    color: FluTheme.dark ? "#FF99A4" : "#D13438"
                    wrapMode: Text.WrapAnywhere
                }
            }

            Rectangle {
                objectName: "jiraAuditRules"
                Layout.fillWidth: true
                implicitHeight: ruleColumn.implicitHeight + 24
                radius: 6
                color: FluTheme.frameColor
                border.color: FluTheme.dividerColor

                ColumnLayout {
                    id: ruleColumn
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    FluText {
                        text: qsTr("Rules")
                        font: FluTextStyle.Subtitle
                    }

                    Repeater {
                        model: JiraAuditBridge.ruleRows

                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: ruleRow.implicitHeight + 16
                            radius: 4
                            color: "transparent"
                            border.color: FluTheme.dividerColor

                            ColumnLayout {
                                id: ruleRow
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 3

                                FluText {
                                    Layout.fillWidth: true
                                    text: modelData.ruleId + " · " + modelData.section + " · " + modelData.field
                                    font: FluTextStyle.BodyStrong
                                    wrapMode: Text.WrapAnywhere
                                }
                                FluText {
                                    Layout.fillWidth: true
                                    text: modelData.requirement
                                    wrapMode: Text.WrapAnywhere
                                }
                                FluText {
                                    Layout.fillWidth: true
                                    text: modelData.guidance
                                    color: FluTheme.fontSecondaryColor
                                    wrapMode: Text.WrapAnywhere
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                objectName: "jiraAuditProgress"
                Layout.fillWidth: true
                implicitHeight: progressColumn.implicitHeight + 24
                radius: 6
                color: FluTheme.frameColor
                border.color: FluTheme.dividerColor

                ColumnLayout {
                    id: progressColumn
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        FluText {
                            text: qsTr("Audit Progress")
                            font: FluTextStyle.Subtitle
                        }
                        Item { Layout.fillWidth: true }
                        FluText {
                            text: JiraAuditBridge.processedCount + " / " + JiraAuditBridge.totalCount
                            color: FluTheme.fontSecondaryColor
                        }
                    }
                    FluProgressBar {
                        Layout.fillWidth: true
                        indeterminate: JiraAuditBridge.state === "resolving"
                        value: JiraAuditBridge.progressValue
                    }
                    FluText {
                        Layout.fillWidth: true
                        text: JiraAuditBridge.statusText
                        color: FluTheme.fontSecondaryColor
                        wrapMode: Text.WrapAnywhere
                    }
                }
            }

            Rectangle {
                objectName: "jiraAuditResults"
                Layout.fillWidth: true
                visible: JiraAuditBridge.state === "completed"
                implicitHeight: resultsColumn.implicitHeight + 24
                radius: 6
                color: FluTheme.frameColor
                border.color: FluTheme.dividerColor

                ColumnLayout {
                    id: resultsColumn
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    FluText {
                        text: qsTr("Results")
                        font: FluTextStyle.Subtitle
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 18
                        FluText { text: qsTr("Total") + ": " + (JiraAuditBridge.resultSummary.totalCount || 0) }
                        FluText { text: qsTr("Passed") + ": " + (JiraAuditBridge.resultSummary.passedCount || 0) }
                        FluText { text: qsTr("Failed") + ": " + (JiraAuditBridge.resultSummary.failedCount || 0) }
                        FluText { text: qsTr("Violations") + ": " + (JiraAuditBridge.resultSummary.violationCount || 0) }
                        Item { Layout.fillWidth: true }
                    }

                    FluText {
                        visible: JiraAuditBridge.violationRows.length === 0
                        text: qsTr("No violations were found.")
                        color: FluTheme.fontSecondaryColor
                    }

                    ColumnLayout {
                        objectName: "jiraAuditViolations"
                        Layout.fillWidth: true
                        spacing: 6

                        Repeater {
                            model: JiraAuditBridge.violationRows

                            Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                implicitHeight: violationColumn.implicitHeight + 16
                                radius: 4
                                color: "transparent"
                                border.color: FluTheme.dividerColor

                                ColumnLayout {
                                    id: violationColumn
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 3
                                    FluText {
                                        Layout.fillWidth: true
                                        text: modelData.key + " · " + modelData.ruleId + " · " + modelData.field
                                        font: FluTextStyle.BodyStrong
                                        wrapMode: Text.WrapAnywhere
                                    }
                                    FluText {
                                        Layout.fillWidth: true
                                        text: modelData.reason
                                        wrapMode: Text.WrapAnywhere
                                    }
                                    FluText {
                                        Layout.fillWidth: true
                                        text: modelData.guidance
                                        color: FluTheme.fontSecondaryColor
                                        wrapMode: Text.WrapAnywhere
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: exportColumn.implicitHeight + 24
                radius: 6
                color: FluTheme.frameColor
                border.color: FluTheme.dividerColor

                ColumnLayout {
                    id: exportColumn
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        FluFilledButton {
                            objectName: "jiraAuditExport"
                            text: qsTr("Export XLSX")
                            disabled: !JiraAuditBridge.canExport
                            onClicked: JiraAuditBridge.exportReport()
                        }
                        FluButton {
                            objectName: "jiraAuditReveal"
                            text: qsTr("Show in Folder")
                            disabled: JiraAuditBridge.exportPath.length === 0
                            onClicked: JiraAuditBridge.revealExport()
                        }
                        Item { Layout.fillWidth: true }
                    }
                    FluText {
                        text: qsTr("Exported file")
                        font: FluTextStyle.BodyStrong
                    }
                    FluText {
                        Layout.fillWidth: true
                        text: JiraAuditBridge.exportPath.length > 0
                              ? JiraAuditBridge.exportPath
                              : qsTr("No export has been created.")
                        color: FluTheme.fontSecondaryColor
                        wrapMode: Text.WrapAnywhere
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
            }
        }
    }
}
