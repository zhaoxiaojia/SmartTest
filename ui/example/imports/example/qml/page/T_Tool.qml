import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0
import "../component"
import "../component/redmine"

FluPage {
    title: qsTr("Tool")
    launchMode: FluPageType.SingleInstance

    property int selectedGroupIndex: 0
    property int selectedToolIndex: 0
    property var selectedGroup: ToolBridge.groups.length > selectedGroupIndex ? ToolBridge.groups[selectedGroupIndex] : ({})
    property var selectedTool: selectedGroup.tools && selectedGroup.tools.length > selectedToolIndex ? selectedGroup.tools[selectedToolIndex] : ({})

    function selectTool(groupId, toolIndex) {
        for (var index = 0; index < ToolBridge.groups.length; ++index) {
            if (ToolBridge.groups[index].id === groupId) {
                selectedGroupIndex = index
                selectedToolIndex = toolIndex
                return
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 20
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
                    id: redmineLogin
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: selectedTool.id === "redmine" && RedmineBridge.state !== "authenticated"
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
                    sourceComponent: RedmineWorkspace {}
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
