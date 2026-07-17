import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0

Item {
    id: root
    objectName: "jiraIssueBrowserLayout"
    property var issues: []
    property var selectedIssue: ({})
    property var projectFilters: [qsTr("All projects")]
    property var statusFilters: [qsTr("All statuses")]
    property var typeFilters: [qsTr("All types")]
    property var filters: ({})
    property bool dataLoading: false
    property string dataStatusText: ""
    property int dataLoaded: 0
    property int dataTotal: 0
    property bool issueListCollapsed: false

    signal searchRequested(var filters)
    signal issueSelected(var issue)
    signal openIssueRequested(string issueKey, string webUrl)
    signal externalLinkRequested(string url)
    signal commentSubmitRequested(string issueKey, string content)
    signal attachmentFilesSelected(string issueKey, var fileUrls)
    signal attachmentUploadConfirmed(string issueKey, var fileUrls)

    function safeCount(value) {
        return value && value.length !== undefined ? value.length : 0
    }

    function selectedIssueIndex() {
        var key = root.selectedIssue.id || root.selectedIssue.key || ""
        if(key.length === 0) {
            return -1
        }
        for(var i = 0; i < safeCount(root.issues); ++i) {
            var row = root.issues[i] || {}
            if(row.id === key || row.key === key) {
                return i
            }
        }
        return -1
    }

    function positionText() {
        var index = selectedIssueIndex()
        if(index < 0 || safeCount(root.issues) === 0) {
            return ""
        }
        return qsTr("%1 of %2").arg(index + 1).arg(safeCount(root.issues))
    }

    function selectRelativeIssue(offset) {
        var index = selectedIssueIndex()
        if(index < 0) {
            return
        }
        var nextIndex = Math.max(0, Math.min(safeCount(root.issues) - 1, index + offset))
        if(nextIndex !== index) {
            root.issueSelected(root.issues[nextIndex])
        }
    }

    function modelIndexOf(model, value) {
        for(var i = 0; i < safeCount(model); ++i) {
            if(model[i] === value) {
                return i
            }
        }
        return -1
    }

    function applyFilterState() {
        var projectIndex = modelIndexOf(projectFilter.model, root.filters.project || qsTr("All projects"))
        var statusIndex = modelIndexOf(statusFilter.model, root.filters.status || qsTr("All statuses"))
        var typeIndex = modelIndexOf(typeFilter.model, root.filters.type || qsTr("All types"))
        projectFilter.currentIndex = Math.max(0, projectIndex)
        statusFilter.currentIndex = Math.max(0, statusIndex)
        typeFilter.currentIndex = Math.max(0, typeIndex)
        textFilter.text = root.filters.text || ""
    }

    onFiltersChanged: Qt.callLater(applyFilterState)
    onProjectFiltersChanged: Qt.callLater(applyFilterState)
    onStatusFiltersChanged: Qt.callLater(applyFilterState)
    onTypeFiltersChanged: Qt.callLater(applyFilterState)
    Component.onCompleted: Qt.callLater(applyFilterState)

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        FluFrame {
            Layout.fillWidth: true
            padding: 12
            RowLayout {
                anchors.fill: parent
                spacing: 8
                FluComboBox { id: projectFilter; Layout.preferredWidth: 220; model: safeCount(root.projectFilters) ? root.projectFilters : [qsTr("All projects")] }
                FluComboBox { id: statusFilter; Layout.preferredWidth: 140; model: safeCount(root.statusFilters) ? root.statusFilters : [qsTr("All statuses")] }
                FluComboBox { id: typeFilter; Layout.preferredWidth: 130; model: safeCount(root.typeFilters) ? root.typeFilters : [qsTr("All types")] }
                FluTextBox { id: textFilter; Layout.fillWidth: true; placeholderText: qsTr("Contains text") }
                FluFilledButton {
                    text: qsTr("Search")
                    disabled: root.dataLoading
                    onClicked: root.searchRequested({
                        "project": projectFilter.currentText,
                        "status": statusFilter.currentText,
                        "type": typeFilter.currentText,
                        "text": textFilter.text
                    })
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: root.dataLoading || root.dataStatusText.length > 0
            FluProgressRing { visible: root.dataLoading; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
            FluProgressBar {
                visible: root.dataLoading && root.dataTotal > 0
                indeterminate: false
                value: root.dataTotal > 0 ? Math.min(1, root.dataLoaded / root.dataTotal) : 0
                Layout.preferredWidth: 180
            }
            FluText { Layout.fillWidth: true; text: root.dataStatusText; color: FluTheme.fontSecondaryColor; elide: Text.ElideRight }
        }

        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            FluFrame {
                visible: !root.issueListCollapsed
                SplitView.preferredWidth: Math.max(240, root.width * 0.28)
                SplitView.minimumWidth: 220
                padding: 0
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.margins: 12
                        FluText { text: qsTr("Issues"); font: FluTextStyle.Subtitle }
                        Item { Layout.fillWidth: true }
                        FluText { text: String(safeCount(root.issues)); color: FluTheme.fontSecondaryColor }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: FluTheme.frameColor }
                    ListView {
                        id: issueList
                        objectName: "jiraIssueList"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.issues || []
                        delegate: ItemDelegate {
                            width: ListView.view.width
                            height: 64
                            highlighted: (root.selectedIssue.id || root.selectedIssue.key || "") === (modelData.id || modelData.key || "")
                            onClicked: root.issueSelected(modelData)
                            contentItem: RowLayout {
                                spacing: 8
                                FluText {
                                    text: modelData.key || ""
                                    color: FluTheme.fontPrimaryColor
                                    font.bold: true
                                }
                                FluText {
                                    Layout.fillWidth: true
                                    text: modelData.title || ""
                                    elide: Text.ElideRight
                                    color: FluTheme.fontPrimaryColor
                                }
                                FluText {
                                    text: modelData.clonedIssueKey || (modelData.cloneStatus === "not_cloned" ? qsTr("Not cloned") : "")
                                    color: modelData.clonedIssueKey ? (FluTheme.dark ? "#6EA8FE" : "#0F62FE") : FluTheme.fontSecondaryColor
                                    font: FluTextStyle.Caption
                                }
                            }
                        }
                        FluText { anchors.centerIn: parent; visible: issueList.count === 0; text: qsTr("No issues loaded"); color: FluTheme.fontSecondaryColor }
                        ScrollBar.vertical: FluScrollBar {}
                    }
                }
            }

            FluFrame {
                SplitView.fillWidth: true
                padding: 0
                JiraIssueDetailLayout {
                    anchors.fill: parent
                    issue: root.selectedIssue
                    comments: root.selectedIssue.comments || []
                    attachments: root.selectedIssue.attachments || []
                    commentsLoading: root.dataLoading && !!root.selectedIssue.key
                    attachmentsLoading: root.dataLoading && !!root.selectedIssue.key
                    positionText: root.positionText()
                    canGoPrevious: root.selectedIssueIndex() > 0
                    canGoNext: root.selectedIssueIndex() >= 0 && root.selectedIssueIndex() < safeCount(root.issues) - 1
                    onPreviousIssueRequested: root.selectRelativeIssue(-1)
                    onNextIssueRequested: root.selectRelativeIssue(1)
                    onToggleIssueListRequested: root.issueListCollapsed = !root.issueListCollapsed
                    onOpenIssueRequested: (key, url) => root.openIssueRequested(key, url)
                    onExternalLinkRequested: url => root.externalLinkRequested(url)
                    onCommentSubmitRequested: (key, content) => root.commentSubmitRequested(key, content)
                    onAttachmentFilesSelected: (key, urls) => root.attachmentFilesSelected(key, urls)
                    onAttachmentUploadConfirmed: (key, urls) => root.attachmentUploadConfirmed(key, urls)
                }
            }
        }
    }
}
