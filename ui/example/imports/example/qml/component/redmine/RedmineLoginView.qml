import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

FluFrame {
    id: root
    property string state: "idle"
    property string statusText: ""
    signal startLoginRequested()
    signal credentialsSubmitRequested(string username, string password)
    signal verificationSubmitRequested(string code)
    signal cancelRequested()
    padding: 28

    onStateChanged: {
        if (state !== "credentials_required") passwordInput.text = ""
        if (state !== "verification_required") verificationInput.text = ""
    }

    function clearSecrets() {
        passwordInput.text = ""
        verificationInput.text = ""
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 56, 520)
        spacing: 14

        FluText { text: qsTr("Redmine sign in"); font: FluTextStyle.Title }
        FluText {
            Layout.fillWidth: true
            text: root.statusText
            color: root.state === "failed" ? FluTheme.errorColor : FluTheme.fontSecondaryColor
            wrapMode: Text.WordWrap
        }

        RowLayout {
            visible: root.state === "signing_in"
            spacing: 12
            FluProgressRing { Layout.preferredWidth: 28; Layout.preferredHeight: 28 }
            FluText { text: qsTr("Signing in with the SmartTest LDAP account...") }
        }

        ColumnLayout {
            visible: root.state === "credentials_required"
            Layout.fillWidth: true
            spacing: 10
            FluText { text: qsTr("Use a separate Redmine account") ; font: FluTextStyle.Subtitle }
            FluTextBox { id: usernameInput; Layout.fillWidth: true; placeholderText: qsTr("Username") }
            FluPasswordBox { id: passwordInput; Layout.fillWidth: true; placeholderText: qsTr("Password") }
            RowLayout {
                FluFilledButton { text: qsTr("Sign in"); onClicked: root.credentialsSubmitRequested(usernameInput.text, passwordInput.text) }
                FluButton { text: qsTr("Cancel"); onClicked: root.cancelRequested() }
            }
        }

        ColumnLayout {
            visible: root.state === "verification_required"
            Layout.fillWidth: true
            spacing: 10
            FluText { text: qsTr("Mobile verification"); font: FluTextStyle.Subtitle }
            FluText { Layout.fillWidth: true; text: qsTr("Enter the verification code shown on your phone."); wrapMode: Text.WordWrap }
            FluTextBox { id: verificationInput; Layout.fillWidth: true; placeholderText: qsTr("Verification code") }
            RowLayout {
                FluFilledButton { text: qsTr("Verify"); onClicked: root.verificationSubmitRequested(verificationInput.text) }
                FluButton { text: qsTr("Cancel"); onClicked: root.cancelRequested() }
            }
        }

        RowLayout {
            visible: root.state === "failed"
            FluFilledButton { objectName: "redmineLoginButton"; text: qsTr("Retry"); onClicked: root.startLoginRequested() }
            FluButton { text: qsTr("Cancel"); onClicked: root.cancelRequested() }
        }
    }
}
