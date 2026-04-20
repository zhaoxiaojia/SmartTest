import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluPage {
    title: qsTr("Jira")

    property var promptSuggestions: [
        qsTr("Show the issues assigned to me this week and point out blockers."),
        qsTr("Analyze open bugs related to Wi-Fi stability and summarize the hotspots."),
        qsTr("Find high-priority Jira tickets that may affect the next regression run.")
    ]
    property var recentSessions: [
        {name: qsTr("Sprint risk review"), detail: qsTr("Critical and blocked items")},
        {name: qsTr("Wi-Fi defect analysis"), detail: qsTr("Cluster by component")},
        {name: qsTr("Ready-for-test triage"), detail: qsTr("Focus on next regression")}
    ]
    property var conversationRows: []
    property var issueRows: []
    property var quickStats: []
    property var analysisActions: []
    property var selectedIssue: ({})
    property var savedFilters: []
    property bool issueDetailExpanded: false
    property var projectFilterOptions: []
    property var statusFilterOptions: []
    property var priorityFilterOptions: []
    property var issueTypeFilterOptions: []
    property var assigneeFilterOptions: []
    property var reporterFilterOptions: []
    property var labelFilterOptions: []
    property var selectedProjects: ["all_supported_projects"]
    property var selectedStatuses: []
    property var selectedPriorities: []
    property var selectedIssueTypes: ["bug"]
    property var selectedAssignees: []
    property var selectedReporters: []
    property var selectedLabels: []
    property bool filterStateReady: false

    function issueStatusColor(status){
        if(status === "Done" || status === "Closed"){
            return Qt.rgba(82 / 255, 196 / 255, 26 / 255, 1)
        }
        if(status === "In Progress" || status === "Verified"){
            return Qt.rgba(24 / 255, 144 / 255, 1, 1)
        }
        if(status === "Blocked"){
            return Qt.rgba(1, 77 / 255, 79 / 255, 1)
        }
        if(status === "To Do" || status === "Open" || status === "Ready for Test"){
            return Qt.rgba(250 / 255, 173 / 255, 20 / 255, 1)
        }
        return FluTheme.primaryColor
    }

    function syncBridgeState(){
        conversationRows = JiraBridge.conversationRows()
        issueRows = JiraBridge.issueRows()
        quickStats = JiraBridge.quickStats()
        selectedIssue = JiraBridge.selectedIssue()
        analysisActions = JiraBridge.analysisActions()
        savedFilters = JiraBridge.savedFilters()
        rebuildDynamicFilterOptions()
        Qt.callLater(function(){
            if(list_conversation.count > 0){
                list_conversation.positionViewAtEnd()
            }
        })
    }

    function usePrompt(text){
        input_prompt.text = text
        input_prompt.forceActiveFocus()
    }

    function applySavedFilter(filterRow){
        textbox_jql.text = (filterRow.jql || "").trim()
        persistFilterState()
        refreshCurrentScopeIfReady()
    }

    function refreshOptionModels(resetDefaults){
        var boardIndex = resetDefaults ? 0 : combo_board.currentIndex
        var timeframeIndex = resetDefaults ? 1 : combo_timeframe.currentIndex
        projectFilterOptions = JiraBridge.projectFilterOptions()
        statusFilterOptions = JiraBridge.statusFilterOptions()
        priorityFilterOptions = JiraBridge.priorityFilterOptions()
        issueTypeFilterOptions = JiraBridge.issueTypeFilterOptions()
        combo_board.model = JiraBridge.boardOptions()
        combo_timeframe.model = JiraBridge.timeframeOptions()
        combo_board.currentIndex = Math.max(0, Math.min(boardIndex, combo_board.model.length - 1))
        combo_timeframe.currentIndex = Math.max(0, Math.min(timeframeIndex, combo_timeframe.model.length - 1))
        if(resetDefaults){
            selectedProjects = ["all_supported_projects"]
            selectedStatuses = []
            selectedPriorities = []
            selectedIssueTypes = ["bug"]
            selectedAssignees = []
            selectedReporters = []
            selectedLabels = []
        }
    }

    function optionListFromStrings(values){
        return values.map(function(item){
            return {id: item, label: item}
        })
    }

    function distinctIssueValues(fieldName){
        var seen = {}
        var values = []
        for(var i = 0; i < issueRows.length; ++i){
            var value = ((issueRows[i] || {})[fieldName] || "").trim()
            if(value.length === 0 || seen[value]){
                continue
            }
            seen[value] = true
            values.push(value)
        }
        values.sort()
        return values
    }

    function distinctIssueListValues(fieldName){
        var seen = {}
        var values = []
        for(var i = 0; i < issueRows.length; ++i){
            var listValue = (issueRows[i] || {})[fieldName] || []
            for(var j = 0; j < listValue.length; ++j){
                var item = (listValue[j] || "").trim()
                if(item.length === 0 || seen[item]){
                    continue
                }
                seen[item] = true
                values.push(item)
            }
        }
        values.sort()
        return values
    }

    function keepExistingSelections(currentSelections, availableOptions){
        if(availableOptions.length === 0){
            return currentSelections.slice()
        }
        var availableIds = availableOptions.map(function(option){ return option.id })
        return currentSelections.filter(function(item){ return availableIds.indexOf(item) !== -1 })
    }

    function rebuildDynamicFilterOptions(){
        assigneeFilterOptions = optionListFromStrings(distinctIssueValues("assignee"))
        reporterFilterOptions = optionListFromStrings(distinctIssueValues("reporter"))
        labelFilterOptions = optionListFromStrings(distinctIssueListValues("labels"))
        selectedAssignees = keepExistingSelections(selectedAssignees, assigneeFilterOptions)
        selectedReporters = keepExistingSelections(selectedReporters, reporterFilterOptions)
        selectedLabels = keepExistingSelections(selectedLabels, labelFilterOptions)
    }

    function hasId(values, id){
        return values.indexOf(id) !== -1
    }

    function toggleProject(id, checked){
        var next = selectedProjects.slice()
        if(id === "all_supported_projects"){
            selectedProjects = checked ? ["all_supported_projects"] : []
            if(selectedProjects.length === 0){
                selectedProjects = ["all_supported_projects"]
            }
            persistFilterState()
            return
        }
        var allIndex = next.indexOf("all_supported_projects")
        if(allIndex !== -1){
            next.splice(allIndex, 1)
        }
        var index = next.indexOf(id)
        if(checked && index === -1){
            next.push(id)
        }
        if(!checked && index !== -1){
            next.splice(index, 1)
        }
        if(next.length === 0){
            next = ["all_supported_projects"]
        }
        selectedProjects = next
        persistFilterState()
    }

    function toggleSelection(values, id, checked){
        var next = values.slice()
        var index = next.indexOf(id)
        if(checked && index === -1){
            next.push(id)
        }
        if(!checked && index !== -1){
            next.splice(index, 1)
        }
        return next
    }

    function selectedCsv(values){
        return values.join(",")
    }

    function labelsForIds(options, ids){
        var labels = []
        for(var i = 0; i < options.length; ++i){
            var option = options[i]
            if(ids.indexOf(option.id) !== -1){
                labels.push(option.label)
            }
        }
        return labels
    }

    function summaryText(options, ids, allText, emptyText){
        if(ids.indexOf("all_supported_projects") !== -1){
            return allText
        }
        var labels = labelsForIds(options, ids)
        if(labels.length === 0){
            return emptyText
        }
        return labels.join(", ")
    }

    function loadPersistedState(){
        selectedProjects = selectedCsvToArray(SettingsHelper.getString("jira/projects", "all_supported_projects"), ["all_supported_projects"])
        selectedStatuses = selectedCsvToArray(SettingsHelper.getString("jira/statuses", ""), [])
        selectedPriorities = selectedCsvToArray(SettingsHelper.getString("jira/priorities", ""), [])
        selectedIssueTypes = selectedCsvToArray(SettingsHelper.getString("jira/issue_types", "bug"), ["bug"])
        selectedAssignees = selectedCsvToArray(SettingsHelper.getString("jira/assignees", ""), [])
        selectedReporters = selectedCsvToArray(SettingsHelper.getString("jira/reporters", ""), [])
        selectedLabels = selectedCsvToArray(SettingsHelper.getString("jira/labels", ""), [])
        combo_board.currentIndex = Math.max(0, Math.min(SettingsHelper.getInt("jira/board_index", 0), combo_board.model.length - 1))
        combo_timeframe.currentIndex = Math.max(0, Math.min(SettingsHelper.getInt("jira/timeframe_index", 1), combo_timeframe.model.length - 1))
        textbox_jql.text = SettingsHelper.getString("jira/raw_jql", "")
        textbox_keyword.text = SettingsHelper.getString("jira/keyword", "")
        filterStateReady = true
    }

    function persistFilterState(){
        if(!filterStateReady){
            return
        }
        SettingsHelper.saveString("jira/projects", selectedCsv(selectedProjects))
        SettingsHelper.saveString("jira/statuses", selectedCsv(selectedStatuses))
        SettingsHelper.saveString("jira/priorities", selectedCsv(selectedPriorities))
        SettingsHelper.saveString("jira/issue_types", selectedCsv(selectedIssueTypes))
        SettingsHelper.saveString("jira/assignees", selectedCsv(selectedAssignees))
        SettingsHelper.saveString("jira/reporters", selectedCsv(selectedReporters))
        SettingsHelper.saveString("jira/labels", selectedCsv(selectedLabels))
        SettingsHelper.saveInt("jira/board_index", combo_board.currentIndex)
        SettingsHelper.saveInt("jira/timeframe_index", combo_timeframe.currentIndex)
        SettingsHelper.saveString("jira/raw_jql", textbox_jql.text)
        SettingsHelper.saveString("jira/keyword", textbox_keyword.text)
    }

    function refreshCurrentScope(){
        JiraBridge.refreshScope(
            textbox_jql.text,
            selectedCsv(selectedProjects),
            combo_board.currentText,
            combo_timeframe.currentText,
            selectedCsv(selectedStatuses),
            selectedCsv(selectedPriorities),
            selectedCsv(selectedIssueTypes),
            textbox_keyword.text,
            selectedCsv(selectedAssignees),
            selectedCsv(selectedReporters),
            selectedCsv(selectedLabels),
            true,
            true,
            false
        )
    }

    function refreshCurrentScopeIfReady(){
        if(!filterStateReady || JiraBridge.loading){
            return
        }
        if(!AuthBridge.isAuthenticated() || !AuthBridge.hasCredential()){
            return
        }
        refreshCurrentScope()
    }

    function selectedCsvToArray(csv, fallback){
        var values = []
        var text = (csv || "").trim()
        if(text.length > 0){
            values = text.split(",").map(function(item){ return item.trim() }).filter(function(item){ return item.length > 0 })
        }
        if(values.length === 0){
            return fallback.slice()
        }
        return values
    }

    function submitPrompt(){
        var promptText = (input_prompt.text || "").trim()
        if(promptText.length === 0 || JiraBridge.loading){
            return
        }
        JiraBridge.submitPrompt(
            promptText,
            textbox_jql.text,
            selectedCsv(selectedProjects),
            combo_board.currentText,
            combo_timeframe.currentText,
            selectedCsv(selectedStatuses),
            selectedCsv(selectedPriorities),
            selectedCsv(selectedIssueTypes),
            textbox_keyword.text,
            selectedCsv(selectedAssignees),
            selectedCsv(selectedReporters),
            selectedCsv(selectedLabels),
            true,
            true,
            false
        )
        input_prompt.text = ""
    }

    Component.onCompleted: {
        refreshOptionModels(true)
        loadPersistedState()
        JiraBridge.bootstrap()
        syncBridgeState()
        if(AuthBridge.isAuthenticated() && AuthBridge.hasCredential()){
            refreshCurrentScope()
        }
    }

    Connections{
        target: JiraBridge
        function onStateChanged(){ syncBridgeState() }
        function onConnectionChanged(){ syncBridgeState() }
    }

    Connections{
        target: TranslateHelper
        function onCurrentChanged(){
            refreshOptionModels(false)
            syncBridgeState()
        }
    }

    ColumnLayout{
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        FluFrame{
            Layout.fillWidth: true
            padding: 12

            ColumnLayout{
                anchors.fill: parent
                spacing: 10

                RowLayout{
                    Layout.fillWidth: true
                    spacing: 12

                    ColumnLayout{
                        Layout.fillWidth: true
                        spacing: 4

                        FluText{
                            text: qsTr("Jira AI Workspace")
                            font: FluTextStyle.Title
                        }

                        FluText{
                            Layout.fillWidth: true
                            text: qsTr("Signed in as %1. LDAP credentials are reused directly for Jira access.").arg(AuthBridge.username)
                            font: FluTextStyle.Body
                            color: FluTheme.fontSecondaryColor
                            wrapMode: Text.WordWrap
                        }

                        FluText{
                            Layout.fillWidth: true
                            visible: JiraBridge.activeScopeSummary.length > 0
                            text: JiraBridge.activeScopeSummary
                            font: FluTextStyle.Caption
                            color: FluTheme.fontSecondaryColor
                            wrapMode: Text.WordWrap
                        }
                    }

                    FluFrame{
                        Layout.preferredWidth: 320
                        padding: 10

                        ColumnLayout{
                            anchors.fill: parent
                            spacing: 4

                            FluText{
                                Layout.fillWidth: true
                                text: qsTr("Connection")
                                font: FluTextStyle.BodyStrong
                            }

                            RowLayout{
                                spacing: 8

                                Rectangle{
                                    width: 10
                                    height: 10
                                    radius: 5
                                    color: JiraBridge.connected
                                           ? Qt.rgba(82 / 255, 196 / 255, 26 / 255, 1)
                                           : Qt.rgba(250 / 255, 173 / 255, 20 / 255, 1)
                                }

                                FluText{
                                    text: JiraBridge.loading
                                          ? qsTr("Loading")
                                          : (JiraBridge.connected ? qsTr("Connected") : qsTr("Waiting"))
                                    font: FluTextStyle.Body
                                }
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: JiraBridge.statusText
                                font: FluTextStyle.Caption
                                color: FluTheme.fontSecondaryColor
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }

                RowLayout{
                    Layout.fillWidth: true
                    spacing: 10

                    Repeater{
                        model: quickStats

                        FluFrame{
                            Layout.fillWidth: true
                            padding: 10

                            ColumnLayout{
                                anchors.fill: parent
                                spacing: 2

                                FluText{
                                    text: modelData.label
                                    font: FluTextStyle.Caption
                                    color: FluTheme.fontSecondaryColor
                                }

                                FluText{
                                    text: modelData.value
                                    font: FluTextStyle.TitleLarge
                                }

                                FluText{
                                    text: modelData.detail
                                    font: FluTextStyle.Caption
                                    color: FluTheme.fontSecondaryColor
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                }

            }
        }

        FluSplitLayout{
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            FluFrame{
                SplitView.preferredWidth: 300
                SplitView.minimumWidth: 260
                SplitView.maximumWidth: 380
                SplitView.fillHeight: true
                padding: 10

                Flickable{
                    anchors.fill: parent
                    clip: true
                    contentHeight: layout_left.implicitHeight
                    ScrollBar.vertical: FluScrollBar{}

                    ColumnLayout{
                        id: layout_left
                        width: parent.width
                        spacing: 10

                        FluText{
                            text: qsTr("Search Scope")
                            font: FluTextStyle.Subtitle
                        }

                        FluGroupBox{
                            title: qsTr("Common Jira Filters")
                            Layout.fillWidth: true

                            ColumnLayout{
                                anchors.left: parent.left
                                anchors.right: parent.right
                                spacing: 8

                                FluText{
                                    text: qsTr("JQL Filter")
                                    font: FluTextStyle.BodyStrong
                                    Layout.fillWidth: true
                                }

                                FluTextBox{
                                    id: textbox_jql
                                    Layout.fillWidth: true
                                    placeholderText: qsTr("Paste a Jira filter, for example: project = TV ORDER BY created DESC")
                                    onEditingFinished: persistFilterState()
                                }

                                FluText{
                                    Layout.fillWidth: true
                                    text: qsTr("When this field is filled, SmartTest uses this JQL directly and skips the common Jira filters below.")
                                    font: FluTextStyle.Caption
                                    color: FluTheme.fontSecondaryColor
                                    wrapMode: Text.WordWrap
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Projects") + "  |  "
                                                + summaryText(projectFilterOptions, selectedProjects, qsTr("All Supported Projects"), qsTr("Not limited"))
                                    contentHeight: project_filter_content.implicitHeight

                                    Item{
                                        id: project_filter_content
                                        width: parent.width
                                        implicitHeight: col_project_filter.implicitHeight + 20

                                        ColumnLayout{
                                            id: col_project_filter
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            spacing: 6

                                            Repeater{
                                                model: projectFilterOptions

                                                FluCheckBox{
                                                    text: modelData.label
                                                    checked: hasId(selectedProjects, modelData.id)
                                                    onClicked: toggleProject(modelData.id, checked)
                                                }
                                            }
                                        }
                                    }
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Workflow Preset") + "  |  " + combo_board.currentText
                                    contentHeight: board_filter_content.implicitHeight

                                    Item{
                                        id: board_filter_content
                                        width: parent.width
                                        implicitHeight: combo_board.implicitHeight + 20

                                        FluComboBox{
                                            id: combo_board
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            onCurrentIndexChanged: persistFilterState()
                                        }
                                    }
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Time Window") + "  |  " + combo_timeframe.currentText
                                    contentHeight: timeframe_filter_content.implicitHeight

                                    Item{
                                        id: timeframe_filter_content
                                        width: parent.width
                                        implicitHeight: combo_timeframe.implicitHeight + 20

                                        FluComboBox{
                                            id: combo_timeframe
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            onCurrentIndexChanged: persistFilterState()
                                        }
                                    }
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Statuses") + "  |  "
                                                + summaryText(statusFilterOptions, selectedStatuses, qsTr("Not limited"), qsTr("Not limited"))
                                    contentHeight: status_filter_content.implicitHeight

                                    Item{
                                        id: status_filter_content
                                        width: parent.width
                                        implicitHeight: col_status_filter.implicitHeight + 20

                                        ColumnLayout{
                                            id: col_status_filter
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            spacing: 6

                                            Repeater{
                                                model: statusFilterOptions

                                                FluCheckBox{
                                                    text: modelData.label
                                                    checked: hasId(selectedStatuses, modelData.id)
                                                    onClicked: {
                                                        selectedStatuses = toggleSelection(selectedStatuses, modelData.id, checked)
                                                        persistFilterState()
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Priorities") + "  |  "
                                                + summaryText(priorityFilterOptions, selectedPriorities, qsTr("Not limited"), qsTr("Not limited"))
                                    contentHeight: priority_filter_content.implicitHeight

                                    Item{
                                        id: priority_filter_content
                                        width: parent.width
                                        implicitHeight: col_priority_filter.implicitHeight + 20

                                        ColumnLayout{
                                            id: col_priority_filter
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            spacing: 6

                                            Repeater{
                                                model: priorityFilterOptions

                                                FluCheckBox{
                                                    text: modelData.label
                                                    checked: hasId(selectedPriorities, modelData.id)
                                                    onClicked: {
                                                        selectedPriorities = toggleSelection(selectedPriorities, modelData.id, checked)
                                                        persistFilterState()
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Issue Types") + "  |  "
                                                + summaryText(issueTypeFilterOptions, selectedIssueTypes, qsTr("Not limited"), qsTr("Not limited"))
                                    contentHeight: issue_type_filter_content.implicitHeight

                                    Item{
                                        id: issue_type_filter_content
                                        width: parent.width
                                        implicitHeight: col_issue_type_filter.implicitHeight + 20

                                        ColumnLayout{
                                            id: col_issue_type_filter
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            spacing: 6

                                            Repeater{
                                                model: issueTypeFilterOptions

                                                FluCheckBox{
                                                    text: modelData.label
                                                    checked: hasId(selectedIssueTypes, modelData.id)
                                                    onClicked: {
                                                        selectedIssueTypes = toggleSelection(selectedIssueTypes, modelData.id, checked)
                                                        if(selectedIssueTypes.length === 0){
                                                            selectedIssueTypes = ["bug"]
                                                        }
                                                        persistFilterState()
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Keyword text") + "  |  "
                                                + ((textbox_keyword.text || "").trim().length > 0 ? textbox_keyword.text : qsTr("Not limited"))
                                    contentHeight: keyword_filter_content.implicitHeight

                                    Item{
                                        id: keyword_filter_content
                                        width: parent.width
                                        implicitHeight: textbox_keyword.implicitHeight + 20

                                        FluTextBox{
                                            id: textbox_keyword
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            placeholderText: qsTr("Keyword text")
                                            onTextChanged: persistFilterState()
                                        }
                                    }
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Assignee") + "  |  "
                                                + summaryText(assigneeFilterOptions, selectedAssignees, qsTr("Not limited"), qsTr("Not limited"))
                                    contentHeight: assignee_filter_content.implicitHeight

                                    Item{
                                        id: assignee_filter_content
                                        width: parent.width
                                        implicitHeight: col_assignee_filter.implicitHeight + 20

                                        ColumnLayout{
                                            id: col_assignee_filter
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            spacing: 6

                                            FluText{
                                                visible: assigneeFilterOptions.length === 0
                                                text: qsTr("No options in current result set")
                                                font: FluTextStyle.Caption
                                                color: FluTheme.fontSecondaryColor
                                            }

                                            Repeater{
                                                model: assigneeFilterOptions

                                                FluCheckBox{
                                                    text: modelData.label
                                                    checked: hasId(selectedAssignees, modelData.id)
                                                    onClicked: {
                                                        selectedAssignees = toggleSelection(selectedAssignees, modelData.id, checked)
                                                        persistFilterState()
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Reporter") + "  |  "
                                                + summaryText(reporterFilterOptions, selectedReporters, qsTr("Not limited"), qsTr("Not limited"))
                                    contentHeight: reporter_filter_content.implicitHeight

                                    Item{
                                        id: reporter_filter_content
                                        width: parent.width
                                        implicitHeight: col_reporter_filter.implicitHeight + 20

                                        ColumnLayout{
                                            id: col_reporter_filter
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            spacing: 6

                                            FluText{
                                                visible: reporterFilterOptions.length === 0
                                                text: qsTr("No options in current result set")
                                                font: FluTextStyle.Caption
                                                color: FluTheme.fontSecondaryColor
                                            }

                                            Repeater{
                                                model: reporterFilterOptions

                                                FluCheckBox{
                                                    text: modelData.label
                                                    checked: hasId(selectedReporters, modelData.id)
                                                    onClicked: {
                                                        selectedReporters = toggleSelection(selectedReporters, modelData.id, checked)
                                                        persistFilterState()
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                FluExpander{
                                    Layout.fillWidth: true
                                    headerText: qsTr("Labels") + "  |  "
                                                + summaryText(labelFilterOptions, selectedLabels, qsTr("Not limited"), qsTr("Not limited"))
                                    contentHeight: labels_filter_content.implicitHeight

                                    Item{
                                        id: labels_filter_content
                                        width: parent.width
                                        implicitHeight: col_labels_filter.implicitHeight + 20

                                        ColumnLayout{
                                            id: col_labels_filter
                                            x: 12
                                            y: 10
                                            width: parent.width - 24
                                            spacing: 6

                                            FluText{
                                                visible: labelFilterOptions.length === 0
                                                text: qsTr("No options in current result set")
                                                font: FluTextStyle.Caption
                                                color: FluTheme.fontSecondaryColor
                                            }

                                            Repeater{
                                                model: labelFilterOptions

                                                FluCheckBox{
                                                    text: modelData.label
                                                    checked: hasId(selectedLabels, modelData.id)
                                                    onClicked: {
                                                        selectedLabels = toggleSelection(selectedLabels, modelData.id, checked)
                                                        persistFilterState()
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                FluFilledButton{
                                    Layout.fillWidth: true
                                    text: JiraBridge.loading ? qsTr("Loading...") : qsTr("Refresh Results")
                                    disabled: JiraBridge.loading
                                    onClicked: refreshCurrentScope()
                                }
                            }
                        }

                        FluGroupBox{
                            title: qsTr("My Filters")
                            Layout.fillWidth: true

                            ColumnLayout{
                                anchors.left: parent.left
                                anchors.right: parent.right
                                spacing: 8

                                FluText{
                                    visible: JiraBridge.filtersLoading
                                    Layout.fillWidth: true
                                    text: qsTr("Loading your Jira filters...")
                                    font: FluTextStyle.Caption
                                    color: FluTheme.fontSecondaryColor
                                    wrapMode: Text.WordWrap
                                }

                                FluText{
                                    visible: !JiraBridge.filtersLoading && savedFilters.length === 0
                                    Layout.fillWidth: true
                                    text: qsTr("No favourite filters were found for this account.")
                                    font: FluTextStyle.Caption
                                    color: FluTheme.fontSecondaryColor
                                    wrapMode: Text.WordWrap
                                }

                                Repeater{
                                    model: savedFilters

                                    Item{
                                        Layout.fillWidth: true
                                        implicitHeight: saved_filter_column.implicitHeight + 16

                                        Rectangle{
                                            anchors.fill: parent
                                            radius: 6
                                            color: FluTheme.frameColor
                                            border.width: 1
                                            border.color: FluTheme.dividerColor
                                        }

                                        Column{
                                            id: saved_filter_column
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.top: parent.top
                                            anchors.margins: 8
                                            spacing: 2

                                            FluText{
                                                width: parent.width
                                                text: modelData.name
                                                font: FluTextStyle.BodyStrong
                                                wrapMode: Text.WordWrap
                                            }

                                            FluText{
                                                width: parent.width
                                                text: modelData.jql
                                                font: FluTextStyle.Caption
                                                color: FluTheme.fontSecondaryColor
                                                wrapMode: Text.WordWrap
                                                maximumLineCount: 2
                                                elide: Text.ElideRight
                                            }

                                            FluText{
                                                width: parent.width
                                                text: qsTr("Click to apply this filter to the current JQL box.")
                                                font: FluTextStyle.Caption
                                                color: FluTheme.fontSecondaryColor
                                                wrapMode: Text.WordWrap
                                            }
                                        }

                                        MouseArea{
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: applySavedFilter(modelData)
                                        }
                                    }
                                }
                            }
                        }

                        FluGroupBox{
                            title: qsTr("Suggested Queries")
                            Layout.fillWidth: true

                            ColumnLayout{
                                anchors.left: parent.left
                                anchors.right: parent.right
                                spacing: 8

                                Repeater{
                                    model: promptSuggestions

                                    Item{
                                        Layout.fillWidth: true
                                        implicitHeight: suggested_query_column.implicitHeight + 20

                                        Rectangle{
                                            anchors.fill: parent
                                            radius: 6
                                            color: FluTheme.frameColor
                                            border.width: 1
                                            border.color: FluTheme.dividerColor
                                        }

                                        Column{
                                            id: suggested_query_column
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.top: parent.top
                                            anchors.margins: 10
                                            spacing: 4

                                            FluText{
                                                width: parent.width
                                                text: modelData
                                                wrapMode: Text.WordWrap
                                            }

                                            FluText{
                                                width: parent.width
                                                text: qsTr("Click to place this prompt into the AI input box.")
                                                font: FluTextStyle.Caption
                                                color: FluTheme.fontSecondaryColor
                                                wrapMode: Text.WordWrap
                                            }
                                        }

                                        MouseArea{
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: usePrompt(modelData)
                                        }
                                    }
                                }
                            }
                        }

                        FluGroupBox{
                            title: qsTr("Recent Sessions")
                            Layout.fillWidth: true

                            ColumnLayout{
                                anchors.left: parent.left
                                anchors.right: parent.right
                                spacing: 6

                                Repeater{
                                    model: recentSessions

                                    Item{
                                        Layout.fillWidth: true
                                        implicitHeight: recent_session_column.implicitHeight + 16

                                        Rectangle{
                                            anchors.fill: parent
                                            radius: 6
                                            color: FluTheme.frameColor
                                            border.width: 1
                                            border.color: FluTheme.dividerColor
                                        }

                                        Column{
                                            id: recent_session_column
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.top: parent.top
                                            anchors.margins: 8
                                            spacing: 2

                                            FluText{
                                                width: parent.width
                                                text: modelData.name
                                                font: FluTextStyle.BodyStrong
                                                wrapMode: Text.WordWrap
                                            }

                                            FluText{
                                                width: parent.width
                                                text: modelData.detail
                                                font: FluTextStyle.Caption
                                                color: FluTheme.fontSecondaryColor
                                                wrapMode: Text.WordWrap
                                            }
                                        }

                                        MouseArea{
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: usePrompt(modelData.name)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            FluFrame{
                SplitView.fillWidth: true
                SplitView.minimumWidth: 420
                SplitView.fillHeight: true
                padding: 10

                ColumnLayout{
                    anchors.fill: parent
                    spacing: 10

                    RowLayout{
                        Layout.fillWidth: true

                        ColumnLayout{
                            Layout.fillWidth: true
                            spacing: 2

                            FluText{
                                text: qsTr("AI Conversation")
                                font: FluTextStyle.Subtitle
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: qsTr("Use plain language. Jira search and AI analysis are both driven from this workspace.")
                                color: FluTheme.fontSecondaryColor
                                wrapMode: Text.WordWrap
                            }
                        }

                        FluButton{
                            text: qsTr("Clear Session")
                            onClicked: JiraBridge.clearConversation()
                        }
                    }

                    ListView{
                        id: list_conversation
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 10
                        model: conversationRows
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: FluScrollBar{}

                        delegate: Item{
                            width: list_conversation.width
                            height: bubble.implicitHeight + 4

                            Rectangle{
                                id: bubble
                                width: Math.min(list_conversation.width * 0.78, 560)
                                implicitHeight: bubble_content.implicitHeight + 20
                                radius: 8
                                color: modelData.role === "user" ? FluTheme.primaryColor : FluTheme.frameColor
                                anchors.right: modelData.role === "user" ? parent.right : undefined
                                anchors.left: modelData.role === "assistant" ? parent.left : undefined

                                ColumnLayout{
                                    id: bubble_content
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 6

                                    FluText{
                                        text: modelData.author + "  " + modelData.timestamp
                                        font: FluTextStyle.Caption
                                        color: modelData.role === "user" ? FluColors.White : FluTheme.fontSecondaryColor
                                    }

                                    FluText{
                                        Layout.fillWidth: true
                                        text: modelData.message
                                        wrapMode: Text.WordWrap
                                        color: modelData.role === "user" ? FluColors.White : FluTheme.fontPrimaryColor
                                    }
                                }
                            }
                        }
                    }

                    FluFrame{
                        Layout.fillWidth: true
                        padding: 10

                        ColumnLayout{
                            anchors.fill: parent
                            spacing: 8

                            FluMultilineTextBox{
                                id: input_prompt
                                Layout.fillWidth: true
                                Layout.preferredHeight: 110
                                placeholderText: qsTr("Ask Jira in natural language. Example: summarize blocked issues related to WPA this sprint.")
                                isCtrlEnterForNewline: true
                                onCommit: submitPrompt()
                            }

                            RowLayout{
                                Layout.fillWidth: true
                                spacing: 8

                                FluButton{
                                    text: qsTr("Use Selected Issue")
                                    onClicked: {
                                        if(selectedIssue.keyId){
                                            usePrompt(qsTr("Analyze %1 and tell me the risk for testing.").arg(selectedIssue.keyId))
                                        }
                                    }
                                }

                                Item{
                                    Layout.fillWidth: true
                                }

                                FluFilledButton{
                                    text: JiraBridge.loading ? qsTr("Running...") : qsTr("Send")
                                    disabled: JiraBridge.loading
                                    onClicked: submitPrompt()
                                }
                            }
                        }
                    }
                }
            }

            FluFrame{
                SplitView.preferredWidth: 360
                SplitView.minimumWidth: 300
                SplitView.maximumWidth: 460
                SplitView.fillHeight: true
                padding: 10

                ColumnLayout{
                    anchors.fill: parent
                    spacing: 10

                    FluText{
                        text: qsTr("Structured Results")
                        font: FluTextStyle.Subtitle
                    }

                    FluPivot{
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        FluPivotItem{
                            title: qsTr("Issues")
                            contentItem: Component{
                                Item{
                                    anchors.fill: parent

                                    ColumnLayout{
                                        anchors.fill: parent
                                        spacing: 10

                                        ListView{
                                            id: list_issue
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            visible: !issueDetailExpanded
                                            clip: true
                                            model: issueRows
                                            spacing: 8
                                            boundsBehavior: Flickable.StopAtBounds
                                            ScrollBar.vertical: FluScrollBar{}

                                            delegate: Item{
                                                width: list_issue.width
                                                height: issue_card_column.implicitHeight + 20

                                                Rectangle{
                                                    anchors.fill: parent
                                                    radius: 6
                                                    color: selectedIssue.keyId === modelData.keyId
                                                           ? FluTheme.frameActiveColor
                                                           : FluTheme.frameColor
                                                    border.width: selectedIssue.keyId === modelData.keyId ? 1 : 0
                                                    border.color: FluTheme.primaryColor
                                                }

                                                MouseArea{
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        JiraBridge.selectIssue(index, true, true)
                                                        issueDetailExpanded = true
                                                    }
                                                }

                                                Column{
                                                    id: issue_card_column
                                                    anchors.left: parent.left
                                                    anchors.right: parent.right
                                                    anchors.top: parent.top
                                                    anchors.margins: 10
                                                    spacing: 6

                                                    Item{
                                                        width: parent.width
                                                        height: Math.max(issue_key.implicitHeight, 8)

                                                        FluText{
                                                            id: issue_key
                                                            text: modelData.keyId
                                                            font: FluTextStyle.BodyStrong
                                                            color: FluTheme.primaryColor
                                                            anchors.left: parent.left
                                                            anchors.verticalCenter: parent.verticalCenter
                                                        }

                                                        MouseArea{
                                                            anchors.fill: issue_key
                                                            cursorShape: Qt.PointingHandCursor
                                                            onClicked: function(mouse){
                                                                var issueUrl = JiraBridge.issueBrowseUrl(modelData.keyId)
                                                                if(issueUrl.length > 0){
                                                                    Qt.openUrlExternally(issueUrl)
                                                                }
                                                                mouse.accepted = true
                                                            }
                                                        }

                                                        Rectangle{
                                                            width: 8
                                                            height: 8
                                                            radius: 4
                                                            color: issueStatusColor(modelData.status)
                                                            anchors.right: parent.right
                                                            anchors.verticalCenter: parent.verticalCenter
                                                        }
                                                    }

                                                    FluText{
                                                        width: parent.width
                                                        text: modelData.summary
                                                        wrapMode: Text.WordWrap
                                                    }

                                                    FluText{
                                                        width: parent.width
                                                        text: modelData.project + " | " + modelData.priority + " | " + modelData.status + " | " + modelData.assignee
                                                        font: FluTextStyle.Caption
                                                        color: FluTheme.fontSecondaryColor
                                                        wrapMode: Text.WordWrap
                                                    }
                                                }
                                            }
                                        }

                                        FluButton{
                                            Layout.alignment: Qt.AlignHCenter
                                            visible: !issueDetailExpanded && JiraBridge.canLoadMore()
                                            text: JiraBridge.loading ? qsTr("Loading...") : qsTr("Load More")
                                            disabled: JiraBridge.loading
                                            onClicked: JiraBridge.loadMore()
                                        }

                                        Item{
                                            Layout.fillWidth: true
                                            Layout.fillHeight: issueDetailExpanded
                                            implicitHeight: issueDetailExpanded ? 320 : (selected_issue_column.implicitHeight + 20)

                                            Rectangle{
                                                anchors.fill: parent
                                                radius: 6
                                                color: FluTheme.frameColor
                                                border.width: 1
                                                border.color: FluTheme.dividerColor
                                            }

                                            Column{
                                                id: selected_issue_column
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.top: parent.top
                                                anchors.margins: 10
                                                spacing: 6

                                                Item{
                                                    width: parent.width
                                                    height: Math.max(selected_issue_title.implicitHeight, 20)

                                                    FluText{
                                                        id: selected_issue_title
                                                        text: qsTr("Selected Issue")
                                                        font: FluTextStyle.BodyStrong
                                                        anchors.left: parent.left
                                                        anchors.verticalCenter: parent.verticalCenter
                                                    }

                                                    FluText{
                                                        visible: !!selectedIssue.keyId
                                                        text: issueDetailExpanded ? qsTr("Click to collapse") : qsTr("Click to expand")
                                                        font: FluTextStyle.Caption
                                                        color: FluTheme.fontSecondaryColor
                                                        anchors.right: parent.right
                                                        anchors.verticalCenter: parent.verticalCenter
                                                    }

                                                    MouseArea{
                                                        anchors.fill: parent
                                                        enabled: !!selectedIssue.keyId
                                                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                        onClicked: issueDetailExpanded = !issueDetailExpanded
                                                    }
                                                }

                                                FluText{
                                                    width: parent.width
                                                    text: selectedIssue.summary ? selectedIssue.summary : qsTr("No issue selected")
                                                    wrapMode: Text.WordWrap
                                                }

                                                RowLayout{
                                                    width: parent.width
                                                    spacing: 6
                                                    visible: !!selectedIssue.keyId

                                                    FluText{
                                                        text: selectedIssue.keyId
                                                        font: FluTextStyle.Caption
                                                        color: FluTheme.primaryColor
                                                    }

                                                    FluText{
                                                        Layout.fillWidth: true
                                                        text: selectedIssue.keyId
                                                              ? qsTr("| Updated %1 | %2 comments | %3 links").arg(selectedIssue.updatedAt).arg(selectedIssue.commentCount).arg(selectedIssue.linkCount)
                                                              : ""
                                                        font: FluTextStyle.Caption
                                                        color: FluTheme.fontSecondaryColor
                                                        wrapMode: Text.WordWrap
                                                    }

                                                    MouseArea{
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: {
                                                            var selectedIssueUrl = JiraBridge.issueBrowseUrl(selectedIssue.keyId)
                                                            if(selectedIssueUrl.length > 0){
                                                                Qt.openUrlExternally(selectedIssueUrl)
                                                            }
                                                        }
                                                    }
                                                }

                                                FluText{
                                                    visible: issueDetailExpanded && (selectedIssue.labels || []).length > 0
                                                    width: parent.width
                                                    text: qsTr("Labels") + ": " + (selectedIssue.labels || []).join(", ")
                                                    font: FluTextStyle.Caption
                                                    color: FluTheme.fontSecondaryColor
                                                    wrapMode: Text.WordWrap
                                                }

                                                Rectangle{
                                                    width: parent.width
                                                    height: 1
                                                    color: FluTheme.dividerColor
                                                }

                                                Flickable{
                                                    width: parent.width
                                                    height: issueDetailExpanded ? Math.max(160, parent.parent.height - y - 10) : 0
                                                    visible: issueDetailExpanded
                                                    contentHeight: selected_issue_detail_content.implicitHeight
                                                    clip: true
                                                    boundsBehavior: Flickable.StopAtBounds
                                                    ScrollBar.vertical: FluScrollBar{}

                                                    Column{
                                                        id: selected_issue_detail_content
                                                        width: parent.width
                                                        spacing: 10

                                                        Rectangle{
                                                            width: parent.width
                                                            radius: 6
                                                            color: FluTheme.itemNormalColor
                                                            border.width: 1
                                                            border.color: FluTheme.dividerColor
                                                            height: bug_status_column.implicitHeight + 20

                                                            Column{
                                                                id: bug_status_column
                                                                anchors.left: parent.left
                                                                anchors.right: parent.right
                                                                anchors.top: parent.top
                                                                anchors.margins: 10
                                                                spacing: 8

                                                                FluText{
                                                                    width: parent.width
                                                                    text: qsTr("Bug Status")
                                                                    font: FluTextStyle.BodyStrong
                                                                }

                                                                GridLayout{
                                                                    width: parent.width
                                                                    columns: 2
                                                                    columnSpacing: 12
                                                                    rowSpacing: 6

                                                                    FluText{ text: qsTr("Type") + ":"; font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor }
                                                                    FluText{ text: selectedIssue.issueType || "-"; font: FluTextStyle.Caption; wrapMode: Text.WordWrap }

                                                                    FluText{ text: qsTr("Priority") + ":"; font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor }
                                                                    FluText{ text: selectedIssue.priority || "-"; font: FluTextStyle.Caption; wrapMode: Text.WordWrap }

                                                                    FluText{ text: qsTr("Status") + ":"; font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor }
                                                                    FluText{ text: selectedIssue.status || "-"; font: FluTextStyle.Caption; wrapMode: Text.WordWrap }

                                                                    FluText{ text: qsTr("Resolution") + ":"; font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor }
                                                                    FluText{ text: selectedIssue.resolution || "-"; font: FluTextStyle.Caption; wrapMode: Text.WordWrap }

                                                                    FluText{ text: qsTr("Assignee") + ":"; font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor }
                                                                    FluText{ text: selectedIssue.assignee || "-"; font: FluTextStyle.Caption; wrapMode: Text.WordWrap }

                                                                    FluText{ text: qsTr("Reporter") + ":"; font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor }
                                                                    FluText{ text: selectedIssue.reporter || "-"; font: FluTextStyle.Caption; wrapMode: Text.WordWrap }

                                                                    FluText{ text: qsTr("Labels") + ":"; font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor }
                                                                    FluText{ text: (selectedIssue.labels || []).length > 0 ? selectedIssue.labels.join(", ") : "-"; font: FluTextStyle.Caption; wrapMode: Text.WordWrap }
                                                                }

                                                                FluText{
                                                                    visible: !!selectedIssue.detail
                                                                    width: parent.width
                                                                    text: qsTr("Description")
                                                                    font: FluTextStyle.BodyStrong
                                                                }

                                                                FluText{
                                                                    visible: !!selectedIssue.detail
                                                                    width: parent.width
                                                                    text: selectedIssue.detail || ""
                                                                    wrapMode: Text.WordWrap
                                                                    color: FluTheme.fontSecondaryColor
                                                                }
                                                            }
                                                        }

                                                        Rectangle{
                                                            width: parent.width
                                                            radius: 6
                                                            color: FluTheme.itemNormalColor
                                                            border.width: 1
                                                            border.color: FluTheme.dividerColor
                                                            height: comments_column.implicitHeight + 20

                                                            Column{
                                                                id: comments_column
                                                                anchors.left: parent.left
                                                                anchors.right: parent.right
                                                                anchors.top: parent.top
                                                                anchors.margins: 10
                                                                spacing: 8

                                                                FluText{
                                                                    width: parent.width
                                                                    text: qsTr("Comments")
                                                                    font: FluTextStyle.BodyStrong
                                                                }

                                                                FluText{
                                                                    visible: (selectedIssue.comments || []).length === 0
                                                                    width: parent.width
                                                                    text: qsTr("No comments yet.")
                                                                    font: FluTextStyle.Caption
                                                                    color: FluTheme.fontSecondaryColor
                                                                    wrapMode: Text.WordWrap
                                                                }

                                                                Repeater{
                                                                    model: selectedIssue.comments || []

                                                                    Rectangle{
                                                                        width: comments_column.width
                                                                        radius: 4
                                                                        color: FluTheme.frameColor
                                                                        border.width: 1
                                                                        border.color: FluTheme.dividerColor
                                                                        height: comment_text.implicitHeight + 16

                                                                        FluText{
                                                                            id: comment_text
                                                                            anchors.left: parent.left
                                                                            anchors.right: parent.right
                                                                            anchors.top: parent.top
                                                                            anchors.margins: 8
                                                                            text: modelData
                                                                            wrapMode: Text.WordWrap
                                                                            font: FluTextStyle.Caption
                                                                            color: FluTheme.fontSecondaryColor
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        FluPivotItem{
                            title: qsTr("Analysis")
                            contentItem: Component{
                                Item{
                                    anchors.fill: parent

                                    Flickable{
                                        anchors.fill: parent
                                        clip: true
                                        contentHeight: analysis_layout.implicitHeight
                                        ScrollBar.vertical: FluScrollBar{}

                                        ColumnLayout{
                                            id: analysis_layout
                                            width: parent.width
                                            spacing: 10

                                            FluFrame{
                                                Layout.fillWidth: true
                                                padding: 10

                                                ColumnLayout{
                                                    anchors.fill: parent
                                                    spacing: 6

                                                    FluText{
                                                        text: qsTr("AI Summary")
                                                        font: FluTextStyle.BodyStrong
                                                    }

                                                    FluText{
                                                        Layout.fillWidth: true
                                                        text: JiraBridge.analysisSummary()
                                                        wrapMode: Text.WordWrap
                                                    }
                                                }
                                            }

                                            FluFrame{
                                                Layout.fillWidth: true
                                                padding: 10

                                                ColumnLayout{
                                                    anchors.fill: parent
                                                    spacing: 6

                                                    FluText{
                                                        text: qsTr("Suggested Next Actions")
                                                        font: FluTextStyle.BodyStrong
                                                    }

                                                    Repeater{
                                                        model: analysisActions

                                                        FluText{
                                                            Layout.fillWidth: true
                                                            text: "- " + modelData
                                                            wrapMode: Text.WordWrap
                                                            color: FluTheme.fontSecondaryColor
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
