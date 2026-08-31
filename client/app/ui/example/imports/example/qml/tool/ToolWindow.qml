import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0
import "../global"

FluWindow {
    id: window
    title: "SmartTest Tool"
    width: 1100
    height: 720
    minimumWidth: 760
    minimumHeight: 480
    launchMode: FluWindowType.SingleTask

    FluWindowResultLauncher {
        id: loginLauncher
        objectName: "toolLoginLauncher"
        path: "/login"
    }

    appBar: FluAppBar {
        width: window.width
        showDark: true
        darkClickListener: function() {
            FluTheme.darkMode = FluTheme.dark ? FluThemeType.Light : FluThemeType.Dark
        }
    }

    FluIconButton {
        objectName: "toolAboutButton"
        z: 8
        width: 40
        height: 36
        anchors.right: parent.right
        anchors.rightMargin: window.appBar.layoutStandardbuttons.width
        iconSource: FluentIcons.Important
        text: qsTr("About")
        onClicked: FluRouter.navigate("/about")
    }

    FluNavigationView {
        id: navigation
        anchors.fill: parent
        pageMode: FluNavigationViewType.Stack
        displayMode: GlobalModel.displayMode
        logo: "qrc:/example/res/image/app_icon.png"
        title: "SmartTest Tool"
        onCollapseRequested: function(collapsed) {
            GlobalModel.displayMode = collapsed
                    ? FluNavigationViewType.Compact
                    : FluNavigationViewType.Open
        }
        items: FluObject {
            FluPaneItem {
                objectName: "toolMainPaneItem"
                title: qsTr("Tool")
                icon: FluentIcons.Repair
                url: "qrc:/example/qml/page/T_Tool.qml"
                onTap: navigation.push(url)
            }
        }
        footerItems: FluObject {
            FluPaneItem {
                objectName: "toolAccountPaneItem"
                title: AuthBridge.displayName || qsTr("Account")
                icon: FluentIcons.Contact
                onTap: loginLauncher.launch({username: AuthBridge.username})
            }
            FluPaneItem {
                objectName: "toolSettingsPaneItem"
                title: qsTr("Settings")
                icon: FluentIcons.Settings
                url: "qrc:/example/qml/page/T_Settings.qml"
                onTap: navigation.push(url)
            }
        }
        Component.onCompleted: {
            navigation.setCurrentIndex(0)
            if (!AuthBridge.authenticated)
                loginLauncher.launch({username: AuthBridge.username})
        }
    }
}
