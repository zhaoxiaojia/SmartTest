import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0
import "../component"

FluPage {
    title: qsTr("Tool")
    launchMode: FluPageType.SingleInstance

    property int selectedGroupIndex: 0
    property int selectedToolIndex: 0
    property var selectedGroup: ToolBridge.groups.length > selectedGroupIndex ? ToolBridge.groups[selectedGroupIndex] : ({})
    property var selectedTool: selectedGroup.tools && selectedGroup.tools.length > selectedToolIndex ? selectedGroup.tools[selectedToolIndex] : ({})

    Connections {
        target: RedmineBridge
        function onCredentialsRequired() { redmine_credentials.open() }
        function onVerificationRequired() { redmine_verification.open() }
        function onChanged() {
            if (RedmineBridge.state !== "credentials_required") redmine_credentials.clearSecret()
            if (RedmineBridge.state !== "verification_required") redmine_verification.clearSecret()
        }
    }

    FluContentDialog {
        id: redmine_credentials
        property string username: ""
        property string password: ""
        function clearSecret() { password = "" }
        title: qsTr("Redmine credentials")
        positiveText: qsTr("Sign in")
        negativeText: qsTr("Cancel")
        contentDelegate: Component {
            ColumnLayout {
                spacing: 8
                FluTextBox { Layout.fillWidth: true; placeholderText: qsTr("Username"); onTextChanged: redmine_credentials.username = text }
                FluPasswordBox { Layout.fillWidth: true; text: redmine_credentials.password; placeholderText: qsTr("Password"); onTextChanged: redmine_credentials.password = text }
            }
        }
        onPositiveClicked: { RedmineBridge.submitCredentials(username, password); clearSecret() }
        onNegativeClicked: { clearSecret(); RedmineBridge.cancelLogin() }
    }

    FluContentDialog {
        id: redmine_verification
        property string code: ""
        function clearSecret() { code = "" }
        title: qsTr("Mobile verification")
        message: qsTr("Enter the verification code shown on your phone.")
        positiveText: qsTr("Verify")
        negativeText: qsTr("Cancel")
        contentDelegate: Component { FluTextBox { text: redmine_verification.code; placeholderText: qsTr("Verification code"); onTextChanged: redmine_verification.code = text } }
        onPositiveClicked: { RedmineBridge.submitVerification(code); clearSecret() }
        onNegativeClicked: { clearSecret(); RedmineBridge.cancelLogin() }
    }

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
            Layout.preferredWidth: 252
            Layout.fillHeight: true
            color: FluTheme.dark ? "#202020" : "#f7f7f7"
            border.color: FluTheme.frameColor
            radius: 8

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                FluText {
                    text: qsTr("Tools")
                    font: FluTextStyle.Title
                }
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
            padding: 28

            ColumnLayout {
                anchors.fill: parent
                spacing: 12

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
                FluText {
                    text: qsTr("Tool workspace")
                    font: FluTextStyle.Subtitle
                }
                FluText {
                    Layout.fillWidth: true
                    text: selectedTool.id === "redmine" ? RedmineBridge.statusText : qsTr("This area is reserved for the selected tool. Execution is not available yet.")
                    color: FluTheme.fontSecondaryColor
                    wrapMode: Text.WordWrap
                }
                RowLayout {
                    visible: selectedTool.id === "redmine"
                    FluButton { objectName: "redmineLoginButton"; text: qsTr("Sign in"); disabled: RedmineBridge.loading; onClicked: RedmineBridge.startLogin() }
                    FluButton { text: qsTr("Cancel"); onClicked: RedmineBridge.cancelLogin() }
                }
                Item {
                    Layout.fillHeight: true
                }
            }
        }
    }
}
