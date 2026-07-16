import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../issue"

Item {
    id: root
    property var issues: []
    property var selectedIssue: ({})
    signal searchRequested(var filters)
    signal issueSelected(var issue)
    signal openIssueRequested(string issueKey, string webUrl)
    signal commentSubmitRequested(string issueKey, string content)
    signal attachmentFilesSelected(string issueKey, var fileUrls)
    signal attachmentUploadConfirmed(string issueKey, var fileUrls)

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        FluFrame {
            Layout.fillWidth: true
            padding: 12
            RowLayout {
                anchors.fill: parent
                spacing: 8
                FluComboBox { id: projectFilter; Layout.preferredWidth: 150; model: [qsTr("Project")] }
                FluComboBox { id: statusFilter; Layout.preferredWidth: 120; model: [qsTr("Status")] }
                FluComboBox { id: typeFilter; Layout.preferredWidth: 130; model: [qsTr("Issue type")] }
                FluComboBox { id: assigneeFilter; Layout.preferredWidth: 140; model: [qsTr("Assignee")] }
                FluTextBox { id: textFilter; Layout.fillWidth: true; placeholderText: qsTr("Contains text") }
                FluFilledButton {
                    text: qsTr("Search")
                    onClicked: root.searchRequested({
                        "project": projectFilter.currentText,
                        "status": statusFilter.currentText,
                        "type": typeFilter.currentText,
                        "assignee": assigneeFilter.currentText,
                        "text": textFilter.text
                    })
                }
            }
        }

        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            FluFrame {
                SplitView.preferredWidth: Math.max(240, root.width * 0.28)
                SplitView.minimumWidth: 220
                padding: 0
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true; Layout.margins: 12
                        FluText { text: qsTr("Issues"); font: FluTextStyle.Subtitle }
                        Item { Layout.fillWidth: true }
                        FluText { text: root.issues.length; color: FluTheme.fontSecondaryColor }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: FluTheme.frameColor }
                    ListView {
                        id: issueList
                        objectName: "redmineIssueList"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.issues
                        delegate: ItemDelegate {
                            width: ListView.view.width
                            height: 64
                            text: (modelData.key || "") + (modelData.title ? "  " + modelData.title : "")
                            onClicked: { root.selectedIssue = modelData; root.issueSelected(modelData) }
                        }
                        FluText {
                            anchors.centerIn: parent
                            visible: issueList.count === 0
                            text: qsTr("No issues loaded")
                            color: FluTheme.fontSecondaryColor
                        }
                        ScrollBar.vertical: FluScrollBar {}
                    }
                }
            }

            FluFrame {
                SplitView.fillWidth: true
                padding: 0
                IssueDetailView {
                    anchors.fill: parent
                    issue: root.selectedIssue
                    comments: []
                    attachments: []
                    onOpenIssueRequested: (key, url) => root.openIssueRequested(key, url)
                    onCommentSubmitRequested: (key, content) => root.commentSubmitRequested(key, content)
                    onAttachmentFilesSelected: (key, urls) => root.attachmentFilesSelected(key, urls)
                    onAttachmentUploadConfirmed: (key, urls) => root.attachmentUploadConfirmed(key, urls)
                }
            }
        }
    }
}
