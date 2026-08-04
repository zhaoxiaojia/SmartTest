import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0
import "../component"
import "../component/redmine"
import "../component/jiraaudit"
import "../component/confluenceaudit"
import "../component/dailyreport"
import "../global"

FluPage {
    id: page
    title: qsTr("Tool")
    launchMode: FluPageType.SingleInstance

    property int selectedGroupIndex: 0
    property int selectedToolIndex: 0
    property var selectedGroup: ToolBridge.groups.length > selectedGroupIndex ? ToolBridge.groups[selectedGroupIndex] : ({})
    property var selectedTool: selectedGroup.tools && selectedGroup.tools.length > selectedToolIndex ? selectedGroup.tools[selectedToolIndex] : ({})
    property string autoStartedToolId: ""

    function ensureSelectedToolAvailable() {
        if (!selectedGroup.available) {
            selectedGroupIndex = 0
            selectedToolIndex = 0
            autoStartedToolId = ""
            return
        }
        if (!selectedGroup.tools || selectedToolIndex >= selectedGroup.tools.length)
            selectedToolIndex = 0
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
    onSelectedGroupChanged: ensureSelectedToolAvailable()
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

    function selectToolById(toolId) {
        for (var groupIndex = 0; groupIndex < ToolBridge.groups.length; ++groupIndex) {
            const tools = ToolBridge.groups[groupIndex].tools || []
            for (var toolIndex = 0; toolIndex < tools.length; ++toolIndex) {
                if (tools[toolIndex].id === toolId) {
                    selectedGroupIndex = groupIndex
                    selectedToolIndex = toolIndex
                    Qt.callLater(maybeStartRedmineLogin)
                    return
                }
            }
        }
    }

    Connections {
        target: ScheduleBridge
        function onToolOpenRequested(toolId) { selectToolById(toolId) }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        FluFrame {
            objectName: "toolScheduleArea"
            Layout.fillWidth: true
            Layout.preferredHeight: 118
            padding: 10

            ColumnLayout {
                anchors.fill: parent
                spacing: 8

                FluText { text: qsTr("Schedule"); font: FluTextStyle.Subtitle }
                FluText {
                    objectName: "toolScheduleEmptyState"
                    visible: ScheduleBridge.rows.length === 0
                    text: qsTr("No SmartTest Windows schedules are currently enabled.")
                    color: FluTheme.fontSecondaryColor
                }
                Flickable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: ScheduleBridge.rows.length > 0
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
                                Layout.preferredWidth: 340
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
                                            Layout.fillWidth: true
                                            text: modelData.registered ? qsTr("Registered") : qsTr("Not registered")
                                            color: FluTheme.fontSecondaryColor
                                        }
                                    }
                                    FluButton {
                                        objectName: "toolScheduleOpenButton_" + modelData.planId
                                        text: qsTr("Open")
                                        onClicked: ScheduleBridge.openPlan(modelData.provider, modelData.planId)
                                    }
                                    FluButton {
                                        objectName: "toolScheduleDisableButton_" + modelData.planId
                                        text: qsTr("Disable")
                                        onClicked: ScheduleBridge.setPlanEnabled(modelData.provider, modelData.planId, false)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: ResponsiveMetrics.isCompact(page.width) ? 1 : 3
            columnSpacing: 0
            rowSpacing: 0

        Rectangle {
            Layout.preferredWidth: 216
            Layout.fillWidth: ResponsiveMetrics.isCompact(page.width)
            Layout.preferredHeight: ResponsiveMetrics.isCompact(page.width) ? 190 : -1
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
            Layout.preferredHeight: ResponsiveMetrics.isCompact(page.width) ? 12 : 0
        }

        FluFrame {
            Layout.fillWidth: true
            Layout.fillHeight: true
            padding: 12

            ColumnLayout {
                anchors.fill: parent
                spacing: 8

                FluText {
                    text: selectedTool.title || selectedGroup.title || qsTr("Select a tool")
                    font: FluTextStyle.Title
                }
                FluText {
                    Layout.fillWidth: true
                    text: selectedTool.description || qsTr("Tools for this group will appear here.")
                    color: FluTheme.fontSecondaryColor
                    wrapMode: Text.WordWrap
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
                Loader {
                    id: redmineWorkspace
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: selectedTool.id === "redmine" && RedmineBridge.state === "authenticated"
                    visible: active
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
