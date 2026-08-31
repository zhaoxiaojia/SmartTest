pragma Singleton

import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

FluObject{

    property var navigationView
    property Component paneItemMenu: null
    property var accountLoginHandler
    property bool compact: false
    readonly property string accountTitle: AuthBridge.authenticated
        ? (AuthBridge.displayName || AuthBridge.username)
        : qsTr("Account")
    readonly property string accountRole: AuthBridge.authenticated ? AuthBridge.roleText : ""
    readonly property string accountInitials: AuthBridge.initials || "A"
    readonly property url accountAvatarUrl: AuthBridge.avatarUrl

    id:footer_items

    FluPaneItemSeparator{}

    FluPaneItem{
        title: footer_items.accountTitle
        itemHeight: 58
        compactItemHeight: 58
        contentDelegate: Item {
            FluClip {
                id: footerAvatar
                width: footer_items.compact ? 32 : 34
                height: width
                radius: [width / 2, width / 2, width / 2, width / 2]
                anchors {
                    left: parent.left
                    leftMargin: footer_items.compact ? 3 : 9
                    top: parent.top
                    topMargin: footer_items.compact ? 3 : 11
                }
                Rectangle {
                    anchors.fill: parent
                    color: FluTheme.dark ? "#334155" : "#DCEBFA"
                    FluText {
                        anchors.centerIn: parent
                        text: footer_items.accountInitials
                        font.pixelSize: 10
                        font.bold: true
                        color: FluTheme.dark ? "#FFFFFF" : "#1E3A5F"
                    }
                }
                Image {
                    anchors.fill: parent
                    source: footer_items.accountAvatarUrl
                    visible: source.toString() !== ""
                    fillMode: Image.PreserveAspectCrop
                    sourceSize: Qt.size(64, 64)
                    cache: false
                }
            }
            Column {
                visible: !footer_items.compact
                anchors {
                    left: footerAvatar.right
                    leftMargin: 10
                    right: parent.right
                    rightMargin: 8
                    verticalCenter: parent.verticalCenter
                }
                spacing: 2
                FluText {
                    width: parent.width
                    text: footer_items.accountTitle
                    elide: Text.ElideRight
                    font: FluTextStyle.BodyStrong
                }
                FluText {
                    width: parent.width
                    text: footer_items.accountRole
                    visible: text !== ""
                    elide: Text.ElideRight
                    font: FluTextStyle.Caption
                    color: FluTheme.fontSecondaryColor
                }
            }
            FluText {
                visible: footer_items.compact
                anchors {
                    top: footerAvatar.bottom
                    topMargin: 2
                    horizontalCenter: parent.horizontalCenter
                }
                width: 42
                horizontalAlignment: Text.AlignHCenter
                text: footer_items.accountTitle
                elide: Text.ElideRight
                font.pixelSize: 7
                color: FluTheme.fontSecondaryColor
            }
        }
        onTapListener:function(){
            if(accountLoginHandler){
                accountLoginHandler()
            }else{
                console.warn("ItemsFooter.Account login handler is not ready")
            }
        }
    }

    FluPaneItem{
        title:qsTr("Settings")
        menuDelegate: paneItemMenu
        icon:FluentIcons.Settings
        url:"qrc:/example/qml/page/T_Settings.qml"
        onTap:{
            navigationView.push(url)
        }
    }

}
