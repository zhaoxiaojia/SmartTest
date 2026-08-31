import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import FluentUI


Button {
    property bool disabled: false
    property string contentDescription: ""
    property color normalColor: FluTheme.dark ? Qt.rgba(38/255,45/255,52/255,1) : Qt.rgba(250/255,253/255,255/255,1)
    property color hoverColor: FluTheme.dark ? Qt.rgba(44/255,58/255,66/255,1) : Qt.rgba(236/255,250/255,255/255,1)
    property color disableColor: FluTheme.dark ? Qt.rgba(59/255,59/255,59/255,1) : Qt.rgba(251/255,251/255,251/255,1)
    property color dividerColor: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.42) : Qt.rgba(0/255,178/255,255/255,0.50)
    property color textColor: {
        if(FluTheme.dark){
            if(!enabled){
                return Qt.rgba(131/255,131/255,131/255,1)
            }
            if(pressed){
                return Qt.rgba(162/255,162/255,162/255,1)
            }
            return Qt.rgba(1,1,1,1)
        }else{
            if(!enabled){
                return Qt.rgba(160/255,160/255,160/255,1)
            }
            if(pressed){
                return Qt.rgba(96/255,96/255,96/255,1)
            }
            return Qt.rgba(0,0,0,1)
        }
    }
    Accessible.role: Accessible.Button
    Accessible.name: control.text
    Accessible.description: contentDescription
    Accessible.onPressAction: control.clicked()
    id: control
    enabled: !disabled
    verticalPadding: 0
    horizontalPadding:12
    font:FluTextStyle.Body
    focusPolicy:Qt.TabFocus
    background: FluControlBackground{
        implicitWidth: 30
        implicitHeight: 32
        radius: 6
        neon: true
        neonActive: control.enabled && (control.hovered || control.activeFocus)
        neonColor: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,1) : Qt.rgba(0/255,178/255,255/255,1)
        neonSecondaryColor: FluTheme.dark ? Qt.rgba(124/255,77/255,255/255,1) : Qt.rgba(55/255,103/255,255/255,1)
        border.width: 1
        border.color: {
            if(!enabled){
                return dividerColor
            }
            if(control.hovered || control.activeFocus){
                return neonColor
            }
            return FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.30) : Qt.rgba(0/255,160/255,255/255,0.42)
        }
        color: {
            if(!enabled){
                return disableColor
            }
            return hovered ? hoverColor :normalColor
        }
        shadow: !pressed && enabled
        FluFocusRectangle{
            visible: control.activeFocus
            radius:6
        }
    }
    contentItem: FluText {
        text: control.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font: control.font
        color: control.textColor
    }
}
