import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0

Item {
    id: root
    objectName: "jiraIssueBrowserLayout"
    property var issues: []
    property var selectedIssue: ({})
    property var actionableIssues: []
    property var projectFilters: [qsTr("All projects")]
    property var statusFilters: [qsTr("All statuses")]
    property var typeFilters: [qsTr("All types")]
    property var filters: ({})
    property bool dataLoading: false
    property string dataStatusText: ""
    property int dataLoaded: 0
    property int dataTotal: 0
    property bool issueListCollapsed: false
    property var quickViews: []
    property string activeQuickViewId: ""
    property string watchedIssueText: ""
    property string watchedIssueError: ""
    property var projectOptions: []
    property bool projectsLoading: false
    property bool projectsReady: true
    property string projectsStatusText: ""
    property bool searchLoading: false
    property bool searchCanCancel: false
    property bool cloneSelectionMode: false
    property bool cloneSelectable: false
    property var cloneSelectedIds: []

    signal searchRequested(var filters)
    signal quickViewRequested(string quickViewId)
    signal watchedIssueIdsSaved(string text)
    signal cancelSearchRequested()
    signal issueSelected(var issue)
    signal openIssueRequested(string issueKey, string webUrl)
    signal externalLinkRequested(string url)
    signal commentSubmitRequested(string issueKey, string content)
    signal attachmentFilesSelected(string issueKey, var fileUrls)
    signal attachmentUploadConfirmed(string issueKey, var fileUrls)
    signal cloneSelectionRequested()
    signal cloneSelectionToggled(string issueId, bool selected)
    signal cloneSelectionCancelled()
    signal cloneSelectionConfirmed()

    function safeCount(value) {
        return value && value.length !== undefined ? value.length : 0
    }

    function partyLabel(row) {
        if((row || {}).responsibilityType === "unassigned") return qsTr("Unassigned")
        if((row || {}).updateParty === "customer") return qsTr("Customer inactivity")
        if((row || {}).updateParty === "amlogic") return qsTr("AML inactivity")
        return ""
    }

    function staleLabel(row) {
        if((row || {}).staleType === "stale_amlogic") return qsTr("Stale AML issue")
        if((row || {}).staleType === "stale_customer") return qsTr("Stale customer issue")
        return ""
    }

    function actionLabel(row) {
        var labels = []
        var party = partyLabel(row)
        var stale = staleLabel(row)
        if(party.length) labels.push(party)
        if(stale.length) labels.push(stale)
        return labels.join(" · ")
    }

    function responsibilityColor(row) {
        if((row || {}).responsibilityType === "unassigned") return FluTheme.dark ? "#8A8886" : "#605E5C"
        if((row || {}).updateParty === "customer") return FluTheme.dark ? "#F6A800" : "#A15C00"
        return FluTheme.dark ? "#6EA8FE" : "#0F62FE"
    }

    function responsibilityFill(row) {
        if((row || {}).responsibilityType === "unassigned") return FluTheme.dark ? "#343434" : "#F3F2F1"
        if((row || {}).updateParty === "customer") return FluTheme.dark ? "#4A3510" : "#FFF4CE"
        return FluTheme.dark ? "#17365D" : "#E5F1FB"
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

    function modelIndexById(model, value) {
        for(var i = 0; i < safeCount(model); ++i) {
            if((model[i].id || "") === value) return i
        }
        return -1
    }

    function selectedProjectId() {
        if(safeCount(root.projectOptions)) return projectFilter.currentValue || ""
        return projectFilter.currentText === qsTr("All projects") ? "" : projectFilter.currentText
    }

    function applyFilterState() {
        var wantedProject = root.filters.project || ""
        var statusIndex = modelIndexOf(statusFilter.model, root.filters.status || qsTr("All statuses"))
        var typeIndex = modelIndexOf(typeFilter.model, root.filters.type || qsTr("All types"))
        if(safeCount(root.projectOptions)) {
            projectFilter.currentIndex = Math.max(0, modelIndexById(projectFilter.model, wantedProject))
        } else {
            projectFilter.currentIndex = Math.max(0, modelIndexOf(projectFilter.model, wantedProject || qsTr("All projects")))
        }
        statusFilter.currentIndex = Math.max(0, statusIndex)
        typeFilter.currentIndex = Math.max(0, typeIndex)
        textFilter.text = root.filters.text || ""
        subjectFilter.text = root.filters.subject || ""
    }

    onFiltersChanged: Qt.callLater(applyFilterState)
    onProjectFiltersChanged: Qt.callLater(applyFilterState)
    onProjectOptionsChanged: Qt.callLater(applyFilterState)
    onStatusFiltersChanged: Qt.callLater(applyFilterState)
    onTypeFiltersChanged: Qt.callLater(applyFilterState)
    Component.onCompleted: Qt.callLater(applyFilterState)

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        FluFrame {
            Layout.fillWidth: true
            padding: 12
            ColumnLayout {
                anchors.fill: parent
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    visible: safeCount(root.quickViews) > 0
                    FluText { text: qsTr("Quick views"); font: FluTextStyle.Caption }
                    Repeater {
                        model: root.quickViews
                        FluButton { text: modelData.label || modelData.name || ""; onClicked: root.quickViewRequested(modelData.id || "") }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    FluComboBox {
                        id: projectFilter
                        Layout.preferredWidth: 420
                        Layout.minimumWidth: 320
                        textRole: safeCount(root.projectOptions) ? "label" : ""
                        valueRole: safeCount(root.projectOptions) ? "id" : ""
                        model: safeCount(root.projectOptions) ? root.projectOptions : (safeCount(root.projectFilters) ? root.projectFilters : [qsTr("All projects")])
                        popup.width: Math.max(width, 640)
                        ToolTip.visible: hovered
                        ToolTip.text: displayText
                    }
                    FluComboBox { id: statusFilter; Layout.preferredWidth: 140; model: safeCount(root.statusFilters) ? root.statusFilters : [qsTr("All statuses")] }
                    FluComboBox { id: typeFilter; Layout.preferredWidth: 130; model: safeCount(root.typeFilters) ? root.typeFilters : [qsTr("All types")] }
                    FluTextBox { id: subjectFilter; Layout.preferredWidth: 180; placeholderText: qsTr("Subject") }
                    FluTextBox { id: textFilter; Layout.fillWidth: true; placeholderText: qsTr("Contains text") }
                    FluFilledButton {
                        text: qsTr("Search")
                        disabled: root.searchLoading || root.projectsLoading || !root.projectsReady
                        onClicked: root.searchRequested({
                            "project": root.selectedProjectId(),
                            "status": statusFilter.currentText,
                            "type": typeFilter.currentText,
                            "subject": subjectFilter.text,
                            "text": textFilter.text
                        })
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: root.activeQuickViewId === "watched"
                    FluTextBox { id: watchedIds; Layout.fillWidth: true; text: root.watchedIssueText; placeholderText: qsTr("Watched issue IDs") }
                    FluFilledButton { text: qsTr("Save watched IDs"); onClicked: root.watchedIssueIdsSaved(watchedIds.text) }
                    FluText { visible: root.watchedIssueError.length > 0; text: root.watchedIssueError; color: "#D13438"; wrapMode: Text.Wrap }
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
            FluButton {
                visible: root.searchCanCancel
                text: "×"
                ToolTip.text: qsTr("Cancel search")
                onClicked: root.cancelSearchRequested()
            }
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
                        FluButton {
                            visible: safeCount(root.actionableIssues) > 0
                            text: "⚠ " + safeCount(root.actionableIssues)
                            onClicked: riskPopup.open()
                        }
                        FluText { text: String(safeCount(root.issues)); color: FluTheme.fontSecondaryColor }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 12; Layout.rightMargin: 12; Layout.bottomMargin: 8
                        visible: root.cloneSelectionMode
                        FluText { text: qsTr("%1 selected").arg(root.safeCount(root.cloneSelectedIds)) }
                        Item { Layout.fillWidth: true }
                        FluButton { text: qsTr("Cancel"); onClicked: root.cloneSelectionCancelled() }
                        FluFilledButton { text: qsTr("Prepare drafts"); disabled: root.safeCount(root.cloneSelectedIds) === 0; onClicked: root.cloneSelectionConfirmed() }
                    }
                    FluButton {
                        Layout.leftMargin: 12; Layout.bottomMargin: 8
                        visible: root.cloneSelectable && !root.cloneSelectionMode
                        text: qsTr("Clone to Jira")
                        onClicked: root.cloneSelectionRequested()
                    }
                    Popup {
                        id: riskPopup
                        x: Math.max(0, parent.width - width - 12)
                        y: 44
                        width: Math.min(460, Math.max(300, root.width * 0.45))
                        height: Math.min(420, riskList.contentHeight + 20)
                        padding: 10
                        modal: false
                        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                        background: Rectangle { color: FluTheme.dark ? "#2B2B2B" : "#FFFFFF"; border.color: FluTheme.frameColor; radius: 6 }
                        ListView {
                            id: riskList
                            anchors.fill: parent
                            clip: true
                            model: root.actionableIssues || []
                            delegate: ItemDelegate {
                                width: ListView.view.width
                                height: 60
                                onClicked: { root.issueSelected(modelData); riskPopup.close() }
                                contentItem: RowLayout {
                                    spacing: 8
                                    Rectangle { width: 8; height: 8; radius: 4; color: modelData.updateRisk === "red" ? "#D13438" : modelData.responsibilityType === "unassigned" ? "#797775" : modelData.staleType ? "#8764B8" : "#FFB900" }
                                    FluButton {
                                        objectName: "flyoutIssueLink"
                                        text: modelData.key || modelData.id || ""
                                        disabled: !(modelData.webUrl || "")
                                        onClicked: root.openIssueRequested(modelData.key || modelData.id || "", modelData.webUrl || "")
                                    }
                                    FluText { Layout.fillWidth: true; text: modelData.title || ""; elide: Text.ElideRight }
                                    Rectangle {
                                        visible: root.partyLabel(modelData).length > 0
                                        radius: 8; height: 22; width: flyoutParty.implicitWidth + 14
                                        color: root.responsibilityFill(modelData); border.color: root.responsibilityColor(modelData)
                                        FluText { id: flyoutParty; anchors.centerIn: parent; text: root.partyLabel(modelData); color: root.responsibilityColor(modelData); font: FluTextStyle.Caption }
                                    }
                                    Rectangle {
                                        visible: root.staleLabel(modelData).length > 0
                                        radius: 8; height: 22; width: flyoutStale.implicitWidth + 14
                                        color: FluTheme.dark ? "#35264A" : "#F3EAFB"; border.color: FluTheme.dark ? "#C6A7E2" : "#744DA9"
                                        FluText { id: flyoutStale; anchors.centerIn: parent; text: root.staleLabel(modelData); color: FluTheme.dark ? "#C6A7E2" : "#744DA9"; font: FluTextStyle.Caption }
                                    }
                                    FluText { text: modelData.updateAgeText || ""; color: modelData.updateRisk === "red" ? "#D13438" : "#B07D00" }
                                }
                            }
                        }
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
                            height: 76
                            highlighted: (root.selectedIssue.id || root.selectedIssue.key || "") === (modelData.id || modelData.key || "")
                            onClicked: root.issueSelected(modelData)
                            contentItem: RowLayout {
                                spacing: 8
                                property bool cloneSelectable: modelData.cloneStatus !== "cloned" && !modelData.clonedIssueKey
                                FluCheckBox {
                                    visible: root.cloneSelectionMode
                                    disabled: !parent.cloneSelectable
                                    checked: root.cloneSelectedIds.indexOf(String(modelData.id || modelData.key || "")) >= 0
                                    onClicked: root.cloneSelectionToggled(String(modelData.id || modelData.key || ""), checked)
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    RowLayout {
                                    Layout.fillWidth: true; spacing: 8
                                    FluButton {
                                        objectName: "ordinaryIssueLink"
                                        text: modelData.key || modelData.id || ""
                                        disabled: !(modelData.webUrl || "")
                                        onClicked: root.openIssueRequested(modelData.key || modelData.id || "", modelData.webUrl || "")
                                    }
                                    Rectangle {
                                        visible: root.partyLabel(modelData).length > 0
                                        radius: 8; height: 22; width: rowParty.implicitWidth + 14
                                        color: root.responsibilityFill(modelData); border.color: root.responsibilityColor(modelData)
                                        FluText { id: rowParty; anchors.centerIn: parent; text: root.partyLabel(modelData); color: root.responsibilityColor(modelData); font: FluTextStyle.Caption }
                                    }
                                    Rectangle {
                                        visible: root.staleLabel(modelData).length > 0
                                        radius: 8; height: 22; width: rowStale.implicitWidth + 14
                                        color: FluTheme.dark ? "#35264A" : "#F3EAFB"; border.color: FluTheme.dark ? "#C6A7E2" : "#744DA9"
                                        FluText { id: rowStale; anchors.centerIn: parent; text: root.staleLabel(modelData); color: FluTheme.dark ? "#C6A7E2" : "#744DA9"; font: FluTextStyle.Caption }
                                    }
                                    Item { Layout.fillWidth: true }
                                    FluText {
                                        visible: !!modelData.updateAgeText
                                        text: "◷ " + (modelData.updateAgeText || "")
                                        color: modelData.updateRisk === "red" ? "#D13438" : modelData.updateRisk === "yellow" ? "#B07D00" : modelData.updateRisk === "green" ? "#107C10" : FluTheme.fontSecondaryColor
                                        font: FluTextStyle.Caption
                                    }
                                }
                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 8
                                        FluText { Layout.fillWidth: true; text: modelData.title || ""; elide: Text.ElideRight; color: FluTheme.fontPrimaryColor }
                                        FluText {
                                            visible: !!modelData.clonedIssueKey || modelData.cloneStatus === "not_cloned"
                                            text: modelData.clonedIssueKey || (modelData.cloneStatus === "not_cloned" ? qsTr("Not cloned") : "")
                                            color: modelData.clonedIssueKey ? (FluTheme.dark ? "#6EA8FE" : "#0F62FE") : FluTheme.fontSecondaryColor
                                            font: FluTextStyle.Caption
                                        }
                                    }
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
