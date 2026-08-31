import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../component"
import "../component/redmine"

FluPage {
    id: root
    title: qsTr("Tool")
    launchMode: FluPageType.SingleInstance

    property int selectedGroupIndex: 0
    property int selectedToolIndex: 0
    property var selectedGroup: ToolBridge.groups.length > selectedGroupIndex ? ToolBridge.groups[selectedGroupIndex] : ({})
    property var selectedTool: selectedGroup.tools && selectedGroup.tools.length > selectedToolIndex ? selectedGroup.tools[selectedToolIndex] : ({})
    property string autoStartedToolId: ""

    FluContentDialog {
        id: supportedBrowserMissingDialog
        title: qsTr("Supported browser required")
        message: qsTr("Install Google Chrome or Microsoft Edge to use Redmine. Other browsers are not supported yet.")
        positiveText: qsTr("OK")
        buttonFlags: FluContentDialogType.PositiveButton
    }

    Connections {
        target: RedmineBridge
        function onSupportedBrowserMissing() {
            supportedBrowserMissingDialog.open()
        }
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
                    visible: selectedTool.id !== "redmine"
                    text: qsTr("This area is reserved for the selected tool. Execution is not available yet.")
                    color: FluTheme.fontSecondaryColor
                }
            }
        }
    }
    }
}
