import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Controls.Basic 2.15 as Basic
import QtQuick.Layouts 1.15
import FluentUI 1.0
import "../../state"

Item {
    id: root
    Loader {
        id: auditStateLoader
        active: AuthBridge.authenticated === true
                && (AuthBridge.pageStateAccount || "").length > 0
        sourceComponent: Component {
            JiraAuditWorkspaceState { account: AuthBridge.pageStateAccount }
        }
        onLoaded: auditInput.text = item.auditInput
        onActiveChanged: if (!active) {
            auditSaveTimer.stop()
            auditInput.text = ""
        }
    }
    readonly property var view: JiraAuditBridge.viewState
    Component.onDestruction: {
        if (auditSaveTimer.running && auditStateLoader.item) {
            auditStateLoader.item.auditInput = auditInput.text
            auditStateLoader.item.sync()
        }
    }
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

            FluMultilineTextBox { /* persistence-opt-out: owner:auditStateLoader */
                id: auditInput
                objectName: "jiraAuditInput"
                Layout.fillWidth: true
                Layout.preferredHeight: 92
                placeholderText: qsTr("Paste JQL or a Jira issue, filter, or search URL.")
                enabled: root.view.canStart
                onTextChanged: if (activeFocus) auditSaveTimer.restart()
            }

            Timer {
                id: auditSaveTimer
                objectName: "auditSaveTimer"
                interval: 700
                onTriggered: {
                    if (auditStateLoader.item) {
                        auditStateLoader.item.auditInput = auditInput.text
                        auditStateLoader.item.sync()
                    }
                }
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
                RowLayout {
                    Layout.fillWidth: true
                    SectionTitle { text: qsTr("Audit Progress") }
                    Item { Layout.fillWidth: true }
                    FluText {
                        text: root.view.processedCount + " / " + root.view.totalCount
                        color: FluTheme.fontSecondaryColor
                    }
                }
                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 6

                    FluProgressBar {
                        anchors.fill: parent
                        visible: root.view.state === "resolving"
                        indeterminate: true
                        strokeWidth: 6
                    }
                    Basic.ProgressBar {
                        id: auditDeterminateProgress
                        objectName: "jiraAuditDeterminateProgress"
                        anchors.fill: parent
                        visible: root.view.state !== "resolving"
                        from: 0
                        to: 1
                        value: ["awaiting_confirmation", "confirmed", "exported"].indexOf(
                                   root.view.state) >= 0 ? 1.0 : root.view.progressValue
                        padding: 0
                        background: Rectangle {
                            radius: height / 2
                            color: FluTheme.dark
                                   ? Qt.rgba(23 / 255, 34 / 255, 40 / 255, 1)
                                   : Qt.rgba(230 / 255, 247 / 255, 255 / 255, 1)
                            border.width: 1
                            border.color: FluTheme.dark
                                          ? Qt.rgba(0, 229 / 255, 1, 0.28)
                                          : Qt.rgba(0, 178 / 255, 1, 0.35)
                        }
                        contentItem: Item {
                            Rectangle {
                                objectName: "jiraAuditProgressFill"
                                width: auditDeterminateProgress.visualPosition
                                       * parent.width
                                height: parent.height
                                radius: height / 2
                                color: FluTheme.dark
                                       ? Qt.rgba(0, 229 / 255, 1, 1)
                                       : Qt.rgba(0, 178 / 255, 1, 1)
                            }
                        }
                    }
                }
                SecondaryText { text: root.view.statusText }
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
                RowLayout {
                    Layout.fillWidth: true
                    visible: root.view.violationPageCount > 1

                    Item { Layout.fillWidth: true }
                    FluButton {
                        objectName: "previousViolationPageButton"
                        text: "<"
                        disabled: root.view.violationPage <= 1
                        onClicked: JiraAuditBridge.previousViolationPage()
                    }
                    FluText {
                        text: root.view.violationPage + " / "
                              + root.view.violationPageCount
                        color: FluTheme.fontSecondaryColor
                    }
                    FluButton {
                        objectName: "nextViolationPageButton"
                        text: ">"
                        disabled: root.view.violationPage >= root.view.violationPageCount
                        onClicked: JiraAuditBridge.nextViolationPage()
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
                                Item { Layout.fillWidth: true }
                            }
                            WrappedText {
                                objectName: "observedViolationText"
                                visible: text.length > 0
                                text: modelData.observed || ""
                                font: FluTextStyle.BodyStrong
                            }
                            WrappedText {
                                objectName: "violationReasonText"
                                text: modelData.reason
                            }
                            SecondaryText {
                                objectName: "violationGuidanceText"
                                text: modelData.guidance
                            }
                            SecondaryText {
                                objectName: "violationMetadataText"
                                text: modelData.rule_id + " · " + modelData.field
                            }
                        }
                    }
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
        }
    }
}
