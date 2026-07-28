import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

Item {
    id: root
    readonly property var view: JiraAuditBridge.viewState
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
    component SecondaryText: WrappedText {
        color: FluTheme.fontSecondaryColor
    }
    component SectionTitle: FluText {
        font: FluTextStyle.Subtitle
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
                Layout.fillWidth: true
                Layout.preferredHeight: 92
                placeholderText: qsTr("Paste JQL or a Jira issue, filter, or search URL.")
                enabled: root.view.canStart
            }

            RowLayout {
                Layout.fillWidth: true

                FluFilledButton {
                    text: qsTr("Start Audit")
                    disabled: !root.view.canStart
                    onClicked: JiraAuditBridge.startAudit(auditInput.text)
                }
                WrappedText {
                    visible: root.view.inputError.length > 0
                    text: root.view.inputError
                    color: FluTheme.dark ? "#FF99A4" : "#D13438"
                }
            }

            AuditSection {
                SectionTitle { text: qsTr("Rules") }
                Repeater {
                    model: root.view.ruleRows

                    DetailCard {
                        required property var modelData
                        WrappedText {
                            text: modelData.rule_id + " · " + modelData.section
                                  + " · " + modelData.field
                            font: FluTextStyle.BodyStrong
                        }
                        WrappedText { text: modelData.requirement }
                        SecondaryText { text: modelData.guidance }
                    }
                }
            }

            AuditSection {
                RowLayout {
                    Layout.fillWidth: true
                    SectionTitle { text: qsTr("Audit Progress") }
                    Item { Layout.fillWidth: true }
                    FluText {
                        text: root.view.processedCount + " / " + root.view.totalCount
                        color: FluTheme.fontSecondaryColor
                    }
                }
                FluProgressBar {
                    Layout.fillWidth: true
                    indeterminate: root.view.state === "resolving"
                    value: root.view.progressValue
                }
                SecondaryText { text: root.view.statusText }
            }

            AuditSection {
                visible: ["awaiting_confirmation", "confirmed", "exported"].indexOf(root.view.state) >= 0

                SectionTitle { text: qsTr("Results") }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 18
                    FluText { text: qsTr("Total") + ": " + (root.view.resultSummary.totalCount || 0) }
                    FluText { text: qsTr("Passed") + ": " + (root.view.resultSummary.passedCount || 0) }
                    FluText { text: qsTr("Failed") + ": " + (root.view.resultSummary.failedCount || 0) }
                    FluText { text: qsTr("Violations") + ": " + (root.view.resultSummary.violationCount || 0) }
                    Item { Layout.fillWidth: true }
                }
                FluText {
                    visible: root.view.violationRows.length === 0
                    text: qsTr("No violations were found.")
                    color: FluTheme.fontSecondaryColor
                }
                RowLayout {
                    Layout.fillWidth: true
                    FluText {
                        text: qsTr("AI Review") + ": " + root.view.aiReviewText
                        color: FluTheme.fontSecondaryColor
                    }
                    Item { Layout.fillWidth: true }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Repeater {
                        model: root.view.violationRows

                        DetailCard {
                            required property var modelData
                            RowLayout {
                                Layout.fillWidth: true
                                FluButton {
                                    text: modelData.issueKey
                                    onClicked: Qt.openUrlExternally(modelData.issueUrl)
                                }
                                WrappedText {
                                    text: modelData.rule_id + " · " + modelData.field
                                    font: FluTextStyle.BodyStrong
                                }
                            }
                            WrappedText { text: modelData.reason }
                            SecondaryText { text: modelData.guidance }
                        }
                    }
                }
            }

            AuditSection {
                RowLayout {
                    Layout.fillWidth: true
                    FluFilledButton {
                        objectName: "confirmAuditButton"
                        text: qsTr("Confirm Audit")
                        disabled: !root.view.canConfirm
                        onClicked: JiraAuditBridge.confirmAudit()
                    }
                    FluFilledButton {
                        objectName: "exportAuditButton"
                        text: qsTr("Export XLSX")
                        disabled: !root.view.canExport
                        onClicked: JiraAuditBridge.exportReport()
                    }
                    FluButton {
                        objectName: "showAuditExportButton"
                        text: qsTr("Show in Folder")
                        disabled: root.view.exportPath.length === 0
                        onClicked: FluTools.showFileInFolder(root.view.exportPath)
                    }
                    Item { Layout.fillWidth: true }
                }
                FluText { text: qsTr("Exported file"); font: FluTextStyle.BodyStrong }
                SecondaryText {
                    text: root.view.exportPath.length > 0
                          ? root.view.exportPath
                          : qsTr("No export has been created.")
                }
            }
        }
    }
}
