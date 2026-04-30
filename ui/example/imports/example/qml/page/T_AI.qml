import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.platform 1.1
import FluentUI 1.0

FluPage {
    id: page
    title: qsTr("AI Assistant")

    property var sessionRows: []
    property var projectRows: []
    property var messageRows: []
    property var attachmentRows: []
    property var mcpSourceRows: []
    property string selectedSessionId: ""
    property string selectedSessionTitle: ""
    property string selectedProjectId: ""
    property string expandedProjectId: ""
    property bool sidebarCollapsed: false
    property color pageBg: "#ffffff"
    property color sidebarBg: "#f7f7f7"
    property color hoverBg: "#ececec"
    property color selectedBg: "#e8e8e8"
    property color primaryText: "#111111"
    property color secondaryText: "#6b7280"
    property color borderColor: "#ececec"
    property color accentColor: "#ff5a1f"
    property int chatTrackWidth: 1000
    property int assistantContentWidth: 760
    property int chatFontSize: 16
    property real chatLineHeight: 1.45

    function syncState(){
        sessionRows = AIBridge.sessions()
        projectRows = AIBridge.projects()
        messageRows = AIBridge.messages()
        attachmentRows = AIBridge.attachments()
        mcpSourceRows = AIBridge.mcpSources()
        if(selectedProjectId.length === 0){
            selectedSessionId = AIBridge.currentSessionId()
        }
        Qt.callLater(function(){
            if(list_messages.count > 0){
                list_messages.positionViewAtEnd()
            }
        })
    }

    function sendPrompt(){
        var promptText = (input_prompt.text || "").trim()
        if(promptText.length === 0 || AIBridge.loading){
            return
        }
        AIBridge.sendMessage(promptText)
        input_prompt.text = ""
    }

    function sessionTitle(row, fallback){
        var title = ((row || {}).title || "").trim()
        return title.length > 0 ? title : fallback
    }

    function currentSessionTitle(){
        for(var i = 0; i < sessionRows.length; i++){
            if(sessionRows[i].id === selectedSessionId){
                return sessionTitle(sessionRows[i], qsTr("Untitled Chat"))
            }
        }
        return qsTr("Untitled Chat")
    }

    function filteredSessions(keyword){
        var query = (keyword || "").trim().toLowerCase()
        if(query.length === 0){
            return sessionRows
        }
        return sessionRows.filter(function(row){
            return sessionTitle(row, qsTr("Untitled Chat")).toLowerCase().indexOf(query) !== -1
        })
    }

    function projectById(projectId){
        for(var i = 0; i < projectRows.length; i++){
            if(projectRows[i].id === projectId){
                return projectRows[i]
            }
        }
        return null
    }

    function projectTitle(projectId){
        var project = projectById(projectId)
        if(!project){
            return ""
        }
        return displayProjectTitle(project)
    }

    function displayProjectTitle(project){
        if(!project){
            return ""
        }
        if(project.id === "default-new-project"){
            return qsTr("New Project")
        }
        if(project.id === "default-test-notes" && project.title === "Test Notes"){
            return qsTr("Test Notes")
        }
        return project.title
    }

    function projectSessionIds(projectId){
        var project = projectById(projectId)
        return project ? (project.session_ids || []) : []
    }

    function projectSessions(projectId){
        var ids = projectSessionIds(projectId)
        return sessionRows.filter(function(row){ return ids.indexOf(row.id) !== -1 })
    }

    function isProjectSession(projectId, sessionId){
        return projectSessionIds(projectId).indexOf(sessionId) !== -1
    }

    function selectProject(projectId){
        selectedProjectId = projectId
        expandedProjectId = projectId
        selectedSessionId = ""
    }

    function selectChat(sessionId){
        selectedProjectId = ""
        AIBridge.selectSession(sessionId)
    }

    function formatSessionDate(seconds){
        var value = Number(seconds || 0)
        if(value <= 0){
            return ""
        }
        var date = new Date(value * 1000)
        return Qt.locale().toString(date, "MMM d")
    }

    function enabledMcpSources(){
        return mcpSourceRows.filter(function(row){ return row.enabled })
    }

    function openSourcePopup(){
        var composerPoint = composer.mapToItem(page, 0, 0)
        var anchorX = composerPoint.x + 190
        var anchorY = composerPoint.y - source_popup.height - 12
        source_popup.x = Math.max(sidebar.width + 12, Math.min(page.width - source_popup.width - 12, anchorX))
        source_popup.y = Math.max(12, anchorY)
        console.debug("[AI_UI] source_popup_open x=" + source_popup.x + " y=" + source_popup.y + " w=" + source_popup.width + " h=" + source_popup.height + " pageW=" + page.width + " pageH=" + page.height)
        source_popup.open()
    }

    function accountName(){
        var name = (AuthBridge.username || "").trim()
        if(name.length === 0){
            return "Chao.li"
        }
        var slashIndex = name.lastIndexOf("\\")
        return slashIndex >= 0 ? name.substring(slashIndex + 1) : name
    }

    function accountInitials(){
        var name = accountName()
        var parts = name.split(/[.\s_-]+/).filter(function(item){ return item.length > 0 })
        if(parts.length >= 2){
            return (parts[0][0] + parts[1][0]).toUpperCase()
        }
        return name.substring(0, Math.min(2, name.length)).toUpperCase()
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
        var html = "<div style='font-size: " + chatFontSize + "px; line-height: " + chatLineHeight + "; color: #111111;'>"
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

    Component.onCompleted: syncState()

    Connections{
        target: AIBridge
        function onStateChanged(){ syncState() }
        function onLoadingChanged(){ syncState() }
    }

    FileDialog{
        id: file_dialog
        title: qsTr("Attach File")
        nameFilters: [
            qsTr("Text files") + " (*.txt *.log *.md *.json *.yaml *.yml *.xml *.py *.csv *.ini *.cfg)",
            qsTr("All files") + " (*)"
        ]
        onAccepted: AIBridge.addAttachmentFromUrl(currentFile)
    }

    FluMenu{
        id: composer_add_menu

        FluMenuItem{
            text: qsTr("Attach File")
            iconSource: FluentIcons.Attach
            onTriggered: file_dialog.open()
        }

        FluMenuItem{
            text: qsTr("Add Source")
            iconSource: FluentIcons.ConnectApp
            onTriggered: openSourcePopup()
        }
    }

    Popup{
        id: source_popup
        width: 320
        height: Math.min(360, page.height - 160)
        x: sidebar.width + 12
        y: 12
        modal: false
        dim: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle{
            radius: 12
            color: pageBg
            border.width: 1
            border.color: "#d8d8d8"
        }

        contentItem: ColumnLayout{
            spacing: 8

            FluText{
                Layout.fillWidth: true
                text: qsTr("Sources")
                color: primaryText
                font: FluTextStyle.BodyStrong
            }

            FluText{
                Layout.fillWidth: true
                text: qsTr("Choose MCP sources for this chat.")
                color: secondaryText
                font: FluTextStyle.Caption
                wrapMode: Text.WordWrap
            }

            ListView{
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: mcpSourceRows
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
                            iconColor: primaryText
                        }

                        ColumnLayout{
                            Layout.fillWidth: true
                            spacing: 1

                            FluText{
                                Layout.fillWidth: true
                                text: modelData.name
                                color: primaryText
                                elide: Text.ElideRight
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: modelData.description
                                color: secondaryText
                                font: FluTextStyle.Caption
                                elide: Text.ElideRight
                            }
                        }

                        SourceSwitch{
                            checked: modelData.enabled
                            onClicked: AIBridge.setMcpSourceEnabled(modelData.id, !modelData.enabled)
                        }
                    }

                    MouseArea{
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                        onEntered: parent.color = hoverBg
                        onExited: parent.color = "transparent"
                    }
                }
            }
        }
        padding: 12
    }

    FluMenu{
        id: session_menu
        property string sessionId: ""
        property string titleText: ""

        FluMenuItem{
            text: qsTr("Start group chat")
            iconSource: FluentIcons.People
        }

        FluMenuItem{
            text: qsTr("View files in chat")
            iconSource: FluentIcons.OpenFile
        }

        FluMenu{
            title: qsTr("Move to project")

            Repeater{
                model: projectRows.filter(function(project){ return project.id !== "default-new-project" })

                FluMenuItem{
                    text: displayProjectTitle(modelData)
                    iconSource: FluentIcons.Folder
                    onTriggered: AIBridge.moveSessionToProject(session_menu.sessionId, modelData.id)
                }
            }
        }

        FluMenuItem{
            text: qsTr("Pin chat")
            iconSource: FluentIcons.Pinned
        }

        FluMenuItem{
            text: qsTr("Archive")
            iconSource: FluentIcons.Save
        }

        FluMenuSeparator{}

        FluMenuItem{
            text: qsTr("Rename")
            iconSource: FluentIcons.Edit
            onTriggered: rename_dialog.showDialog(session_menu.sessionId, session_menu.titleText)
        }

        FluMenuItem{
            text: qsTr("Share")
            iconSource: FluentIcons.Share
            onTriggered: share_dialog.showDialog(session_menu.sessionId, session_menu.titleText)
        }

        FluMenuSeparator{}

        FluMenuItem{
            text: qsTr("Delete")
            iconSource: FluentIcons.Delete
            onTriggered: delete_dialog.showDialog(session_menu.sessionId, session_menu.titleText)
        }
    }

    FluMenu{
        id: project_menu
        property string projectId: ""
        property string titleText: ""

        FluMenuItem{
            text: qsTr("Share")
            onTriggered: AIBridge.copyText(project_menu.titleText)
        }

        FluMenuItem{
            text: qsTr("Rename project")
            onTriggered: rename_project_dialog.showDialog(project_menu.projectId, project_menu.titleText)
        }

        FluMenuSeparator{}

        FluMenuItem{
            text: qsTr("Delete project")
            onTriggered: delete_project_dialog.showDialog(project_menu.projectId, project_menu.titleText)
        }
    }

    FluContentDialog{
        id: rename_dialog
        property string sessionId: ""
        property string titleText: ""
        title: qsTr("Rename chat")
        negativeText: qsTr("Cancel")
        positiveText: qsTr("Save")
        contentDelegate: Component{
            Item{
                implicitWidth: parent.width
                implicitHeight: 72

                FluTextBox{
                    id: rename_text
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    onTextChanged: rename_dialog.titleText = text
                    Component.onCompleted: {
                        text = rename_dialog.titleText
                        selectAll()
                        forceActiveFocus()
                    }
                    Keys.onReturnPressed: rename_dialog.acceptRename()
                }
            }
        }
        onPositiveClicked: acceptRename()
        function showDialog(sessionId, titleText){
            rename_dialog.sessionId = sessionId
            rename_dialog.titleText = titleText
            rename_dialog.open()
        }
        function acceptRename(){
            var cleanTitle = (rename_dialog.titleText || "").trim()
            if(cleanTitle.length > 0){
                AIBridge.renameSession(rename_dialog.sessionId, cleanTitle)
            }
            rename_dialog.close()
        }
    }

    FluContentDialog{
        id: delete_dialog
        property string sessionId: ""
        title: qsTr("Delete chat?")
        message: qsTr("This chat will be removed from SmartTest chat history.")
        negativeText: qsTr("Cancel")
        positiveText: qsTr("Delete")
        onPositiveClicked: {
            AIBridge.deleteSession(delete_dialog.sessionId)
            delete_dialog.close()
        }
        function showDialog(sessionId, titleText){
            delete_dialog.sessionId = sessionId
            delete_dialog.title = qsTr("Delete chat?")
            delete_dialog.message = qsTr("Delete \"%1\" from SmartTest chat history?").arg(titleText)
            delete_dialog.open()
        }
    }

    FluContentDialog{
        id: rename_project_dialog
        property string projectId: ""
        property string titleText: ""
        title: qsTr("Rename project")
        negativeText: qsTr("Cancel")
        positiveText: qsTr("Save")
        contentDelegate: Component{
            Item{
                implicitWidth: parent.width
                implicitHeight: 72

                FluTextBox{
                    id: rename_project_text
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    onTextChanged: rename_project_dialog.titleText = text
                    Component.onCompleted: {
                        text = rename_project_dialog.titleText
                        selectAll()
                        forceActiveFocus()
                    }
                    Keys.onReturnPressed: rename_project_dialog.acceptRename()
                }
            }
        }
        onPositiveClicked: acceptRename()
        function showDialog(projectId, titleText){
            rename_project_dialog.projectId = projectId
            rename_project_dialog.titleText = titleText
            rename_project_dialog.open()
        }
        function acceptRename(){
            var cleanTitle = (rename_project_dialog.titleText || "").trim()
            if(cleanTitle.length > 0){
                AIBridge.renameProject(rename_project_dialog.projectId, cleanTitle)
            }
            rename_project_dialog.close()
        }
    }

    FluContentDialog{
        id: delete_project_dialog
        property string projectId: ""
        title: qsTr("Delete project?")
        message: qsTr("Project chats will remain in chat history.")
        negativeText: qsTr("Cancel")
        positiveText: qsTr("Delete")
        onPositiveClicked: {
            if(selectedProjectId === delete_project_dialog.projectId){
                selectedProjectId = ""
                expandedProjectId = ""
            }
            AIBridge.deleteProject(delete_project_dialog.projectId)
            delete_project_dialog.close()
        }
        function showDialog(projectId, titleText){
            delete_project_dialog.projectId = projectId
            delete_project_dialog.title = qsTr("Delete project?")
            delete_project_dialog.message = qsTr("Delete \"%1\"? Project chats will remain in chat history.").arg(titleText)
            delete_project_dialog.open()
        }
    }

    FluContentDialog{
        id: share_dialog
        property string sessionId: ""
        property string titleText: ""
        property string shareLink: ""
        title: qsTr("Share chat")
        negativeText: qsTr("Close")
        positiveText: shareLink.length > 0 ? qsTr("Copy Link") : qsTr("Create Link")
        contentDelegate: Component{
            Item{
                implicitWidth: parent.width
                implicitHeight: 154

                ColumnLayout{
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    anchors.topMargin: 8
                    anchors.bottomMargin: 10
                    spacing: 8

                    FluText{
                        Layout.fillWidth: true
                        text: qsTr("A local HTML snapshot will be created. Anyone who can access the copied file link can view this chat snapshot.")
                        color: secondaryText
                        wrapMode: Text.WordWrap
                        font: FluTextStyle.Caption
                    }

                    FluTextBox{
                        Layout.fillWidth: true
                        text: share_dialog.titleText
                        onTextChanged: share_dialog.titleText = text
                    }

                    FluTextBox{
                        Layout.fillWidth: true
                        readOnly: true
                        text: share_dialog.shareLink
                        placeholderText: qsTr("Create a link to copy it")
                    }

                    FluTextButton{
                        visible: share_dialog.shareLink.length > 0
                        text: qsTr("Delete shared link")
                        onClicked: {
                            AIBridge.deleteShareLink(share_dialog.sessionId)
                            share_dialog.shareLink = ""
                        }
                    }
                }
            }
        }
        onPositiveClicked: {
            if(share_dialog.shareLink.length === 0){
                share_dialog.shareLink = AIBridge.createShareLink(share_dialog.sessionId, share_dialog.titleText)
            }else{
                AIBridge.copyText(share_dialog.shareLink)
            }
        }
        function showDialog(sessionId, titleText){
            share_dialog.sessionId = sessionId
            share_dialog.titleText = titleText
            share_dialog.shareLink = ""
            share_dialog.open()
        }
    }

    FluContentDialog{
        id: project_dialog
        property string projectName: ""
        title: qsTr("Create project")
        negativeText: qsTr("Cancel")
        positiveText: qsTr("Create project")
        contentDelegate: Component{
            Item{
                implicitWidth: parent.width
                implicitHeight: 152

                ColumnLayout{
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    anchors.topMargin: 6
                    anchors.bottomMargin: 10
                    spacing: 12

                    FluText{
                        text: qsTr("Project name")
                        color: primaryText
                        font: FluTextStyle.Body
                    }

                    FluTextBox{
                        id: project_name_text
                        Layout.fillWidth: true
                        placeholderText: qsTr("Project name")
                        onTextChanged: project_dialog.projectName = text
                        Component.onCompleted: forceActiveFocus()
                        Keys.onReturnPressed: project_dialog.acceptProject()
                    }

                    Rectangle{
                        Layout.fillWidth: true
                        Layout.preferredHeight: 72
                        radius: 8
                        color: "#f2f2f2"

                        RowLayout{
                            z: 1
                            anchors.fill: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 14
                            spacing: 10

                            FluIcon{
                                Layout.preferredWidth: 18
                                iconSource: FluentIcons.Lightbulb
                                iconSize: 17
                                iconColor: secondaryText
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: qsTr("Projects are collections of chats. They can share context and uploaded files for continued work.")
                                color: secondaryText
                                wrapMode: Text.WordWrap
                                font: FluTextStyle.Caption
                            }
                        }
                    }
                }
            }
        }
        onPositiveClicked: acceptProject()
        function showDialog(){
            project_dialog.projectName = ""
            project_dialog.open()
        }
        function acceptProject(){
            var cleanName = (project_dialog.projectName || "").trim()
            if(cleanName.length === 0){
                return
            }
            var projectId = AIBridge.createProject(cleanName)
            selectProject(projectId)
            project_dialog.close()
        }
    }

    FluPopup{
        id: search_popup
        width: Math.min(680, page.width - 80)
        height: Math.min(470, page.height - 80)
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        Rectangle{
            anchors.fill: parent
            radius: 8
            color: pageBg
            border.width: 1
            border.color: "#d8d8d8"

            ColumnLayout{
                anchors.fill: parent
                spacing: 0

                RowLayout{
                    Layout.fillWidth: true
                    Layout.preferredHeight: 64
                    Layout.leftMargin: 20
                    Layout.rightMargin: 16
                    spacing: 8

                    FluTextBox{
                        id: search_text
                        Layout.fillWidth: true
                        placeholderText: qsTr("Search chats...")
                        background: Item{}
                    }

                    FluIconButton{
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        iconSource: FluentIcons.Cancel
                        iconSize: 13
                        text: qsTr("Close")
                        normalColor: "transparent"
                        hoverColor: hoverBg
                        onClicked: search_popup.close()
                    }
                }

                Rectangle{
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: borderColor
                }

                ListView{
                    id: search_results
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.margins: 8
                    clip: true
                    spacing: 6
                    model: filteredSessions(search_text.text)
                    ScrollBar.vertical: FluScrollBar{}

                    header: Column{
                        width: search_results.width
                        spacing: 10

                        Rectangle{
                            width: parent.width
                            height: 44
                            radius: 8
                            color: "#f4f4f4"

                            RowLayout{
                                anchors.fill: parent
                                anchors.leftMargin: 16
                                anchors.rightMargin: 16
                                spacing: 10

                                FluIcon{
                                    iconSource: FluentIcons.Edit
                                    iconSize: 16
                                    iconColor: primaryText
                                }

                                FluText{
                                    text: qsTr("New Chat")
                                    color: primaryText
                                    font: FluTextStyle.Body
                                }
                            }

                            MouseArea{
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    AIBridge.newSession()
                                    search_popup.close()
                                }
                            }
                        }

                        FluText{
                            width: parent.width
                            leftPadding: 16
                            text: qsTr("Today")
                            color: secondaryText
                            font: FluTextStyle.Caption
                        }
                    }

                    delegate: Rectangle{
                        width: search_results.width
                        height: 42
                        radius: 8
                        color: "transparent"

                        RowLayout{
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 16
                            spacing: 10

                            FluIcon{
                                iconSource: FluentIcons.Comment
                                iconSize: 16
                                iconColor: primaryText
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: sessionTitle(modelData, qsTr("Untitled Chat"))
                                color: primaryText
                                elide: Text.ElideRight
                                font: FluTextStyle.Body
                            }
                        }

                        MouseArea{
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onEntered: parent.color = hoverBg
                            onExited: parent.color = "transparent"
                            onClicked: {
                                AIBridge.selectSession(modelData.id)
                                search_popup.close()
                            }
                        }
                    }
                }
            }
        }

        onOpened: {
            search_text.text = ""
            search_text.forceActiveFocus()
        }
    }

    Rectangle{
        anchors.fill: parent
        color: pageBg

        Rectangle{
            id: sidebar
            width: sidebarCollapsed ? 56 : 260
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            color: sidebarBg

            ColumnLayout{
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                RowLayout{
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    spacing: 10

                    Image{
                        Layout.preferredWidth: 22
                        Layout.preferredHeight: 22
                        visible: !sidebarCollapsed
                        source: "qrc:/example/res/svg/deepseek-logo-icon.svg"
                        fillMode: Image.PreserveAspectFit
                    }

                    Item{
                        Layout.fillWidth: true
                        visible: !sidebarCollapsed
                    }

                    FluIconButton{
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        iconSource: FluentIcons.DockLeft
                        iconSize: 15
                        text: qsTr("Collapse Sidebar")
                        normalColor: "transparent"
                        hoverColor: hoverBg
                        onClicked: sidebarCollapsed = !sidebarCollapsed
                    }
                }

                ColumnLayout{
                    Layout.fillWidth: true
                    visible: !sidebarCollapsed
                    spacing: 2

                    SidebarAction{
                        Layout.fillWidth: true
                        iconSource: FluentIcons.Edit
                        text: qsTr("New Chat")
                        onClicked: {
                            selectedProjectId = ""
                            AIBridge.newSession()
                        }
                    }

                    SidebarAction{
                        Layout.fillWidth: true
                        iconSource: FluentIcons.Search
                        text: qsTr("Search Chats")
                        onClicked: search_popup.open()
                    }

                    SidebarAction{
                        Layout.fillWidth: true
                        iconSource: FluentIcons.More
                        text: qsTr("More")
                    }
                }

                ColumnLayout{
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: sidebarCollapsed
                    spacing: 12

                    FluIconButton{
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        Layout.alignment: Qt.AlignHCenter
                        iconSource: FluentIcons.Edit
                        iconSize: 16
                        text: qsTr("New Chat")
                        normalColor: "transparent"
                        hoverColor: hoverBg
                        onClicked: AIBridge.newSession()
                    }

                    FluIconButton{
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        Layout.alignment: Qt.AlignHCenter
                        iconSource: FluentIcons.Search
                        iconSize: 16
                        text: qsTr("Search Chats")
                        normalColor: "transparent"
                        hoverColor: hoverBg
                        onClicked: search_popup.open()
                    }

                    Item{ Layout.fillHeight: true }

                    AvatarView{
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        Layout.alignment: Qt.AlignHCenter
                    }
                }

                FluText{
                    Layout.fillWidth: true
                    Layout.topMargin: 16
                    Layout.leftMargin: 4
                    visible: !sidebarCollapsed
                    text: qsTr("Projects")
                    color: secondaryText
                    font: FluTextStyle.Caption
                }

                Repeater{
                    model: projectRows

                    Rectangle{
                        Layout.fillWidth: true
                        Layout.preferredHeight: 34
                        visible: !sidebarCollapsed
                        radius: 8
                        color: selectedProjectId === modelData.id ? selectedBg : "transparent"

                        RowLayout{
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 4
                            spacing: 8

                            FluIcon{
                                Layout.preferredWidth: 14
                                visible: modelData.id !== "default-new-project"
                                iconSource: expandedProjectId === modelData.id ? FluentIcons.ChevronDown : FluentIcons.ChevronRight
                                iconSize: 10
                                iconColor: primaryText
                            }

                            FluIcon{
                                Layout.preferredWidth: 18
                                iconSource: modelData.id === "default-new-project" ? FluentIcons.NewFolder : FluentIcons.Folder
                                iconSize: 16
                                iconColor: primaryText
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: displayProjectTitle(modelData)
                                color: primaryText
                                elide: Text.ElideRight
                                font: FluTextStyle.Body
                            }

                            FluIconButton{
                                visible: modelData.id !== "default-new-project"
                                Layout.preferredWidth: 26
                                Layout.preferredHeight: 26
                                iconSource: FluentIcons.More
                                iconSize: 12
                                text: qsTr("More")
                                normalColor: "transparent"
                                hoverColor: "#dddddd"
                                onClicked: {
                                    project_menu.projectId = modelData.id
                                    project_menu.titleText = displayProjectTitle(modelData)
                                    project_menu.popup()
                                }
                            }
                        }

                        MouseArea{
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.rightMargin: modelData.id === "default-new-project" ? 0 : 32
                            hoverEnabled: true
                            z: 0
                            onEntered: parent.color = selectedProjectId === modelData.id ? selectedBg : hoverBg
                            onExited: parent.color = selectedProjectId === modelData.id ? selectedBg : "transparent"
                            onClicked: {
                                if(modelData.id === "default-new-project"){
                                    project_dialog.showDialog()
                                }else{
                                    expandedProjectId = expandedProjectId === modelData.id ? "" : modelData.id
                                    selectProject(modelData.id)
                                }
                            }
                        }
                    }
                }

                Repeater{
                    model: projectRows.filter(function(project){ return project.id !== "default-new-project" && expandedProjectId === project.id })

                    ColumnLayout{
                        Layout.fillWidth: true
                        visible: !sidebarCollapsed
                        spacing: 1

                        Repeater{
                            model: projectSessions(modelData.id)

                            SidebarAction{
                                Layout.fillWidth: true
                                Layout.leftMargin: 22
                                iconSource: FluentIcons.Comment
                                text: modelData.title
                                onClicked: selectChat(modelData.id)
                            }
                        }
                    }
                }

                RowLayout{
                    Layout.fillWidth: true
                    Layout.topMargin: 14
                    visible: !sidebarCollapsed
                    spacing: 4

                    FluText{
                        Layout.leftMargin: 4
                        text: qsTr("Recent")
                        color: secondaryText
                        font: FluTextStyle.Caption
                    }

                    FluIcon{
                        iconSource: FluentIcons.ChevronDown
                        iconSize: 10
                        iconColor: secondaryText
                    }
                }

                ListView{
                    id: list_sessions
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: !sidebarCollapsed
                    clip: true
                    spacing: 2
                    model: sessionRows
                    ScrollBar.vertical: FluScrollBar{}

                    delegate: Rectangle{
                        width: list_sessions.width
                        height: 36
                        radius: 8
                        color: modelData.id === selectedSessionId ? selectedBg : "transparent"

                        MouseArea{
                            anchors.fill: parent
                            hoverEnabled: true
                            onEntered: {
                                if(modelData.id !== selectedSessionId){
                                    parent.color = hoverBg
                                }
                            }
                            onExited: {
                                parent.color = modelData.id === selectedSessionId ? selectedBg : "transparent"
                            }
                            onClicked: selectChat(modelData.id)
                        }

                        FluText{
                            anchors.left: parent.left
                            anchors.right: session_more.left
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 9
                            anchors.rightMargin: 6
                            text: sessionTitle(modelData, qsTr("Untitled Chat"))
                            color: primaryText
                            elide: Text.ElideRight
                            font: FluTextStyle.Body
                        }

                        FluIconButton{
                            id: session_more
                            width: 28
                            height: 28
                            anchors.right: parent.right
                            anchors.rightMargin: 4
                            anchors.verticalCenter: parent.verticalCenter
                            iconSource: FluentIcons.More
                            iconSize: 13
                            text: qsTr("More")
                            normalColor: "transparent"
                            hoverColor: "#dddddd"
                            onClicked: {
                                session_menu.sessionId = modelData.id
                                session_menu.titleText = sessionTitle(modelData, qsTr("Untitled Chat"))
                                session_menu.popup()
                            }
                        }
                    }
                }

                RowLayout{
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    visible: !sidebarCollapsed
                    spacing: 9

                    AvatarView{
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                    }

                    ColumnLayout{
                        Layout.fillWidth: true
                        spacing: 0

                        FluText{
                            text: accountName()
                            color: primaryText
                            font: FluTextStyle.Body
                        }

                        Item{ Layout.preferredHeight: 1 }
                    }
                }
            }
        }

        Rectangle{
            id: top_bar
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.top: parent.top
            height: 52
            color: pageBg
            border.width: 0

            Rectangle{
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: borderColor
            }

            RowLayout{
                anchors.fill: parent
                anchors.leftMargin: 32
                anchors.rightMargin: 24
                spacing: 8

                Image{
                    Layout.preferredWidth: 22
                    Layout.preferredHeight: 22
                    visible: selectedProjectId.length === 0
                    source: "qrc:/example/res/svg/deepseek-logo-icon.svg"
                    fillMode: Image.PreserveAspectFit
                }

                FluIcon{
                    visible: selectedProjectId.length > 0
                    Layout.preferredWidth: 22
                    iconSource: FluentIcons.Folder
                    iconSize: 18
                    iconColor: primaryText
                }

                FluText{
                    text: selectedProjectId.length > 0 ? projectTitle(selectedProjectId) : qsTr("DeepSeek Chat")
                    color: primaryText
                    font: FluTextStyle.Subtitle
                }

                FluText{
                    visible: selectedProjectId.length === 0
                    text: qsTr("Preview")
                    color: secondaryText
                    font: FluTextStyle.Body
                }

                FluIcon{
                    visible: selectedProjectId.length === 0
                    iconSource: FluentIcons.ChevronDown
                    iconSize: 12
                    iconColor: secondaryText
                }

                Item{ Layout.fillWidth: true }

                TopAction{
                    iconSource: FluentIcons.Share
                    text: qsTr("Share")
                    onClicked: share_dialog.showDialog(selectedSessionId, currentSessionTitle())
                }

                FluIconButton{
                    Layout.preferredWidth: 34
                    Layout.preferredHeight: 34
                    iconSource: FluentIcons.More
                    iconSize: 14
                    text: qsTr("More")
                    normalColor: "transparent"
                    hoverColor: hoverBg
                    onClicked: {
                        session_menu.sessionId = selectedSessionId
                        session_menu.titleText = currentSessionTitle()
                        session_menu.popup()
                    }
                }
            }
        }

        ListView{
            id: list_messages
            visible: selectedProjectId.length === 0
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.top: top_bar.bottom
            anchors.bottom: composer.top
            anchors.leftMargin: 0
            anchors.rightMargin: 0
            anchors.bottomMargin: 10
            clip: true
            spacing: 24
            model: messageRows
            topMargin: 26
            bottomMargin: 30
            ScrollBar.vertical: FluScrollBar{}

            delegate: Item{
                width: list_messages.width
                height: content_item.implicitHeight

                property bool isUser: modelData.role === "user"

                Item{
                    id: content_item
                    width: Math.min(chatTrackWidth, parent.width - 96)
                    anchors.horizontalCenter: parent.horizontalCenter
                    implicitHeight: isUser ? user_bubble.height : assistant_column.implicitHeight

                    Rectangle{
                        id: user_bubble
                        visible: isUser
                        width: Math.min(520, Math.max(220, Math.min(user_text.implicitWidth + 34, content_item.width * 0.58)))
                        height: user_text.implicitHeight + 22
                        anchors.right: parent.right
                        radius: 18
                        color: "#f0f0f0"

                        Text{
                            id: user_text
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 12
                            text: modelData.content
                            color: primaryText
                            font.family: FluTextStyle.family
                            font.pixelSize: chatFontSize
                            wrapMode: Text.WordWrap
                            textFormat: Text.PlainText
                            lineHeight: chatLineHeight
                            lineHeightMode: Text.ProportionalHeight
                            renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
                        }
                    }

                    Column{
                        id: assistant_column
                        visible: !isUser
                        width: Math.min(assistantContentWidth, parent.width * 0.76)
                        anchors.left: parent.left
                        spacing: 11

                        Text{
                            width: parent.width
                            text: modelData.status === "loading" ? qsTr("Thinking...") : renderMarkdown(modelData.content)
                            textFormat: modelData.status === "loading" ? Text.PlainText : Text.RichText
                            wrapMode: Text.WordWrap
                            color: primaryText
                            linkColor: "#0f62fe"
                            font.family: FluTextStyle.family
                            font.pixelSize: chatFontSize
                            lineHeight: chatLineHeight
                            lineHeightMode: Text.ProportionalHeight
                            renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
                            onLinkActivated: (link)=> Qt.openUrlExternally(link)
                        }

                        Row{
                            spacing: 8

                            FluIconButton{
                                width: 28
                                height: 28
                                iconSource: FluentIcons.Copy
                                iconSize: 13
                                text: qsTr("Copy")
                                normalColor: "transparent"
                                hoverColor: hoverBg
                                onClicked: AIBridge.copyMessage(modelData.id)
                            }

                            FluIconButton{
                                width: 28
                                height: 28
                                iconSource: FluentIcons.Refresh
                                iconSize: 13
                                text: qsTr("Retry")
                                normalColor: "transparent"
                                hoverColor: hoverBg
                                onClicked: AIBridge.retryMessage(modelData.id)
                            }

                            FluIconButton{
                                width: 28
                                height: 28
                                iconSource: FluentIcons.More
                                iconSize: 13
                                text: qsTr("More")
                                normalColor: "transparent"
                                hoverColor: hoverBg
                            }
                        }
                    }
                }
            }
        }

        Item{
            id: project_content
            visible: selectedProjectId.length > 0
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.top: top_bar.bottom
            anchors.bottom: parent.bottom

            ColumnLayout{
                width: Math.min(680, parent.width - 96)
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 70
                spacing: 28

                RowLayout{
                    Layout.fillWidth: true
                    spacing: 12

                    FluIcon{
                        Layout.preferredWidth: 30
                        iconSource: FluentIcons.Folder
                        iconSize: 28
                        iconColor: primaryText
                    }

                    FluText{
                        Layout.fillWidth: true
                        text: projectTitle(selectedProjectId)
                        color: primaryText
                        font.pixelSize: 28
                        font.weight: 600
                        elide: Text.ElideRight
                    }
                }

                Rectangle{
                    Layout.fillWidth: true
                    Layout.preferredHeight: 58
                    radius: 29
                    color: "#ffffff"
                    border.width: 1
                    border.color: "#dddddd"

                    RowLayout{
                        anchors.fill: parent
                        anchors.leftMargin: 18
                        anchors.rightMargin: 16
                        spacing: 12

                        FluIcon{
                            iconSource: FluentIcons.Add
                            iconSize: 18
                            iconColor: primaryText
                        }

                        FluText{
                            Layout.fillWidth: true
                            text: qsTr("New chat in %1").arg(projectTitle(selectedProjectId))
                            color: secondaryText
                            font: FluTextStyle.Body
                            elide: Text.ElideRight
                        }
                    }

                    MouseArea{
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            selectedProjectId = ""
                            AIBridge.newSession()
                        }
                    }
                }

                RowLayout{
                    Layout.fillWidth: true
                    spacing: 12

                    Rectangle{
                        Layout.preferredWidth: 60
                        Layout.preferredHeight: 38
                        radius: 19
                        color: "#f2f2f2"

                        FluText{
                            anchors.centerIn: parent
                            text: qsTr("Chats")
                            color: primaryText
                            font: FluTextStyle.BodyStrong
                        }
                    }

                    FluText{
                        text: qsTr("Sources")
                        color: secondaryText
                        font: FluTextStyle.Body
                    }

                    Item{ Layout.fillWidth: true }
                }

                ColumnLayout{
                    id: project_chat_list
                    Layout.fillWidth: true
                    spacing: 6
                    visible: true

                    FluText{
                        Layout.fillWidth: true
                        text: projectSessions(selectedProjectId).length === 0 ? qsTr("No chats in this project yet.") : qsTr("Chats in this project")
                        color: secondaryText
                        font: FluTextStyle.Caption
                    }

                    Repeater{
                        model: projectSessions(selectedProjectId)

                        Rectangle{
                            Layout.fillWidth: true
                            Layout.preferredHeight: 64
                            radius: 0
                            color: "transparent"

                            RowLayout{
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 12

                                ColumnLayout{
                                    Layout.fillWidth: true
                                    spacing: 2

                                    FluText{
                                        Layout.fillWidth: true
                                        text: sessionTitle(modelData, qsTr("Untitled Chat"))
                                        color: primaryText
                                        elide: Text.ElideRight
                                        font: FluTextStyle.Body
                                    }

                                    FluText{
                                        Layout.fillWidth: true
                                        text: modelData.preview || qsTr("No preview")
                                        color: secondaryText
                                        elide: Text.ElideRight
                                        font: FluTextStyle.Caption
                                    }
                                }

                                FluText{
                                    text: formatSessionDate(modelData.updated_at)
                                    color: secondaryText
                                    font: FluTextStyle.Body
                                }
                            }

                            Rectangle{
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: borderColor
                            }

                            MouseArea{
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onEntered: parent.color = "#f7f7f7"
                                onExited: parent.color = "transparent"
                                onClicked: selectChat(modelData.id)
                            }
                        }
                    }
                }

                Item{ Layout.preferredHeight: 34 }

                ColumnLayout{
                    Layout.fillWidth: true
                    spacing: 6

                    FluText{
                        Layout.alignment: Qt.AlignHCenter
                        text: qsTr("Ask this project")
                        color: primaryText
                        font: FluTextStyle.Subtitle
                    }

                    FluText{
                        Layout.alignment: Qt.AlignHCenter
                        text: qsTr("This project collects chats, shared context, and uploaded files.")
                        color: secondaryText
                        font: FluTextStyle.Caption
                    }
                }
            }
        }

        Column{
            id: composer
            visible: selectedProjectId.length === 0
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 8
            spacing: 4

            Rectangle{
                width: Math.max(360, parent.width - 96)
                height: 106
                anchors.horizontalCenter: parent.horizontalCenter
                radius: 22
                color: "#ffffff"
                border.width: 2
                border.color: accentColor

                FluMultilineTextBox{
                    id: input_prompt
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: composer_tools.top
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    anchors.topMargin: 12
                    anchors.bottomMargin: 2
                    placeholderText: qsTr("Ask anything")
                    disabled: AIBridge.loading
                    isCtrlEnterForNewline: true
                    background: Item{}
                    color: primaryText
                    placeholderNormalColor: "#8a8a8a"
                    placeholderFocusColor: "#8a8a8a"
                    onCommit: sendPrompt()
                }

                RowLayout{
                    id: composer_tools
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
                        hoverColor: hoverBg
                        disabled: AIBridge.loading
                        onClicked: composer_add_menu.popup()
                    }

                    Repeater{
                        model: attachmentRows

                        ToolChip{
                            iconSource: FluentIcons.Attach
                            text: modelData.name
                            removable: true
                            onRemoveClicked: AIBridge.removeAttachment(modelData.id)
                        }
                    }

                    Repeater{
                        model: enabledMcpSources()

                        ToolChip{
                            iconSource: FluentIcons.ConnectApp
                            imageSource: modelData.id === "jira" ? "qrc:/example/res/svg/jira-software-icon.svg" : ""
                            text: modelData.name
                            removable: true
                            onRemoveClicked: AIBridge.setMcpSourceEnabled(modelData.id, false)
                        }
                    }

                    Item{ Layout.fillWidth: true }

                    FluIconButton{
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 30
                        iconSource: FluentIcons.Microphone
                        iconSize: 15
                        text: qsTr("Voice")
                        normalColor: "transparent"
                        hoverColor: hoverBg
                    }

                    Rectangle{
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                        radius: 17
                        color: AIBridge.loading || (input_prompt.text || "").trim().length === 0 ? "#c9c9c9" : "#000000"

                        FluIcon{
                            anchors.centerIn: parent
                            iconSource: FluentIcons.Send
                            iconSize: 15
                            iconColor: "#ffffff"
                        }

                        MouseArea{
                            anchors.fill: parent
                            enabled: !AIBridge.loading && (input_prompt.text || "").trim().length > 0
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: sendPrompt()
                        }
                    }
                }
            }

            FluText{
                anchors.horizontalCenter: parent.horizontalCenter
                text: qsTr("SmartTest AI can make mistakes. Verify important information.")
                color: secondaryText
                font: FluTextStyle.Caption
            }
        }
    }

    component SidebarAction: Rectangle{
        id: sidebar_action
        signal clicked()
        property int iconSource: 0
        property string text: ""
        height: 34
        radius: 8
        color: "transparent"

        RowLayout{
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 10

            FluIcon{
                Layout.preferredWidth: 18
                iconSource: sidebar_action.iconSource
                iconSize: 16
                iconColor: page.primaryText
            }

            FluText{
                Layout.fillWidth: true
                text: sidebar_action.text
                color: page.primaryText
                elide: Text.ElideRight
                font: FluTextStyle.Body
            }
        }

        MouseArea{
            anchors.fill: parent
            hoverEnabled: true
            onEntered: parent.color = page.hoverBg
            onExited: parent.color = "transparent"
            onClicked: parent.clicked()
        }
    }

    component TopAction: Item{
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
                iconColor: page.primaryText
            }

            FluText{
                text: top_action.text
                color: page.primaryText
                font: FluTextStyle.Body
            }
        }

        MouseArea{
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: top_action.clicked()
        }
    }

    component ToolChip: Rectangle{
        id: tool_chip
        signal removeClicked()
        property int iconSource: 0
        property string imageSource: ""
        property string text: ""
        property bool removable: false
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

            FluIcon{
                visible: tool_chip.removable
                iconSource: FluentIcons.Cancel
                iconSize: 10
                iconColor: page.secondaryText
            }
        }

        MouseArea{
            anchors.fill: parent
            enabled: tool_chip.removable
            onClicked: tool_chip.removeClicked()
        }
    }

    component SourceSwitch: Rectangle{
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
            color: checked ? "#ffffff" : "#9a9a9a"
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

    component AvatarView: Rectangle{
        radius: width / 2
        color: "#d8f3ee"
        clip: true

        Image{
            anchors.fill: parent
            visible: (AuthBridge.avatarUrl || "").length > 0
            source: AuthBridge.avatarUrl
            fillMode: Image.PreserveAspectCrop
            cache: false
        }

        FluText{
            anchors.centerIn: parent
            visible: (AuthBridge.avatarUrl || "").length === 0
            text: accountInitials()
            color: "#0f766e"
            font: FluTextStyle.Caption
        }
    }
}
