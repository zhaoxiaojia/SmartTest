import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../component"
import "../component/redmine"
import "../component/jiraaudit"
import "../component/confluenceaudit"
import "../component/dailyreport"

FluPage {
    id: root
    title: qsTr("Tool")
    launchMode: FluPageType.SingleInstance

    property int selectedGroupIndex: 0
    property int selectedToolIndex: 0
    property bool scheduleExpanded: false
    property var selectedGroup: ToolBridge.groups.length > selectedGroupIndex ? ToolBridge.groups[selectedGroupIndex] : ({})
    property var selectedTool: selectedGroup.tools && selectedGroup.tools.length > selectedToolIndex ? selectedGroup.tools[selectedToolIndex] : ({})
    property string autoStartedToolId: ""
    property string pendingScheduleDeleteProvider: ""
    property string pendingScheduleDeletePlan: ""

    FluContentDialog {
        id: scheduleDeleteDialog
        title: qsTr("Delete schedule?")
        message: qsTr("This removes the Windows task, saved schedule, and its stored Daily Report credential.")
        positiveText: qsTr("Delete")
        negativeText: qsTr("Cancel")
        buttonFlags: FluContentDialogType.NegativeButton | FluContentDialogType.PositiveButton
        onPositiveClicked: ScheduleBridge.deletePlan(root.pendingScheduleDeleteProvider, root.pendingScheduleDeletePlan)
    }

    function maybeStartRedmineLogin() {
        if (selectedTool.id !== "redmine") {
            autoStartedToolId = ""
            return
        }
        if (RedmineBridge.state === "idle" && autoStartedToolId !== "redmine") {
            autoStartedToolId = "redmine"
            RedmineBridge.startLogin()
        }
    }

    onSelectedToolChanged: Qt.callLater(maybeStartRedmineLogin)
    Component.onCompleted: {
        ScheduleBridge.refresh()
        Qt.callLater(maybeStartRedmineLogin)
    }

    function selectTool(groupId, toolIndex) {
        for (var index = 0; index < ToolBridge.groups.length; ++index) {
            if (ToolBridge.groups[index].id === groupId) {
                selectedGroupIndex = index
                selectedToolIndex = toolIndex
                Qt.callLater(maybeStartRedmineLogin)
                return
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        FluFrame {
            objectName: "toolScheduleArea"
            Layout.fillWidth: true
            Layout.preferredHeight: scheduleExpanded ? 190 : 46
            padding: 10

            ColumnLayout {
                anchors.fill: parent
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    FluText { text: qsTr("Schedule"); font: FluTextStyle.Subtitle }
                    Item { Layout.fillWidth: true }
                    FluIconButton {
                        objectName: "toolScheduleToggle"
                        iconSource: scheduleExpanded ? FluentIcons.ChevronUp : FluentIcons.ChevronDown
                        onClicked: scheduleExpanded = !scheduleExpanded
                    }
                }
                FluText {
                    objectName: "toolScheduleEmptyState"
                    visible: scheduleExpanded && ScheduleBridge.rows.length === 0
                    text: qsTr("No SmartTest Windows schedules are configured.")
                    color: FluTheme.fontSecondaryColor
                }
                Flickable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: scheduleExpanded && ScheduleBridge.rows.length > 0
                    clip: true
                    contentWidth: scheduleRow.implicitWidth
                    contentHeight: height
                    flickableDirection: Flickable.HorizontalFlick

                    RowLayout {
                        id: scheduleRow
                        height: parent.height
                        spacing: 8
                        Repeater {
                            model: ScheduleBridge.rows
                            FluFrame {
                                required property var modelData
                                objectName: "toolScheduleCard_" + modelData.provider + "_" + modelData.planId
                                Layout.preferredWidth: 700
                                Layout.fillHeight: true
                                padding: 8
                                RowLayout {
                                    anchors.fill: parent
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        FluText { Layout.fillWidth: true; text: modelData.businessTitle; font: FluTextStyle.BodyStrong; elide: Text.ElideRight }
                                        FluText { Layout.fillWidth: true; text: modelData.title; color: FluTheme.fontSecondaryColor; elide: Text.ElideRight }
                                        FluText {
                                            objectName: "toolScheduleType_" + modelData.planId
                                            Layout.fillWidth: true
                                            text: qsTr("Type: %1").arg(modelData.taskTypeText)
                                            color: FluTheme.fontSecondaryColor
                                        }
                                        FluText {
                                            objectName: "toolScheduleContent_" + modelData.planId
                                            Layout.fillWidth: true
                                            text: qsTr("Content: %1").arg(modelData.contentText)
                                            color: FluTheme.fontSecondaryColor
                                            elide: Text.ElideRight
                                        }
                                        FluText {
                                            objectName: "toolSchedulePlan_" + modelData.planId
                                            Layout.fillWidth: true
                                            text: qsTr("Plan: %1").arg(modelData.planText)
                                            color: FluTheme.fontSecondaryColor
                                        }
                                        FluText {
                                            objectName: "toolScheduleStatus_" + modelData.planId
                                            Layout.fillWidth: true
                                            text: modelData.statusText
                                            color: FluTheme.fontSecondaryColor
                                        }
                                        FluText {
                                            objectName: "toolScheduleNextRun_" + modelData.planId
                                            Layout.fillWidth: true
                                            text: modelData.nextRunText
                                            color: FluTheme.fontSecondaryColor
                                        }
                                        FluText { Layout.fillWidth: true; visible: modelData.operationText !== ""; text: modelData.operationText; color: FluTheme.fontSecondaryColor; elide: Text.ElideRight }
                                    }
                                    FluButton {
                                        objectName: "toolScheduleToggle_" + modelData.planId
                                        visible: modelData.manageable
                                        text: modelData.enabled ? qsTr("Stop") : qsTr("Enable")
                                        enabled: !modelData.operationRunning
                                        onClicked: ScheduleBridge.setPlanEnabled(modelData.provider, modelData.planId, !modelData.enabled)
                                    }
                                    FluButton {
                                        objectName: "toolScheduleRunNow_" + modelData.planId
                                        visible: modelData.manageable
                                        text: qsTr("Run now")
                                        enabled: !modelData.operationRunning
                                        onClicked: ScheduleBridge.runNow(modelData.provider, modelData.planId)
                                    }
                                    FluButton {
                                        objectName: "toolScheduleDelete_" + modelData.planId
                                        visible: modelData.manageable
                                        text: qsTr("Delete")
                                        enabled: !modelData.operationRunning
                                        onClicked: {
                                            root.pendingScheduleDeleteProvider = modelData.provider
                                            root.pendingScheduleDeletePlan = modelData.planId
                                            scheduleDeleteDialog.open()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

        Rectangle {
            Layout.preferredWidth: 216
            Layout.fillHeight: true
            color: FluTheme.dark ? "#202020" : "#f7f7f7"
            border.color: FluTheme.frameColor
            radius: 8

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Repeater {
                    model: ToolBridge.groups

                    ColumnLayout {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        spacing: 8

                        FluText {
                            visible: index === 1
                            Layout.fillWidth: true
                            Layout.topMargin: visible ? 8 : 0
                            text: qsTr("Custom Tools")
                            font: FluTextStyle.Caption
                            color: FluTheme.fontSecondaryColor
                        }

                        ToolGroupExpander {
                            id: groupExpander
                            toolGroup: modelData
                            Layout.fillWidth: true
                            headerText: toolGroup.title
                            onToolActivated: (groupId, toolIndex) => selectTool(groupId, toolIndex)
                        }
                    }
                }

                Item {
                    Layout.fillHeight: true
                }
            }
        }

        Item {
            Layout.preferredWidth: 20
        }

        FluFrame {
            Layout.fillWidth: true
            Layout.fillHeight: true
            padding: 12

            ColumnLayout {
                anchors.fill: parent
                spacing: 8

                FluText {
                    objectName: "toolWorkspaceTitle"
                    text: selectedTool.title || selectedGroup.title || qsTr("Select a tool")
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                }
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: FluTheme.frameColor
                }
                Loader {
                    id: jiraAuditWorkspace
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: selectedTool.id === "jira_audit"
                    visible: active
                    sourceComponent: JiraAuditWorkspace {}
                }
                Loader {
                    id: confluenceAuditWorkspace
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: selectedTool.id === "confluence_audit"
                    visible: active
                    sourceComponent: ConfluenceAuditWorkspace {}
                }
                Loader {
                    id: dailyReportWorkspace
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: selectedTool.id === "daily_report"
                    visible: active
                    sourceComponent: DailyReportWorkspace {}
                }
                Loader {
                    id: redmineLogin
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: selectedTool.id === "redmine" && RedmineBridge.state !== "authenticated"
                    visible: active
                    sourceComponent: RedmineLoginView {
                        state: RedmineBridge.state
                        statusText: RedmineBridge.statusText
                        onStartLoginRequested: RedmineBridge.startLogin()
                        onCredentialsSubmitRequested: (username, password) => RedmineBridge.submitCredentials(username, password)
                        onVerificationSubmitRequested: code => RedmineBridge.submitVerification(code)
                        onCancelRequested: RedmineBridge.cancelLogin()
                    }
                }
                Item {
                    id: redmineWorkspaceHost
                    objectName: "redmineWorkspaceHost"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: selectedTool.id === "redmine" && RedmineBridge.state === "authenticated"
                    property bool cloneBatchActive: ["loading", "prepare_failed", "editing", "validating", "submitting", "completed", "partial_failed"].indexOf(RedmineBridge.cloneBatchState) >= 0

                    Flickable {
                        id: redmineWorkspaceScroll
                        objectName: "redmineWorkspaceScroll"
                        anchors.fill: parent
                        clip: true
                        contentWidth: width
                        contentHeight: Math.max(height, 840)
                        interactive: !cloneBatchOverlay.active
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: FluScrollBar {
                            interactive: !cloneBatchOverlay.active
                            visible: !cloneBatchOverlay.active
                        }

                        Loader {
                            id: redmineWorkspace
                            width: redmineWorkspaceScroll.width
                            height: redmineWorkspaceScroll.contentHeight
                            active: redmineWorkspaceHost.visible
                            sourceComponent: RedmineWorkspace {
                                issues: RedmineBridge.issueRows
                                actionableIssues: RedmineBridge.actionableIssues
                                selectedIssue: RedmineBridge.selectedIssue
                                projectFilters: RedmineBridge.projectFilterLabels
                                quickViews: RedmineBridge.quickViews
                                activeQuickViewId: RedmineBridge.activeQuickViewId
                                projectOptions: RedmineBridge.projectOptions
                                projectsLoading: RedmineBridge.projectsLoading
                                projectsReady: RedmineBridge.projectsReadyState
                                projectsStatusText: RedmineBridge.projectsStatusText
                                searchLoading: RedmineBridge.searchLoading
                                searchCanCancel: RedmineBridge.searchCanCancel
                                filters: RedmineBridge.filters
                                dataLoading: RedmineBridge.dataLoading
                                dataLoaded: RedmineBridge.dataLoaded
                                dataTotal: RedmineBridge.dataTotal
                                dataStatusText: RedmineBridge.dataStatusText
                                onSearchRequested: filters => RedmineBridge.applyFilters(filters)
                                onQuickViewRequested: quickViewId => RedmineBridge.activateQuickView(quickViewId)
                                onCancelSearchRequested: RedmineBridge.cancelSearch()
                                onIssueSelected: issue => RedmineBridge.selectIssue(issue.id || issue.key || "")
                                onOpenIssueRequested: (key, url) => RedmineBridge.openWebUrl(url)
                                onExternalLinkRequested: url => RedmineBridge.openWebUrl(url)
                            }
                        }
                    }

                    Loader {
                        id: cloneBatchOverlay
                        anchors.fill: parent
                        z: 1000
                        active: redmineWorkspaceHost.cloneBatchActive
                        source: active ? "../component/issue/JiraCreateBatchDialog.qml" : ""
                    }

                    Binding { target: cloneBatchOverlay.item; property: "cloneDrafts"; value: RedmineBridge.cloneDrafts; when: cloneBatchOverlay.status === Loader.Ready }
                    Binding { target: cloneBatchOverlay.item; property: "batchState"; value: RedmineBridge.cloneBatchState; when: cloneBatchOverlay.status === Loader.Ready }
                    Binding { target: cloneBatchOverlay.item; property: "loaded"; value: RedmineBridge.cloneBatchLoaded; when: cloneBatchOverlay.status === Loader.Ready }
                    Binding { target: cloneBatchOverlay.item; property: "total"; value: RedmineBridge.cloneBatchTotal; when: cloneBatchOverlay.status === Loader.Ready }
                    Binding { target: cloneBatchOverlay.item; property: "batchError"; value: RedmineBridge.cloneBatchError; when: cloneBatchOverlay.status === Loader.Ready }
                    Binding { target: cloneBatchOverlay.item; property: "firstInvalidIssueId"; value: RedmineBridge.firstInvalidIssueId; when: cloneBatchOverlay.status === Loader.Ready }
                    Binding { target: cloneBatchOverlay.item; property: "firstInvalidFieldId"; value: RedmineBridge.firstInvalidFieldId; when: cloneBatchOverlay.status === Loader.Ready }

                    Connections {
                        target: cloneBatchOverlay.item
                        ignoreUnknownSignals: true
                        function onUpdateCloneDraft(issueId, fieldId, value) { RedmineBridge.updateCloneDraft(issueId, fieldId, value) }
                        function onSubmitCloneBatch() { RedmineBridge.submitCloneBatch() }
                        function onRetryFailedClones() { RedmineBridge.retryFailedClones() }
                        function onRetryPrepareCloneDrafts() { RedmineBridge.prepareCloneDrafts() }
                        function onCloseCloneBatch() { RedmineBridge.closeCloneBatch() }
                        function onSearchCloneUsers(issueId, fieldId, query) { RedmineBridge.searchCloneUsers(issueId, fieldId, query) }
                        function onSourceLinkRequested(url) { RedmineBridge.openWebUrl(url) }
                    }
                    Connections {
                        target: RedmineBridge
                        ignoreUnknownSignals: true
                        function onCloneDraftFieldChanged(issueId, field) {
                            if (cloneBatchOverlay.item)
                                cloneBatchOverlay.item.updateDraftField(issueId, field)
                        }
                        function onCloneInvalidFieldRequested(issueId, fieldId) {
                            if (cloneBatchOverlay.item)
                                cloneBatchOverlay.item.focusInvalidField(issueId, fieldId)
                        }
                    }
                }
                FluText {
                    Layout.fillHeight: true
                    visible: selectedTool.id !== "redmine" && selectedTool.id !== "jira_audit"
                             && selectedTool.id !== "confluence_audit"
                             && selectedTool.id !== "daily_report"
                    text: qsTr("This area is reserved for the selected tool. Execution is not available yet.")
                    color: FluTheme.fontSecondaryColor
                }
            }
        }
    }
    }
}
