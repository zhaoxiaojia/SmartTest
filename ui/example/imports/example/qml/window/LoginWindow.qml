import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import QtQuick.Dialogs
import FluentUI 1.0
import "../component"

FluWindow {

    id: window
    title: accountMode ? qsTr("Account") : qsTr("Login")
    width: 400
    height: 320
    fixSize: false
    modality: Qt.ApplicationModal
    property bool accountMode: false
    property url pendingCropSource: ""
    property url selectedAvatarSource: ""

    function queueAvatarCrop(source){
        pendingCropSource = source
        cropOpenTimer.restart()
    }

    Timer {
        id: cropOpenTimer
        interval: 50
        repeat: false
        onTriggered: {
            if(avatarFileDialog.visible){
                restart()
                return
            }
            var source = pendingCropSource
            pendingCropSource = ""
            if(source.toString() !== ""){
                window.requestActivate()
                cropDialog.openForSource(source)
            }
        }
    }

    function applyModeSize(nextAccountMode){
        var targetWidth = nextAccountMode ? 460 : 400
        var targetHeight = nextAccountMode ? 560 : 320
        window.fixSize = false
        window.minimumWidth = 0
        window.minimumHeight = 0
        window.maximumWidth = 16777215
        window.maximumHeight = 16777215
        accountMode = nextAccountMode
        window.width = targetWidth
        window.height = targetHeight
        window.fixSize = true
        window.fixWindowSize()
        if(window.visible && window.autoCenter){
            window.moveWindowToDesktopCenter()
        }
    }

    FileDialog {
        id: avatarFileDialog
        objectName: "avatarFileDialog"
        title: qsTr("Upload Avatar")
        nameFilters: [qsTr("Image files (*.png *.jpg *.jpeg)")]
        onSelectedFileChanged: {
            if(selectedFile.toString() !== ""){
                selectedAvatarSource = selectedFile
            }
        }
        onAccepted: {
            queueAvatarCrop(selectedAvatarSource.toString())
            selectedAvatarSource = ""
        }
        onRejected: selectedAvatarSource = ""
    }

    AvatarCropDialog {
        id: cropDialog
        onCropAccepted: function(source, horizontalPosition, verticalPosition, cropScale){
            var result = AuthBridge.saveCroppedAvatar(
                source.toString(), horizontalPosition, verticalPosition, cropScale
            )
            if(!result.success){
                showError(qsTr("Avatar upload failed"))
            }
        }
    }

    function refreshMode(argument){
        var initialUsername = ""
        if(argument && argument.username){
            initialUsername = argument.username
        }else{
            initialUsername = AuthBridge.currentUsername()
        }
        applyModeSize(AuthBridge.authenticated)
        textbox_username.updateText(initialUsername)
        textbox_password.text = ""
        Qt.callLater(function(){
            if(accountMode){
                btn_primary.forceActiveFocus()
            }else{
                textbox_username.forceActiveFocus()
            }
        })
    }

    function submitLogin(){
        if(textbox_username.text === ""){
            showError(qsTr("Please enter the account"))
            textbox_username.forceActiveFocus()
            return
        }
        if(textbox_password.text === ""){
            showError(qsTr("Please enter your password"))
            textbox_password.forceActiveFocus()
            return
        }
        var result = AuthBridge.login(textbox_username.text, textbox_password.text)
        if(!result.success){
            showError(result.message)
            textbox_password.forceActiveFocus()
            return
        }
        setResult(result)
        window.close()
    }
    onInitArgument:
        (argument)=>{
            refreshMode(argument)
        }

    ColumnLayout{
        anchors{
            left: parent.left
            right: parent.right
            verticalCenter: parent.verticalCenter
        }
        spacing: 10

        FluText{
            visible: !accountMode
            text: qsTr("LDAP Server: %1").arg(AuthBridge.ldapServer())
            Layout.alignment: Qt.AlignHCenter
            font: FluTextStyle.Caption
            color: FluTheme.fontSecondaryColor
        }

        FluAutoSuggestBox{
            id: textbox_username
            visible: !accountMode
            items: AuthBridge.currentUsername() !== "" ? [{title: AuthBridge.currentUsername()}] : []
            placeholderText: qsTr("Please enter the account")
            Layout.preferredWidth: 260
            Layout.alignment: Qt.AlignHCenter
            onCommit: {
                textbox_password.forceActiveFocus()
            }
        }

        FluTextBox{
            id: textbox_password
            visible: !accountMode
            Layout.preferredWidth: 260
            placeholderText: qsTr("Please enter your password")
            echoMode:TextInput.Password
            Layout.alignment: Qt.AlignHCenter
            onCommit: {
                submitLogin()
            }
        }

        FluFilledButton{
            id: btn_primary
            visible: !accountMode
            text: qsTr("Login")
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6
            onClicked:{
                submitLogin()
            }
        }

        Rectangle {
            visible: accountMode
            Layout.preferredWidth: 420
            Layout.preferredHeight: 520
            Layout.alignment: Qt.AlignHCenter
            radius: 12
            color: FluTheme.dark ? "#202226" : "#F5F6F8"
            border.width: 1
            border.color: FluTheme.dark ? "#3B3F46" : "#E3E8EF"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 10

                RowLayout {
                    id: accountHeader
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    FluText { text: qsTr("Account"); font: FluTextStyle.BodyStrong }
                    Item { Layout.fillWidth: true }
                    FluIconButton {
                        id: accountCloseButton
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 30
                        iconSource: FluentIcons.ChromeClose
                        iconSize: 12
                        onClicked: window.close()
                    }
                }
                FluDivider { Layout.fillWidth: true }

                RowLayout {
                    id: accountIdentityRow
                    Layout.fillWidth: true
                    Layout.preferredHeight: 76
                    Layout.topMargin: 18
                    spacing: 16
                    FluClip {
                        id: accountAvatar
                        Layout.preferredWidth: 66
                        Layout.preferredHeight: 66
                        radius: [33, 33, 33, 33]
                        Rectangle {
                            anchors.fill: parent
                            color: FluTheme.dark ? "#334155" : "#DCEBFA"
                            FluText {
                                anchors.centerIn: parent
                                text: AuthBridge.initials
                                font.pixelSize: 22
                                font.bold: true
                                color: FluTheme.dark ? "#FFFFFF" : "#1E3A5F"
                            }
                        }
                        Image {
                            anchors.fill: parent
                            source: AuthBridge.avatarUrl
                            visible: source.toString() !== ""
                            fillMode: Image.PreserveAspectCrop
                            sourceSize: Qt.size(132, 132)
                            cache: false
                        }
                        MouseArea {
                            id: avatarMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: avatarFileDialog.open()
                        }
                        FluTooltip { text: qsTr("Upload Avatar"); visible: avatarMouse.containsMouse }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        FluText {
                            Layout.fillWidth: true
                            text: AuthBridge.displayName || AuthBridge.username
                            font: FluTextStyle.Title
                            elide: Text.ElideRight
                        }
                        FluText {
                            Layout.fillWidth: true
                            text: AuthBridge.jobTitle
                            color: FluTheme.fontSecondaryColor
                            font: FluTextStyle.Caption
                            elide: Text.ElideRight
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 9
                    Rectangle {
                        id: gradeCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: 66
                        radius: 9
                        color: FluTheme.dark ? "#292C31" : "#FFFFFF"
                        border.width: 1
                        border.color: FluTheme.dark ? "#41464E" : "#E2E5EA"
                        Column { anchors.fill: parent; anchors.margins: 11; spacing: 5
                            FluText { text: qsTr("Grade"); color: FluTheme.fontSecondaryColor; font.pixelSize: 10 }
                            FluText { width: parent.width; text: AuthBridge.grade; font: FluTextStyle.BodyStrong; elide: Text.ElideRight }
                        }
                    }
                    Rectangle {
                        id: departmentCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: 66
                        radius: 9
                        color: FluTheme.dark ? "#292C31" : "#FFFFFF"
                        border.width: 1
                        border.color: FluTheme.dark ? "#41464E" : "#E2E5EA"
                        Column { anchors.fill: parent; anchors.margins: 11; spacing: 5
                            FluText { text: qsTr("Department"); color: FluTheme.fontSecondaryColor; font.pixelSize: 10 }
                            FluText { width: parent.width; text: AuthBridge.department; font: FluTextStyle.BodyStrong; elide: Text.ElideRight }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 24
                    spacing: 14
                    FluText { visible: AuthBridge.team !== ""; text: qsTr("Team") + ":"; color: FluTheme.fontSecondaryColor; font.pixelSize: 10 }
                    FluText { visible: AuthBridge.team !== ""; text: AuthBridge.team; elide: Text.ElideRight }
                    Item { Layout.fillWidth: true }
                }
                RowLayout {
                    visible: AuthBridge.reportsTo !== ""
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? 22 : 0
                    spacing: 8
                    FluText { text: qsTr("Reports To") + ":"; color: FluTheme.fontSecondaryColor; font.pixelSize: 10 }
                    FluText { Layout.fillWidth: true; text: AuthBridge.reportsTo; elide: Text.ElideRight }
                }

                Rectangle {
                    id: productLineCard
                    Layout.fillWidth: true
                    Layout.preferredHeight: 78
                    radius: 9
                    color: FluTheme.dark ? "#292C31" : "#FFFFFF"
                    border.width: 1
                    border.color: FluTheme.dark ? "#41464E" : "#E2E5EA"
                    Column {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6
                        FluText { text: qsTr("Product Line"); color: FluTheme.fontSecondaryColor; font.pixelSize: 10 }
                        Flow {
                            id: productLineTags
                            width: parent.width
                            spacing: 6
                            Repeater {
                                model: AuthBridge.productLines
                                delegate: Rectangle {
                                    required property string modelData
                                    width: productTagText.implicitWidth + 16
                                    height: 24
                                    radius: 6
                                    color: FluTheme.dark ? "#233650" : "#EDF4FF"
                                    FluText {
                                        id: productTagText
                                        anchors.centerIn: parent
                                        text: modelData
                                        color: FluTheme.dark ? "#A9C9F5" : "#235EA8"
                                        font.pixelSize: 10
                                    }
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }
                FluButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    text: qsTr("Logout")
                    textColor: FluColors.Red.normal
                    onClicked: {
                        AuthBridge.logout()
                        refreshMode({username: textbox_username.text})
                        showInfo(qsTr("Signed out"))
                    }
                }
            }
        }
    }
}
