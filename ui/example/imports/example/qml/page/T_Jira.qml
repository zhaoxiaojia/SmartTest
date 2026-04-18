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

    function refreshOptionModels(resetDefaults){
        var projectIndex = resetDefaults ? 0 : combo_project.currentIndex
        var boardIndex = resetDefaults ? 0 : combo_board.currentIndex
        var timeframeIndex = resetDefaults ? 1 : combo_timeframe.currentIndex
        combo_project.model = JiraBridge.projectOptions()
        combo_board.model = JiraBridge.boardOptions()
        combo_timeframe.model = JiraBridge.timeframeOptions()
        combo_project.currentIndex = Math.max(0, Math.min(projectIndex, combo_project.model.length - 1))
        combo_board.currentIndex = Math.max(0, Math.min(boardIndex, combo_board.model.length - 1))
        combo_timeframe.currentIndex = Math.max(0, Math.min(timeframeIndex, combo_timeframe.model.length - 1))
    }

    function submitPrompt(){
        var promptText = (input_prompt.text || "").trim()
        if(promptText.length === 0 || JiraBridge.loading){
            return
        }
        JiraBridge.submitPrompt(
            promptText,
            combo_project.currentText,
            combo_board.currentText,
            combo_timeframe.currentText,
            textbox_filter.text,
            toggle_comments.checked,
            toggle_links.checked,
            toggle_only_mine.checked
        )
        input_prompt.text = ""
    }

    Component.onCompleted: {
        refreshOptionModels(true)
        syncBridgeState()
        JiraBridge.bootstrap()
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
                            title: qsTr("Project Filters")
                            Layout.fillWidth: true

                            ColumnLayout{
                                anchors.left: parent.left
                                anchors.right: parent.right
                                spacing: 8

                                FluComboBox{
                                    id: combo_project
                                    Layout.fillWidth: true
                                }

                                FluComboBox{
                                    id: combo_board
                                    Layout.fillWidth: true
                                }

                                FluComboBox{
                                    id: combo_timeframe
                                    Layout.fillWidth: true
                                }

                                FluTextBox{
                                    id: textbox_filter
                                    Layout.fillWidth: true
                                    placeholderText: qsTr("Keyword, label, component...")
                                }

                                FluFilledButton{
                                    Layout.fillWidth: true
                                    text: JiraBridge.loading ? qsTr("Loading...") : qsTr("Refresh Results")
                                    disabled: JiraBridge.loading
                                    onClicked: JiraBridge.refreshScope(
                                                   combo_project.currentText,
                                                   combo_board.currentText,
                                                   combo_timeframe.currentText,
                                                   textbox_filter.text,
                                                   toggle_comments.checked,
                                                   toggle_links.checked,
                                                   toggle_only_mine.checked
                                               )
                                }
                            }
                        }

                        FluGroupBox{
                            title: qsTr("Analysis Options")
                            Layout.fillWidth: true

                            ColumnLayout{
                                anchors.left: parent.left
                                anchors.right: parent.right
                                spacing: 10

                                FluToggleSwitch{
                                    id: toggle_comments
                                    checked: true
                                    text: qsTr("Include comments")
                                }

                                FluToggleSwitch{
                                    id: toggle_links
                                    checked: true
                                    text: qsTr("Include linked issues")
                                }

                                FluToggleSwitch{
                                    id: toggle_only_mine
                                    checked: false
                                    text: qsTr("Limit to my tickets")
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
                                                            anchors.left: parent.left
                                                            anchors.verticalCenter: parent.verticalCenter
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

                                                MouseArea{
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: JiraBridge.selectIssue(index, toggle_comments.checked, toggle_links.checked)
                                                }
                                            }
                                        }

                                        FluButton{
                                            Layout.alignment: Qt.AlignHCenter
                                            visible: JiraBridge.canLoadMore()
                                            text: JiraBridge.loading ? qsTr("Loading...") : qsTr("Load More")
                                            disabled: JiraBridge.loading
                                            onClicked: JiraBridge.loadMore()
                                        }

                                        Item{
                                            Layout.fillWidth: true
                                            implicitHeight: selected_issue_column.implicitHeight + 20

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

                                                FluText{
                                                    text: qsTr("Selected Issue")
                                                    font: FluTextStyle.BodyStrong
                                                }

                                                FluText{
                                                    width: parent.width
                                                    text: selectedIssue.summary ? selectedIssue.summary : qsTr("No issue selected")
                                                    wrapMode: Text.WordWrap
                                                }

                                                FluText{
                                                    width: parent.width
                                                    text: selectedIssue.keyId
                                                          ? qsTr("%1 | Updated %2 | %3 comments | %4 links").arg(selectedIssue.keyId).arg(selectedIssue.updatedAt).arg(selectedIssue.commentCount).arg(selectedIssue.linkCount)
                                                          : ""
                                                    font: FluTextStyle.Caption
                                                    color: FluTheme.fontSecondaryColor
                                                    wrapMode: Text.WordWrap
                                                }

                                                Rectangle{
                                                    width: parent.width
                                                    height: 1
                                                    color: FluTheme.dividerColor
                                                }

                                                FluText{
                                                    width: parent.width
                                                    text: selectedIssue.detail ? selectedIssue.detail : ""
                                                    wrapMode: Text.WordWrap
                                                    color: FluTheme.fontSecondaryColor
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
