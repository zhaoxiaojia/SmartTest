pragma Singleton

import QtQuick 2.15
import FluentUI 1.0

FluObject{

    property var navigationView
    property var paneItemMenu
    property var accountLoginHandler

    id:footer_items

    FluPaneItemSeparator{}

    FluPaneItem{
        title:qsTr("Account")
        icon:FluentIcons.Contact
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
