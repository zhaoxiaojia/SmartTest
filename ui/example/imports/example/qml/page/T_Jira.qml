import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluPage {
    id: page
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
    property var conversationHistoryRows: []
    property var jiraMcpSourceRows: [
        {id: "jira", name: "Jira", description: "Jira MCP", enabled: true},
        {id: "confluence", name: "Confluence", description: "Confluence MCP", enabled: false},
        {id: "soc_spec_search", name: "SoC Spec Search", description: "SoC specification search MCP", enabled: false},
        {id: "opengrok", name: "OpenGrok", description: "OpenGrok source search MCP", enabled: false},
        {id: "gerrit_scgit", name: "Gerrit SCGit", description: "Gerrit code review MCP", enabled: false},
        {id: "jenkins", name: "Jenkins", description: "Jenkins CI MCP", enabled: false}
    ]
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
    property color jiraChatPrimaryText: "#111111"
    property color jiraChatSecondaryText: "#6b7280"
    property color jiraChatHoverBg: "#ececec"
    property color jiraChatBorderColor: "#ececec"
    property color jiraChatAccentColor: "#ff5a1f"
    property int jiraChatFontSize: 16
    property real jiraChatLineHeight: 1.45

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
        conversationHistoryRows = JiraBridge.conversationHistoryRows()
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

    function enabledJiraMcpSources(){
        return jiraMcpSourceRows.filter(function(row){ return row.enabled })
    }

    function setJiraMcpSourceEnabled(sourceId, enabled){
        var rows = jiraMcpSourceRows.slice()
        for(var i = 0; i < rows.length; i++){
            if(rows[i].id === sourceId){
                rows[i] = {
                    id: rows[i].id,
                    name: rows[i].name,
                    description: rows[i].description,
                    enabled: enabled
                }
                break
            }
        }
        jiraMcpSourceRows = rows
    }

    function openJiraSourcePopup(){
        var composerPoint = conversation_composer.mapToItem(page, 0, 0)
        var anchorX = composerPoint.x + 180
        var anchorY = composerPoint.y - jira_source_popup.height - 12
        if(jira_source_chip && jira_source_chip.visible){
            var chipPoint = jira_source_chip.mapToItem(page, 0, 0)
            anchorX = chipPoint.x
            anchorY = chipPoint.y - jira_source_popup.height - 10
            console.debug("[JIRA_UI] source_anchor chipX=" + chipPoint.x + " chipY=" + chipPoint.y + " chipW=" + jira_source_chip.width + " chipH=" + jira_source_chip.height)
        }else{
            console.debug("[JIRA_UI] source_anchor fallback composerX=" + composerPoint.x + " composerY=" + composerPoint.y)
        }
        jira_source_popup.x = Math.max(12, Math.min(page.width - jira_source_popup.width - 12, anchorX))
        jira_source_popup.y = Math.max(12, anchorY)
        console.debug("[JIRA_UI] source_popup posX=" + jira_source_popup.x + " posY=" + jira_source_popup.y + " width=" + jira_source_popup.width + " height=" + jira_source_popup.height + " pageW=" + page.width + " pageH=" + page.height)
        jira_source_popup.open()
    }

    function escapeHtml(text){
        return (text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;")
    }

    function inlineMarkdown(text){
        var html = escapeHtml(text)
        html = html.replace(/`([^`]+)`/g, "<code style='font-family: Consolas, monospace; background-color: #f4f4f4; padding: 2px 5px; border-radius: 4px;'>$1</code>")
        html = html.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
        html = html.replace(/__([^_]+)__/g, "<b>$1</b>")
        html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, "<a href='$2'>$1</a>")
        return html
    }

    function paragraphHtml(lines){
        return "<p style='margin: 0 0 12px 0;'>" + inlineMarkdown(lines.join(" ")) + "</p>"
    }

    function renderMarkdown(text){
        var lines = (text || "").replace(/\r\n/g, "\n").split("\n")
        var html = "<div style='font-size: " + jiraChatFontSize + "px; line-height: " + jiraChatLineHeight + "; color: #111111;'>"
        var paragraph = []
        var inCode = false
        var codeLines = []
        var inList = false

        function flushParagraph(){
            if(paragraph.length > 0){
                html += paragraphHtml(paragraph)
                paragraph = []
            }
        }

        function closeList(){
            if(inList){
                html += "</ul>"
                inList = false
            }
        }

        for(var i = 0; i < lines.length; i++){
            var rawLine = lines[i]
            var line = rawLine.trim()
            if(line.indexOf("```") === 0){
                flushParagraph()
                closeList()
                if(inCode){
                    html += "<pre style='margin: 8px 0 14px 0; padding: 12px 14px; background-color: #f6f6f6; border-radius: 8px; white-space: pre-wrap;'><code style='font-family: Consolas, monospace; font-size: 14px;'>" + escapeHtml(codeLines.join("\n")) + "</code></pre>"
                    codeLines = []
                }
                inCode = !inCode
                continue
            }
            if(inCode){
                codeLines.push(rawLine)
                continue
            }
            if(line.length === 0){
                flushParagraph()
                closeList()
                continue
            }
            var heading = line.match(/^(#{1,6})\s+(.+)$/)
            if(heading){
                flushParagraph()
                closeList()
                var headingSizes = [0, 22, 20, 18, 16, 16, 16]
                var size = headingSizes[heading[1].length]
                html += "<h" + heading[1].length + " style='font-size: " + size + "px; line-height: 1.35; margin: 18px 0 9px 0; font-weight: 700;'>" + inlineMarkdown(heading[2]) + "</h" + heading[1].length + ">"
                continue
            }
            var bullet = line.match(/^[-*+]\s+(.+)$/)
            var ordered = line.match(/^\d+\.\s+(.+)$/)
            if(bullet || ordered){
                flushParagraph()
                if(!inList){
                    html += "<ul style='margin: 0 0 12px 22px;'>"
                    inList = true
                }
                html += "<li style='margin: 3px 0;'>" + inlineMarkdown((bullet || ordered)[1]) + "</li>"
                continue
            }
            var quote = line.match(/^>\s+(.+)$/)
            if(quote){
                flushParagraph()
                closeList()
                html += "<blockquote style='margin: 8px 0 14px 0; padding-left: 13px; border-left: 3px solid #d7d7d7; color: #4b5563;'>" + inlineMarkdown(quote[1]) + "</blockquote>"
                continue
            }
            closeList()
            paragraph.push(rawLine)
        }

        if(inCode){
            html += "<pre style='margin: 8px 0 14px 0; padding: 12px 14px; background-color: #f6f6f6; border-radius: 8px; white-space: pre-wrap;'><code style='font-family: Consolas, monospace; font-size: 14px;'>" + escapeHtml(codeLines.join("\n")) + "</code></pre>"
        }
        flushParagraph()
        closeList()
        html += "</div>"
        return html
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
        function onLoadingChanged(){ syncBridgeState() }
    }

    Connections{
        target: TranslateHelper
        function onCurrentChanged(){
            refreshOptionModels(false)
            syncBridgeState()
        }
    }

    FluMenu{
        id: conversation_more_menu

        FluMenuItem{
            text: qsTr("Clear Session")
            iconSource: FluentIcons.Delete
            onTriggered: JiraBridge.clearConversation()
        }
    }

    FluMenu{
        id: jira_composer_add_menu

        FluMenuItem{
            text: qsTr("Use Selected Issue")
            iconSource: FluentIcons.Page
            onTriggered: {
                if(selectedIssue.keyId){
                    usePrompt(qsTr("Analyze %1 and tell me the risk for testing.").arg(selectedIssue.keyId))
                }
            }
        }

        FluMenuItem{
            text: qsTr("Add Source")
            iconSource: FluentIcons.ConnectApp
            onTriggered: openJiraSourcePopup()
        }
    }

    Popup{
        id: jira_source_popup
        width: 320
        height: Math.min(360, page.height - 160)
        x: 12
        y: 12
        modal: false
        dim: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle{
            radius: 12
            color: FluTheme.windowBackgroundColor
            border.width: 1
            border.color: FluTheme.dividerColor
        }

        contentItem: ColumnLayout{
            spacing: 8

            FluText{
                Layout.fillWidth: true
                text: qsTr("Sources")
                font: FluTextStyle.BodyStrong
            }

            FluText{
                Layout.fillWidth: true
                text: qsTr("Jira MCP is enabled by default for Jira AI.")
                color: FluTheme.fontSecondaryColor
                font: FluTextStyle.Caption
                wrapMode: Text.WordWrap
            }

            ListView{
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: jiraMcpSourceRows
                spacing: 4
                ScrollBar.vertical: FluScrollBar{}

                delegate: Rectangle{
                    width: ListView.view.width
                    height: 44
                    radius: 8
                    color: "transparent"

                    RowLayout{
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 10

                        Image{
                            visible: modelData.id === "jira"
                            Layout.preferredWidth: 18
                            Layout.preferredHeight: 18
                            source: "qrc:/example/res/svg/jira-software-icon.svg"
                            fillMode: Image.PreserveAspectFit
                        }

                        FluIcon{
                            visible: modelData.id !== "jira"
                            Layout.preferredWidth: 18
                            iconSource: FluentIcons.ConnectApp
                            iconSize: 16
                            iconColor: jiraChatPrimaryText
                        }

                        ColumnLayout{
                            Layout.fillWidth: true
                            spacing: 1

                            FluText{
                                Layout.fillWidth: true
                                text: modelData.name
                                color: jiraChatPrimaryText
                                elide: Text.ElideRight
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: modelData.description
                                color: jiraChatSecondaryText
                                font: FluTextStyle.Caption
                                elide: Text.ElideRight
                            }
                        }

                        JiraSourceSwitch{
                            checked: modelData.enabled
                            onClicked: setJiraMcpSourceEnabled(modelData.id, !modelData.enabled)
                        }
                    }
                }
            }
        }
        padding: 12
    }

    FluPopup{
        id: conversation_history_popup
        width: Math.min(640, page.width - 80)
        height: Math.min(560, page.height - 80)
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        Rectangle{
            anchors.fill: parent
            radius: 8
            color: FluTheme.windowBackgroundColor
            border.width: 1
            border.color: FluTheme.dividerColor

            ColumnLayout{
                anchors.fill: parent
                spacing: 0

                RowLayout{
                    Layout.fillWidth: true
                    Layout.preferredHeight: 58
                    Layout.leftMargin: 18
                    Layout.rightMargin: 12
                    spacing: 8

                    FluText{
                        Layout.fillWidth: true
                        text: qsTr("Conversation History")
                        font: FluTextStyle.Subtitle
                    }

                    FluIconButton{
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        iconSource: FluentIcons.Cancel
                        iconSize: 13
                        text: qsTr("Close")
                        normalColor: "transparent"
                        hoverColor: FluTheme.itemHoverColor
                        onClicked: conversation_history_popup.close()
                    }
                }

                Rectangle{
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: FluTheme.dividerColor
                }

                ListView{
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.margins: 10
                    clip: true
                    spacing: 6
                    model: conversationHistoryRows
                    ScrollBar.vertical: FluScrollBar{}

                    delegate: Rectangle{
                        width: ListView.view.width
                        height: 76
                        radius: 8
                        color: "transparent"

                        ColumnLayout{
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            anchors.topMargin: 8
                            anchors.bottomMargin: 8
                            spacing: 3

                            RowLayout{
                                Layout.fillWidth: true

                                FluText{
                                    Layout.fillWidth: true
                                    text: modelData.title
                                    font: FluTextStyle.BodyStrong
                                    elide: Text.ElideRight
                                }

                                FluText{
                                    text: modelData.updatedAt
                                    color: FluTheme.fontSecondaryColor
                                    font: FluTextStyle.Caption
                                }
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: modelData.preview
                                color: FluTheme.fontSecondaryColor
                                elide: Text.ElideRight
                                font: FluTextStyle.Caption
                            }

                            FluText{
                                text: qsTr("%1 messages").arg(modelData.messageCount)
                                color: FluTheme.fontSecondaryColor
                                font: FluTextStyle.Caption
                            }
                        }

                        MouseArea{
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onEntered: parent.color = FluTheme.itemHoverColor
                            onExited: parent.color = "transparent"
                            onClicked: {
                                JiraBridge.restoreConversation(modelData.id)
                                conversation_history_popup.close()
                            }
                        }
                    }

                    FluText{
                        anchors.centerIn: parent
                        visible: conversationHistoryRows.length === 0
                        text: qsTr("No conversation history yet.")
                        color: FluTheme.fontSecondaryColor
                    }
                }
            }
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
                padding: 0

                Rectangle{
                    anchors.fill: parent
                    color: "#ffffff"
                    radius: 6
                    border.width: 1
                    border.color: jiraChatBorderColor

                    Rectangle{
                        id: conversation_top_bar
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 52
                        color: "#ffffff"

                        Rectangle{
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: jiraChatBorderColor
                        }

                        RowLayout{
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 14
                            spacing: 8

                            Image{
                                Layout.preferredWidth: 22
                                Layout.preferredHeight: 22
                                source: "qrc:/example/res/svg/deepseek-logo-icon.svg"
                                fillMode: Image.PreserveAspectFit
                            }

                            FluText{
                                text: qsTr("Jira AI Chat")
                                color: jiraChatPrimaryText
                                font: FluTextStyle.Subtitle
                            }

                            FluText{
                                text: qsTr("Preview")
                                color: jiraChatSecondaryText
                                font: FluTextStyle.Body
                            }

                            FluIcon{
                                iconSource: FluentIcons.ChevronDown
                                iconSize: 12
                                iconColor: jiraChatSecondaryText
                            }

                            Item{ Layout.fillWidth: true }

                            ConversationTopAction{
                                iconSource: FluentIcons.History
                                text: qsTr("History")
                                onClicked: {
                                    conversationHistoryRows = JiraBridge.conversationHistoryRows()
                                    conversation_history_popup.open()
                                }
                            }

                            FluIconButton{
                                Layout.preferredWidth: 34
                                Layout.preferredHeight: 34
                                iconSource: FluentIcons.More
                                iconSize: 14
                                text: qsTr("More")
                                normalColor: "transparent"
                                hoverColor: jiraChatHoverBg
                                onClicked: conversation_more_menu.popup()
                            }
                        }
                    }

                    ListView{
                        id: list_conversation
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: conversation_top_bar.bottom
                        anchors.bottom: conversation_composer.top
                        anchors.bottomMargin: 10
                        clip: true
                        spacing: 24
                        model: conversationRows
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: FluScrollBar{}

                        footer: Item{
                            width: list_conversation.width
                            height: JiraBridge.loading ? thinking_row.implicitHeight + 28 : 0
                            visible: JiraBridge.loading

                            Row{
                                id: thinking_row
                                width: Math.min(1000, parent.width - 48)
                                anchors.horizontalCenter: parent.horizontalCenter
                                spacing: 8

                                FluText{
                                    text: qsTr("Thinking...")
                                    color: jiraChatSecondaryText
                                    font.family: FluTextStyle.family
                                    font.pixelSize: jiraChatFontSize
                                    lineHeight: jiraChatLineHeight
                                    lineHeightMode: Text.ProportionalHeight
                                }

                                FluProgressRing{
                                    width: 16
                                    height: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }

                        delegate: Item{
                            width: list_conversation.width
                            height: message_row.implicitHeight

                            Item{
                                id: message_row
                                width: Math.min(1000, parent.width - 48)
                                anchors.horizontalCenter: parent.horizontalCenter
                                implicitHeight: Math.max(user_bubble.implicitHeight, assistant_column.implicitHeight) + 4
                                readonly property bool isUser: modelData.role === "user"

                                Rectangle{
                                    id: user_bubble
                                    visible: message_row.isUser
                                    width: Math.min(470, parent.width * 0.58)
                                    implicitHeight: user_text.implicitHeight + user_actions.implicitHeight + 28
                                    radius: 18
                                    color: "#f1f1f1"
                                    anchors.right: parent.right

                                    Column{
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.margins: 12
                                        spacing: 6

                                        FluText{
                                            id: user_text
                                            width: parent.width
                                            text: modelData.message
                                            color: jiraChatPrimaryText
                                            font.family: FluTextStyle.family
                                            font.pixelSize: jiraChatFontSize
                                            wrapMode: Text.WordWrap
                                            lineHeight: jiraChatLineHeight
                                            lineHeightMode: Text.ProportionalHeight
                                        }

                                        Row{
                                            id: user_actions
                                            spacing: 8

                                            FluIconButton{
                                                width: 26
                                                height: 26
                                                iconSource: FluentIcons.Copy
                                                iconSize: 12
                                                text: qsTr("Copy")
                                                onClicked: JiraBridge.copyText(modelData.message)
                                            }

                                            FluIconButton{
                                                width: 26
                                                height: 26
                                                iconSource: FluentIcons.RepeatAll
                                                iconSize: 12
                                                text: qsTr("Resend")
                                                disabled: JiraBridge.loading
                                                onClicked: JiraBridge.retryPrompt(modelData.message)
                                            }
                                        }
                                    }
                                }

                                Column{
                                    id: assistant_column
                                    visible: !message_row.isUser
                                    width: Math.min(760, parent.width * 0.82)
                                    anchors.left: parent.left
                                    spacing: 11

                                    Text{
                                        width: parent.width
                                        text: renderMarkdown(modelData.message)
                                        textFormat: Text.RichText
                                        wrapMode: Text.WordWrap
                                        color: jiraChatPrimaryText
                                        linkColor: "#0f62fe"
                                        font.family: FluTextStyle.family
                                        font.pixelSize: jiraChatFontSize
                                        lineHeight: jiraChatLineHeight
                                        lineHeightMode: Text.ProportionalHeight
                                        renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
                                        onLinkActivated: (link)=> Qt.openUrlExternally(link)
                                    }
                                }
                            }
                        }
                    }

                    Column{
                        id: conversation_composer
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 8
                        spacing: 4

                        Rectangle{
                            width: Math.max(320, parent.width - 48)
                            height: 106
                            anchors.horizontalCenter: parent.horizontalCenter
                            radius: 22
                            color: "#ffffff"
                            border.width: 2
                            border.color: jiraChatAccentColor

                            FluMultilineTextBox{
                                id: input_prompt
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.bottom: conversation_composer_tools.top
                                anchors.leftMargin: 18
                                anchors.rightMargin: 18
                                anchors.topMargin: 12
                                anchors.bottomMargin: 2
                                placeholderText: qsTr("Ask anything")
                                disabled: JiraBridge.loading
                                isCtrlEnterForNewline: true
                                background: Item{}
                                color: jiraChatPrimaryText
                                placeholderNormalColor: "#8a8a8a"
                                placeholderFocusColor: "#8a8a8a"
                                onCommit: submitPrompt()
                            }

                            RowLayout{
                                id: conversation_composer_tools
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                anchors.bottomMargin: 10
                                height: 30
                                spacing: 8

                                FluIconButton{
                                    Layout.preferredWidth: 30
                                    Layout.preferredHeight: 30
                                    iconSource: FluentIcons.Add
                                    iconSize: 15
                                    text: qsTr("More")
                                    normalColor: "transparent"
                                    hoverColor: jiraChatHoverBg
                                    onClicked: jira_composer_add_menu.popup()
                                }

                                JiraToolChip{
                                    iconSource: FluentIcons.Flashlight
                                    text: qsTr("Quick")
                                }

                                JiraToolChip{
                                    id: jira_source_chip
                                    iconSource: FluentIcons.ConnectApp
                                    text: qsTr("Sources")
                                    clickable: true
                                    onClicked: openJiraSourcePopup()
                                }

                                Repeater{
                                    model: enabledJiraMcpSources()

                                    JiraToolChip{
                                        iconSource: FluentIcons.ConnectApp
                                        imageSource: modelData.id === "jira" ? "qrc:/example/res/svg/jira-software-icon.svg" : ""
                                        text: modelData.name
                                    }
                                }

                                Item{
                                    Layout.fillWidth: true
                                }

                                FluIconButton{
                                    Layout.preferredWidth: 30
                                    Layout.preferredHeight: 30
                                    iconSource: FluentIcons.Microphone
                                    iconSize: 15
                                    text: qsTr("Voice")
                                    normalColor: "transparent"
                                    hoverColor: jiraChatHoverBg
                                }

                                Rectangle{
                                    Layout.preferredWidth: 34
                                    Layout.preferredHeight: 34
                                    radius: 17
                                    color: JiraBridge.loading || (input_prompt.text || "").trim().length === 0 ? "#c9c9c9" : "#000000"

                                    FluIcon{
                                        anchors.centerIn: parent
                                        iconSource: FluentIcons.Send
                                        iconSize: 15
                                        iconColor: "#ffffff"
                                    }

                                    MouseArea{
                                        anchors.fill: parent
                                        enabled: !JiraBridge.loading && (input_prompt.text || "").trim().length > 0
                                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        onClicked: submitPrompt()
                                    }
                                }
                            }
                        }

                        FluText{
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: qsTr("SmartTest AI can make mistakes. Verify important information.")
                            color: jiraChatSecondaryText
                            font: FluTextStyle.Caption
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

                                                    Item{
                                                        implicitWidth: selected_issue_key_text.implicitWidth
                                                        implicitHeight: selected_issue_key_text.implicitHeight

                                                        FluText{
                                                            id: selected_issue_key_text
                                                            text: selectedIssue.keyId || ""
                                                            font: FluTextStyle.Caption
                                                            color: FluTheme.primaryColor
                                                        }

                                                        MouseArea{
                                                            anchors.fill: parent
                                                            enabled: (selectedIssue.keyId || "").length > 0
                                                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                            onClicked: {
                                                                var selectedIssueUrl = JiraBridge.issueBrowseUrl(selectedIssue.keyId || "")
                                                                if(selectedIssueUrl.length > 0){
                                                                    Qt.openUrlExternally(selectedIssueUrl)
                                                                }
                                                            }
                                                        }
                                                    }

                                                    FluText{
                                                        Layout.fillWidth: true
                                                        text: (selectedIssue.keyId || "").length > 0
                                                              ? qsTr("| Updated %1 | %2 comments | %3 links")
                                                                    .arg(selectedIssue.updatedAt || "")
                                                                    .arg(selectedIssue.commentCount || 0)
                                                                    .arg(selectedIssue.linkCount || 0)
                                                              : ""
                                                        font: FluTextStyle.Caption
                                                        color: FluTheme.fontSecondaryColor
                                                        wrapMode: Text.WordWrap
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

    component ConversationTopAction: Item{
        id: top_action
        signal clicked()
        property int iconSource: 0
        property string text: ""
        implicitWidth: action_row.implicitWidth
        implicitHeight: 34

        RowLayout{
            id: action_row
            anchors.centerIn: parent
            spacing: 5

            FluIcon{
                iconSource: top_action.iconSource
                iconSize: 14
                iconColor: jiraChatPrimaryText
            }

            FluText{
                text: top_action.text
                color: jiraChatPrimaryText
                font: FluTextStyle.Body
            }
        }

        MouseArea{
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: top_action.clicked()
        }
    }

    component JiraToolChip: Rectangle{
        id: tool_chip
        signal clicked()
        property int iconSource: 0
        property string imageSource: ""
        property string text: ""
        property bool clickable: false
        Layout.preferredWidth: Math.min(150, chip_row.implicitWidth + 16)
        Layout.preferredHeight: 28
        radius: 14
        color: "#ffffff"
        border.width: 0

        RowLayout{
            id: chip_row
            anchors.centerIn: parent
            spacing: 5

            Image{
                visible: tool_chip.imageSource.length > 0
                Layout.preferredWidth: 15
                Layout.preferredHeight: 15
                source: tool_chip.imageSource
                fillMode: Image.PreserveAspectFit
            }

            FluIcon{
                visible: tool_chip.imageSource.length === 0
                iconSource: tool_chip.iconSource
                iconSize: 15
                iconColor: "#0f62fe"
            }

            FluText{
                Layout.maximumWidth: 96
                text: tool_chip.text
                color: "#0f62fe"
                elide: Text.ElideRight
                font: FluTextStyle.Body
            }
        }

        MouseArea{
            anchors.fill: parent
            enabled: tool_chip.clickable
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: tool_chip.clicked()
        }
    }

    component JiraSourceSwitch: Rectangle{
        id: source_switch
        signal clicked()
        property bool checked: false
        Layout.preferredWidth: 38
        Layout.preferredHeight: 22
        radius: 11
        color: checked ? "#111111" : "#eeeeee"
        border.width: 1
        border.color: checked ? "#111111" : "#d0d0d0"

        Rectangle{
            width: 16
            height: 16
            radius: 8
            color: checked ? "#ffffff" : "#8a8a8a"
            anchors.verticalCenter: parent.verticalCenter
            x: checked ? parent.width - width - 3 : 3

            Behavior on x{
                NumberAnimation{ duration: 120 }
            }
        }

        MouseArea{
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: source_switch.clicked()
        }
    }
}
