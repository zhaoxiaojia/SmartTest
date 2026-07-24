import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

Item {
    id: root

    component AuditSection: FluFrame {
        default property alias sectionData: sectionColumn.data
        Layout.fillWidth: true
        implicitHeight: sectionColumn.implicitHeight + 24

        ColumnLayout {
            id: sectionColumn
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8
        }
    }

    component DetailCard: FluFrame {
        default property alias detailData: detailColumn.data
        Layout.fillWidth: true
        implicitHeight: detailColumn.implicitHeight + 16

        ColumnLayout {
            id: detailColumn
            anchors.fill: parent
            anchors.margins: 8
            spacing: 3
        }
    }

    component WrappedText: FluText {
        Layout.fillWidth: true
        wrapMode: Text.WrapAnywhere
    }

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
                WrappedText {
                    visible: JiraAuditBridge.inputError.length > 0
                    text: JiraAuditBridge.inputError
                    color: FluTheme.dark ? "#FF99A4" : "#D13438"
                }
            }

            AuditSection {
                objectName: "jiraAuditRules"

                FluText {
                    text: qsTr("Rules")
                    font: FluTextStyle.Subtitle
                }
                Repeater {
                    model: JiraAuditBridge.ruleRows

                    DetailCard {
                        required property var modelData
                        WrappedText {
                            text: modelData.rule_id + " · " + modelData.section
                                  + " · " + modelData.field
                            font: FluTextStyle.BodyStrong
                        }
                        WrappedText { text: modelData.requirement }
                        WrappedText {
                            text: modelData.guidance
                            color: FluTheme.fontSecondaryColor
                        }
                    }
                }
            }

            AuditSection {
                objectName: "jiraAuditProgress"

                RowLayout {
                    Layout.fillWidth: true
                    FluText {
                        text: qsTr("Audit Progress")
                        font: FluTextStyle.Subtitle
                    }
                    Item { Layout.fillWidth: true }
                    FluText {
                        text: JiraAuditBridge.processedCount + " / "
                              + JiraAuditBridge.totalCount
                        color: FluTheme.fontSecondaryColor
                    }
                }
                FluProgressBar {
                    Layout.fillWidth: true
                    indeterminate: JiraAuditBridge.state === "resolving"
                    value: JiraAuditBridge.progressValue
                }
                WrappedText {
                    text: JiraAuditBridge.statusText
                    color: FluTheme.fontSecondaryColor
                }
            }

            AuditSection {
                objectName: "jiraAuditResults"
                visible: JiraAuditBridge.state === "completed"

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

                        DetailCard {
                            required property var modelData
                            WrappedText {
                                text: modelData.key + " · " + modelData.rule_id
                                      + " · " + modelData.field
                                font: FluTextStyle.BodyStrong
                            }
                            WrappedText { text: modelData.reason }
                            WrappedText {
                                text: modelData.guidance
                                color: FluTheme.fontSecondaryColor
                            }
                        }
                    }
                }
            }

            AuditSection {
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
                        onClicked: FluTools.showFileInFolder(JiraAuditBridge.exportPath)
                    }
                    Item { Layout.fillWidth: true }
                }
                FluText {
                    text: qsTr("Exported file")
                    font: FluTextStyle.BodyStrong
                }
                WrappedText {
                    text: JiraAuditBridge.exportPath.length > 0
                          ? JiraAuditBridge.exportPath
                          : qsTr("No export has been created.")
                    color: FluTheme.fontSecondaryColor
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
            }
        }
    }
}
