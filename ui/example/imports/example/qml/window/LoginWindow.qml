import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../component"

FluWindow {

    id: window
    title: accountMode ? qsTr("Account") : qsTr("Login")
    width: 400
    height: 320
    fixSize: true
    modality: Qt.ApplicationModal
    property bool accountMode: false

    function refreshMode(argument){
        var initialUsername = ""
        if(argument && argument.username){
            initialUsername = argument.username
        }else{
            initialUsername = AuthBridge.currentUsername()
        }
        accountMode = AuthBridge.authenticated
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
            text: accountMode
                  ? qsTr("Signed in as %1").arg(AuthBridge.currentUsername())
                  : qsTr("LDAP Server: %1").arg(AuthBridge.ldapServer())
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
            text: accountMode ? qsTr("Logout") : qsTr("Login")
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6
            onClicked:{
                if(accountMode){
                    AuthBridge.logout()
                    refreshMode({username: textbox_username.text})
                    showInfo(qsTr("Signed out"))
                    return
                }
                submitLogin()
            }
        }
    }
}
