import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../../global"

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
    property real densityScale: 1.0
    property bool filterDraftDirty: false
    property var pendingSubmittedFilters: null
    property bool filterStateInitialized: false
    readonly property int responsiveOrientation: issueSplit.orientation

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

    function metric(value, minimum) {
        return Math.max(minimum || 0, Math.round(value * densityScale))
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

    function currentFilterState() {
        return {
            "project": root.selectedProjectId(),
            "status": statusFilter.currentText,
            "type": typeFilter.currentText,
            "subject": subjectFilter.text,
            "text": textFilter.text
        }
    }

    function sameFilterState(left, right) {
        var a = left || {}
        var b = right || {}
        return (a.project || "") === (b.project || "")
            && (a.status || qsTr("All statuses")) === (b.status || qsTr("All statuses"))
            && (a.type || qsTr("All types")) === (b.type || qsTr("All types"))
            && (a.subject || "") === (b.subject || "")
            && (a.text || "") === (b.text || "")
    }

    function currentSelectionsAreValid() {
        var projectValid = safeCount(root.projectOptions)
            ? modelIndexById(projectFilter.model, root.selectedProjectId()) >= 0
            : modelIndexOf(projectFilter.model, projectFilter.currentText) >= 0
        return projectValid
            && modelIndexOf(statusFilter.model, statusFilter.currentText) >= 0
            && modelIndexOf(typeFilter.model, typeFilter.currentText) >= 0
    }

    function submitCurrentFilters() {
        var submitted = currentFilterState()
        root.pendingSubmittedFilters = submitted
        root.filterDraftDirty = false
        root.searchRequested(submitted)
    }

    function applyFilterState(force) {
        var externalFilters = root.filters || {}
        if(root.pendingSubmittedFilters && sameFilterState(externalFilters, root.pendingSubmittedFilters)) {
            root.pendingSubmittedFilters = null
        }
        var preserveDraft = !force
            && root.filterStateInitialized
            && (root.filterDraftDirty || root.pendingSubmittedFilters !== null)
            && currentSelectionsAreValid()
        if(preserveDraft) return
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
        root.filterStateInitialized = true
        root.filterDraftDirty = false
    }

    onFiltersChanged: Qt.callLater(function() { applyFilterState(false) })
    onProjectFiltersChanged: Qt.callLater(function() { applyFilterState(false) })
    onProjectOptionsChanged: Qt.callLater(function() { applyFilterState(false) })
    onStatusFiltersChanged: Qt.callLater(function() { applyFilterState(false) })
    onTypeFiltersChanged: Qt.callLater(function() { applyFilterState(false) })
    onActiveQuickViewIdChanged: Qt.callLater(function() {
        if(root.activeQuickViewId.length === 0 && root.pendingSubmittedFilters !== null) return
        root.pendingSubmittedFilters = null
        applyFilterState(true)
    })
    Component.onCompleted: Qt.callLater(function() { applyFilterState(true) })

    ColumnLayout {
        anchors.fill: parent
        spacing: root.metric(10, 6)

        FluFrame {
            objectName: "issueFilterFrame"
            Layout.fillWidth: true
            padding: root.metric(12, 8)
            ColumnLayout {
                anchors.fill: parent
                spacing: root.metric(8, 5)
                GridLayout {
                    Layout.fillWidth: true
                    columns: ResponsiveMetrics.isCompact(root.width) ? 1 : (ResponsiveMetrics.isMedium(root.width) ? 3 : 5)
                    visible: safeCount(root.quickViews) > 0
                    FluText { text: qsTr("Quick views"); font: FluTextStyle.Caption }
                    Repeater {
                        model: root.quickViews
                        FluButton {
                            objectName: "issueQuickViewButton_" + index
                            text: modelData.label || modelData.name || ""
                            onClicked: root.quickViewRequested(modelData.id || "")
                        }
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: ResponsiveMetrics.isCompact(root.width) ? 1 : (ResponsiveMetrics.isMedium(root.width) ? 3 : 6)
                    FluComboBox { /* persistence-opt-out: transient */
                        id: projectFilter
                        objectName: "issueProjectFilter"
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.metric(36, 28)
                        Layout.preferredWidth: ResponsiveMetrics.isWide(root.width) ? 420 : 240
                        Layout.minimumWidth: 0
                        textRole: safeCount(root.projectOptions) ? "label" : ""
                        valueRole: safeCount(root.projectOptions) ? "id" : ""
                        model: safeCount(root.projectOptions) ? root.projectOptions : (safeCount(root.projectFilters) ? root.projectFilters : [qsTr("All projects")])
                        popup.width: Math.min(root.width * 0.9, Math.max(width, 420))
                        ToolTip.visible: hovered
                        ToolTip.text: displayText
                        onActivated: root.filterDraftDirty = true
                    }
                    FluComboBox { /* persistence-opt-out: transient */ id: statusFilter; Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 140; Layout.preferredHeight: root.metric(36, 28); model: safeCount(root.statusFilters) ? root.statusFilters : [qsTr("All statuses")]; onActivated: root.filterDraftDirty = true }
                    FluComboBox { /* persistence-opt-out: transient */ id: typeFilter; Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 130; Layout.preferredHeight: root.metric(36, 28); model: safeCount(root.typeFilters) ? root.typeFilters : [qsTr("All types")]; onActivated: root.filterDraftDirty = true }
                    FluTextBox { /* persistence-opt-out: transient */ id: subjectFilter; Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 180; Layout.preferredHeight: root.metric(36, 28); placeholderText: qsTr("Subject"); onTextEdited: root.filterDraftDirty = true }
                    FluTextBox { /* persistence-opt-out: transient */ id: textFilter; Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredHeight: root.metric(36, 28); placeholderText: qsTr("Contains text"); onTextEdited: root.filterDraftDirty = true }
                    FluFilledButton {
                        objectName: "issueSearchButton"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: root.metric(36, 28)
                        text: qsTr("Search")
                        disabled: root.searchLoading || root.projectsLoading || !root.projectsReady
                        onClicked: root.submitCurrentFilters()
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: root.activeQuickViewId === "watched"
                    FluTextBox { /* persistence-opt-out: owner:JiraIssueBrowser */ id: watchedIds; Layout.fillWidth: true; text: root.watchedIssueText; placeholderText: qsTr("Watched issue IDs") }
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
            id: issueSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: ResponsiveMetrics.isCompact(root.width) ? Qt.Vertical : Qt.Horizontal

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
                        Layout.margins: root.metric(12, 8)
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
                        Layout.leftMargin: root.metric(12, 8); Layout.rightMargin: root.metric(12, 8); Layout.bottomMargin: root.metric(8, 5)
                        visible: root.cloneSelectionMode
                        FluText { text: qsTr("%1 selected").arg(root.safeCount(root.cloneSelectedIds)) }
                        Item { Layout.fillWidth: true }
                        FluButton { text: qsTr("Cancel"); onClicked: root.cloneSelectionCancelled() }
                        FluFilledButton { text: qsTr("Prepare drafts"); disabled: root.safeCount(root.cloneSelectedIds) === 0; onClicked: root.cloneSelectionConfirmed() }
                    }
                    FluButton {
                        Layout.leftMargin: root.metric(12, 8); Layout.bottomMargin: root.metric(8, 5)
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
                            height: root.metric(76, 54)
                            highlighted: (root.selectedIssue.id || root.selectedIssue.key || "") === (modelData.id || modelData.key || "")
                            onClicked: root.issueSelected(modelData)
                            contentItem: RowLayout {
                                spacing: root.metric(8, 5)
                                property bool cloneSelectable: modelData.cloneStatus !== "cloned" && !modelData.clonedIssueKey
                                FluCheckBox { /* persistence-opt-out: transient */
                                    visible: root.cloneSelectionMode
                                    disabled: !parent.cloneSelectable
                                    checked: root.cloneSelectedIds.indexOf(String(modelData.id || modelData.key || "")) >= 0
                                    onClicked: root.cloneSelectionToggled(String(modelData.id || modelData.key || ""), checked)
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: root.metric(4, 3)
                                    RowLayout {
                                    Layout.fillWidth: true; spacing: root.metric(8, 5)
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
                                        Layout.fillWidth: true; spacing: root.metric(8, 5)
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
                    densityScale: root.densityScale
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
