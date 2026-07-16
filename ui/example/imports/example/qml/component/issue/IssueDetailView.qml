import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0

Flickable {
    id: root
    objectName: "issueDetailRoot"
    property var issue: ({})
    property var comments: []
    property var attachments: []
    property bool commentsLoading: false
    property bool commentSubmitting: false
    property bool attachmentsLoading: false
    property bool attachmentUploading: false
    property string commentError: ""
    property string attachmentError: ""
    property var pendingDropUrls: []
    signal openIssueRequested(string issueKey, string webUrl)
    signal externalLinkRequested(string url)
    signal commentSubmitRequested(string issueKey, string content)
    signal attachmentFilesSelected(string issueKey, var fileUrls)
    signal attachmentUploadConfirmed(string issueKey, var fileUrls)
    signal attachmentOpenRequested(string issueKey, var attachment)
    contentWidth: width
    contentHeight: content.implicitHeight + 32
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: FluScrollBar {}
    function clearCommentDraft() { commentsView.clearDraft() }
    function selectAttachmentFiles(fileUrls) { attachmentsView.selectFiles(fileUrls) }
    function stageDroppedFiles(fileUrls) { if (attachmentUploading) return; pendingDropUrls = attachmentsView.localFiles(fileUrls); if (pendingDropUrls.length > 0) uploadDialog.open() }
    function confirmDroppedFiles() { if (!attachmentUploading && pendingDropUrls.length > 0) attachmentUploadConfirmed(issue.key || "", pendingDropUrls); pendingDropUrls = [] }
    function cancelDroppedFiles() { pendingDropUrls = []; uploadDialog.close() }

    DropArea { anchors.fill: parent; enabled: !root.attachmentUploading; onDropped: event => { if (event.hasUrls) root.stageDroppedFiles(event.urls) } }
    FluContentDialog { id: uploadDialog; objectName: "issueUploadConfirmDialog"; title: qsTr("Confirm upload"); message: qsTr("Upload the dropped files?"); positiveText: qsTr("Upload"); negativeText: qsTr("Cancel"); onPositiveClicked: root.confirmDroppedFiles(); onNegativeClicked: root.cancelDroppedFiles() }
    ColumnLayout {
        id: content
        width: root.width - 40
        x: 20; y: 16; spacing: 18
        IssueHeader { Layout.fillWidth: true; issue: root.issue; onOpenRequested: (key,url) => root.openIssueRequested(key,url); onExternalLinkRequested: url => root.externalLinkRequested(url) }
        RowLayout {
            Layout.fillWidth: true; spacing: 24; Layout.alignment: Qt.AlignTop
            ColumnLayout { id: left; objectName: "issueDetailLeftColumn"; Layout.preferredWidth: (content.width - 24) * 0.68; Layout.maximumWidth: Layout.preferredWidth; Layout.alignment: Qt.AlignTop; IssueFieldSection { Layout.fillWidth: true; title: qsTr("Details"); fields: root.issue.detailsFields || []; onExternalLinkRequested: url => root.externalLinkRequested(url) } }
            ColumnLayout { id: right; objectName: "issueDetailRightColumn"; Layout.preferredWidth: (content.width - 24) * 0.32; Layout.maximumWidth: Layout.preferredWidth; Layout.alignment: Qt.AlignTop; IssueFieldSection { Layout.fillWidth: true; title: qsTr("People"); fields: root.issue.peopleFields || []; onExternalLinkRequested: url => root.externalLinkRequested(url) } IssueFieldSection { Layout.fillWidth: true; title: qsTr("Dates"); fields: root.issue.dateFields || []; onExternalLinkRequested: url => root.externalLinkRequested(url) } Repeater { model: root.issue.extraSections || []; IssueFieldSection { Layout.fillWidth: true; title: modelData.title || ""; fields: modelData.fields || []; onExternalLinkRequested: url => root.externalLinkRequested(url) } } }
        }
        IssueDescription { Layout.fillWidth: true; description: root.issue.description || "" }
        IssueAttachments { id: attachmentsView; Layout.fillWidth: true; issueKey: root.issue.key || ""; attachments: root.attachments; loading: root.attachmentsLoading; uploading: root.attachmentUploading; error: root.attachmentError; onFilesSelected: (key,urls) => root.attachmentFilesSelected(key,urls); onAttachmentOpenRequested: (key,row) => root.attachmentOpenRequested(key,row) }
        IssueComments { id: commentsView; Layout.fillWidth: true; issueKey: root.issue.key || ""; comments: root.comments; loading: root.commentsLoading; submitting: root.commentSubmitting; error: root.commentError; onSubmitRequested: (key,text) => root.commentSubmitRequested(key,text) }
    }
}
