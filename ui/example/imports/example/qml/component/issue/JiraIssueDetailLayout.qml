import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0

Flickable {
    id: root
    objectName: "jiraIssueDetailLayout"
    property var issue: ({})
    property var comments: []
    property var attachments: []
    property bool commentsLoading: false
    property bool commentSubmitting: false
    property bool attachmentsLoading: false
    property bool attachmentUploading: false
    property string commentError: ""
    property string attachmentError: ""
    property string positionText: ""
    property bool canGoPrevious: false
    property bool canGoNext: false
    property var pendingDropUrls: []

    signal openIssueRequested(string issueKey, string webUrl)
    signal externalLinkRequested(string url)
    signal previousIssueRequested()
    signal nextIssueRequested()
    signal toggleIssueListRequested()
    signal commentSubmitRequested(string issueKey, string content)
    signal attachmentFilesSelected(string issueKey, var fileUrls)
    signal attachmentUploadConfirmed(string issueKey, var fileUrls)
    signal attachmentOpenRequested(string issueKey, var attachment)

    contentWidth: width
    contentHeight: content.implicitHeight + 32
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: FluScrollBar {}

    function selectAttachmentFiles(fileUrls) { attachmentsView.selectFiles(fileUrls) }
    function stageDroppedFiles(fileUrls) { if (attachmentUploading) return; pendingDropUrls = attachmentsView.localFiles(fileUrls); if (pendingDropUrls.length > 0) uploadDialog.open() }
    function confirmDroppedFiles() { if (!attachmentUploading && pendingDropUrls.length > 0) attachmentUploadConfirmed(issue.key || "", pendingDropUrls); pendingDropUrls = [] }
    function cancelDroppedFiles() { pendingDropUrls = []; uploadDialog.close() }

    DropArea { anchors.fill: parent; enabled: !root.attachmentUploading; onDropped: event => { if (event.hasUrls) root.stageDroppedFiles(event.urls) } }
    FluContentDialog { id: uploadDialog; objectName: "issueUploadConfirmDialog"; title: qsTr("Confirm upload"); message: qsTr("Upload the dropped files?"); positiveText: qsTr("Upload"); negativeText: qsTr("Cancel"); onPositiveClicked: root.confirmDroppedFiles(); onNegativeClicked: root.cancelDroppedFiles() }

    ColumnLayout {
        id: content
        width: root.width - 40
        x: 20
        y: 16
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Item {
                Layout.preferredWidth: 42
                Layout.preferredHeight: 42
                Layout.alignment: Qt.AlignTop
                Image { anchors.fill: parent; visible: !!root.issue.typeIcon; source: root.issue.typeIcon || ""; fillMode: Image.PreserveAspectFit }
                Rectangle { anchors.fill: parent; visible: !root.issue.typeIcon; radius: 4; color: FluTheme.dark ? "#1F2A44" : "#172B4D" }
                Rectangle { visible: !root.issue.typeIcon; width: 22; height: 26; radius: 3; color: "#FF5630"; anchors.centerIn: parent }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Repeater {
                        model: (root.issue.projectPath && root.issue.projectPath.length) ? root.issue.projectPath : (root.issue.projectName ? [{"label": root.issue.projectName, "url": root.issue.projectUrl || ""}] : [])
                        RowLayout {
                            spacing: 6
                            FluText { visible: index > 0; text: "/"; color: FluTheme.fontSecondaryColor }
                            FluText {
                                text: modelData.label || modelData.value || ""
                                font: FluTextStyle.Caption
                                color: modelData.url ? (FluTheme.dark ? "#6EA8FE" : "#0F62FE") : FluTheme.fontSecondaryColor
                                MouseArea { anchors.fill: parent; enabled: !!modelData.url; cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: root.externalLinkRequested(modelData.url) }
                            }
                        }
                    }

                    FluText {
                        text: root.issue.key || ""
                        font: FluTextStyle.Caption
                        color: FluTheme.dark ? "#6EA8FE" : "#0F62FE"
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.openIssueRequested(root.issue.key || "", root.issue.webUrl || "") }
                    }

                    Item { Layout.fillWidth: true }

                    FluText {
                        text: root.positionText
                        font: FluTextStyle.Caption
                        color: FluTheme.fontSecondaryColor
                    }

                    FluIconButton { Layout.preferredWidth: 24; Layout.preferredHeight: 24; iconSource: FluentIcons.ChevronUp; iconSize: 12; normalColor: "transparent"; disabled: !root.canGoPrevious; onClicked: root.previousIssueRequested() }
                    FluIconButton { Layout.preferredWidth: 24; Layout.preferredHeight: 24; iconSource: FluentIcons.ChevronDown; iconSize: 12; normalColor: "transparent"; disabled: !root.canGoNext; onClicked: root.nextIssueRequested() }
                    FluIconButton { Layout.preferredWidth: 24; Layout.preferredHeight: 24; iconSource: FluentIcons.FullScreen; iconSize: 12; normalColor: "transparent"; disabled: !(root.issue.key || ""); onClicked: root.toggleIssueListRequested() }
                }

                FluText {
                    Layout.fillWidth: true
                    text: root.issue.title || qsTr("No issue selected")
                    font: FluTextStyle.Title
                    color: FluTheme.fontPrimaryColor
                    wrapMode: Text.WordWrap
                    MouseArea { anchors.fill: parent; enabled: !!root.issue.webUrl; cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: root.openIssueRequested(root.issue.key || "", root.issue.webUrl || "") }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 24
            Layout.alignment: Qt.AlignTop
            ColumnLayout {
                Layout.preferredWidth: (content.width - 24) * 0.68
                Layout.maximumWidth: Layout.preferredWidth
                Layout.alignment: Qt.AlignTop
                spacing: 18

                JiraIssueSection {
                    Layout.fillWidth: true
                    title: qsTr("Details")
                    IssueFieldSection { Layout.fillWidth: true; title: ""; fields: root.issue.detailsFields || []; onExternalLinkRequested: url => root.externalLinkRequested(url) }
                }

                JiraIssueSection {
                    Layout.fillWidth: true
                    title: qsTr("Description")
                    IssueDescription { Layout.fillWidth: true; showTitle: false; description: root.issue.description || "" }
                }

                JiraIssueSection {
                    Layout.fillWidth: true
                    title: qsTr("Attachments")
                    IssueAttachments { id: attachmentsView; Layout.fillWidth: true; showTitle: false; issueKey: root.issue.key || ""; attachments: root.attachments; loading: root.attachmentsLoading; uploading: root.attachmentUploading; error: root.attachmentError; onFilesSelected: (key, urls) => root.attachmentFilesSelected(key, urls); onAttachmentOpenRequested: (key, row) => root.attachmentOpenRequested(key, row) }
                }

                JiraIssueSection {
                    Layout.fillWidth: true
                    title: qsTr("Activity")
                    IssueComments { Layout.fillWidth: true; showTitle: false; issueKey: root.issue.key || ""; comments: root.comments; loading: root.commentsLoading; submitting: root.commentSubmitting; error: root.commentError; onSubmitRequested: (key, text) => root.commentSubmitRequested(key, text) }
                }
            }
            ColumnLayout {
                Layout.preferredWidth: (content.width - 24) * 0.32
                Layout.maximumWidth: Layout.preferredWidth
                Layout.alignment: Qt.AlignTop
                spacing: 18

                JiraIssueSection {
                    Layout.fillWidth: true
                    title: qsTr("People")
                    IssueFieldSection { Layout.fillWidth: true; title: ""; fields: root.issue.peopleFields || []; onExternalLinkRequested: url => root.externalLinkRequested(url) }
                }

                JiraIssueSection {
                    Layout.fillWidth: true
                    title: qsTr("Dates")
                    IssueFieldSection { Layout.fillWidth: true; title: ""; fields: root.issue.dateFields || []; onExternalLinkRequested: url => root.externalLinkRequested(url) }
                }

                Repeater {
                    model: root.issue.extraSections || []
                    JiraIssueSection {
                        Layout.fillWidth: true
                        title: modelData.title || ""
                        IssueFieldSection { Layout.fillWidth: true; title: ""; fields: modelData.fields || []; onExternalLinkRequested: url => root.externalLinkRequested(url) }
                    }
                }
            }
        }
    }
}
