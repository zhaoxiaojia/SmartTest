import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

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

    function groupById(groupId) {
        for (var index = 0; index < ToolBridge.groups.length; ++index) {
            if (ToolBridge.groups[index].id === groupId)
                return ToolBridge.groups[index]
        }
        return ({"id": groupId, "available": false, "tools": []})
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

    Component {
        id: tool_group_content

        Item {
            id: tool_group_root
            property var toolGroup: ({"available": false, "tools": []})
            visible: toolGroup.available
            implicitHeight: visible ? tool_items.implicitHeight + 12 : 0

            ColumnLayout {
                id: tool_items
                x: 6
                y: 6
                width: parent.width - 12
                spacing: 4

                Repeater {
                    model: toolGroup.available ? toolGroup.tools : []

                    FluButton {
                        Layout.fillWidth: true
                        text: modelData.title
                        onClicked: selectTool(toolGroup.id, index)
                    }
                }
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
                FluExpander {
                    id: common_tools_expander
                    property var toolGroup: groupById("common")
                    Layout.fillWidth: true
                    headerText: qsTr("Common Tools")
                    contentHeight: common_tools_loader.item ? common_tools_loader.item.implicitHeight : 0
                    Loader {
                        id: common_tools_loader
                        anchors.fill: parent
                        property var toolGroup: common_tools_expander.toolGroup
                        sourceComponent: tool_group_content
                    }
                    Binding {
                        target: common_tools_loader.item
                        property: "toolGroup"
                        value: common_tools_expander.toolGroup
                        when: common_tools_loader.item !== null
                    }
                }

                FluText {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    text: qsTr("Custom Tools")
                    font: FluTextStyle.Caption
                    color: FluTheme.fontSecondaryColor
                }

                FluExpander {
                    id: stb_tools_expander
                    property var toolGroup: groupById("STB")
                    Layout.fillWidth: true
                    headerText: qsTr("STB")
                    contentHeight: stb_tools_loader.item ? stb_tools_loader.item.implicitHeight : 0
                    Loader {
                        id: stb_tools_loader
                        anchors.fill: parent
                        property var toolGroup: stb_tools_expander.toolGroup
                        sourceComponent: tool_group_content
                    }
                    Binding {
                        target: stb_tools_loader.item
                        property: "toolGroup"
                        value: stb_tools_expander.toolGroup
                        when: stb_tools_loader.item !== null
                    }
                }
                FluExpander {
                    id: tv_tools_expander
                    property var toolGroup: groupById("TV")
                    Layout.fillWidth: true
                    headerText: qsTr("TV")
                    contentHeight: tv_tools_loader.item ? tv_tools_loader.item.implicitHeight : 0
                    Loader {
                        id: tv_tools_loader
                        anchors.fill: parent
                        property var toolGroup: tv_tools_expander.toolGroup
                        sourceComponent: tool_group_content
                    }
                    Binding {
                        target: tv_tools_loader.item
                        property: "toolGroup"
                        value: tv_tools_expander.toolGroup
                        when: tv_tools_loader.item !== null
                    }
                }
                FluExpander {
                    id: smart_home_tools_expander
                    property var toolGroup: groupById("SmartHome")
                    Layout.fillWidth: true
                    headerText: qsTr("SmartHome")
                    contentHeight: smart_home_tools_loader.item ? smart_home_tools_loader.item.implicitHeight : 0
                    Loader {
                        id: smart_home_tools_loader
                        anchors.fill: parent
                        property var toolGroup: smart_home_tools_expander.toolGroup
                        sourceComponent: tool_group_content
                    }
                    Binding {
                        target: smart_home_tools_loader.item
                        property: "toolGroup"
                        value: smart_home_tools_expander.toolGroup
                        when: smart_home_tools_loader.item !== null
                    }
                }
                FluExpander {
                    id: iptv_tools_expander
                    property var toolGroup: groupById("IPTV")
                    Layout.fillWidth: true
                    headerText: qsTr("IPTV")
                    contentHeight: iptv_tools_loader.item ? iptv_tools_loader.item.implicitHeight : 0
                    Loader {
                        id: iptv_tools_loader
                        anchors.fill: parent
                        property var toolGroup: iptv_tools_expander.toolGroup
                        sourceComponent: tool_group_content
                    }
                    Binding {
                        target: iptv_tools_loader.item
                        property: "toolGroup"
                        value: iptv_tools_expander.toolGroup
                        when: iptv_tools_loader.item !== null
                    }
                }
                FluExpander {
                    id: wifi_tools_expander
                    property var toolGroup: groupById("Wi-Fi")
                    Layout.fillWidth: true
                    headerText: qsTr("Wi-Fi")
                    contentHeight: wifi_tools_loader.item ? wifi_tools_loader.item.implicitHeight : 0
                    Loader {
                        id: wifi_tools_loader
                        anchors.fill: parent
                        property var toolGroup: wifi_tools_expander.toolGroup
                        sourceComponent: tool_group_content
                    }
                    Binding {
                        target: wifi_tools_loader.item
                        property: "toolGroup"
                        value: wifi_tools_expander.toolGroup
                        when: wifi_tools_loader.item !== null
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
                    FluButton { text: qsTr("Sign in"); disabled: RedmineBridge.loading; onClicked: RedmineBridge.startLogin() }
                    FluButton { text: qsTr("Cancel"); onClicked: RedmineBridge.cancelLogin() }
                }
                Item {
                    Layout.fillHeight: true
                }
            }
        }
    }
}
