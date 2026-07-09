import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import FluentUI

Button {
    property bool disabled: false
    property string contentDescription: ""
    property color normalColor: FluTheme.primaryColor
    property color hoverColor: FluTheme.dark ? Qt.lighter(normalColor,1.08) : Qt.lighter(normalColor,1.16)
    property color disableColor: FluTheme.dark ? Qt.rgba(82/255,82/255,82/255,1) : Qt.rgba(199/255,199/255,199/255,1)
    property color pressedColor: FluTheme.dark ? Qt.darker(normalColor,1.2) : Qt.lighter(normalColor,1.2)
    property color textColor: {
        if(FluTheme.dark){
            if(!enabled){
                return Qt.rgba(173/255,173/255,173/255,1)
            }
            return Qt.rgba(0,0,0,1)
        }else{
            return Qt.rgba(1,1,1,1)
        }
    }
    Accessible.role: Accessible.Button
    Accessible.name: control.text
    Accessible.description: contentDescription
    Accessible.onPressAction: control.clicked()
    id: control
    enabled: !disabled
    focusPolicy:Qt.TabFocus
    font:FluTextStyle.Body
    verticalPadding: 0
    horizontalPadding:12
    background: FluControlBackground{
        implicitWidth: 30
        implicitHeight: 32
        radius: 6
        bottomMargin: enabled ? 2 : 0
        border.width: enabled ? 1 : 0
        border.color: enabled ? (FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.86) : Qt.rgba(0/255,178/255,255/255,0.92)) : disableColor
        neon: true
        neonActive: control.enabled && (control.hovered || control.visualFocus || control.pressed)
        neonColor: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,1) : Qt.rgba(0/255,178/255,255/255,1)
        neonSecondaryColor: FluTheme.dark ? Qt.rgba(92/255,255/255,204/255,1) : Qt.rgba(85/255,92/255,255/255,1)
        color:{
            if(!enabled){
                return disableColor
            }
            if(pressed){
                return pressedColor
            }
            return hovered ? hoverColor :normalColor
        }
        FluFocusRectangle{
            visible: control.visualFocus
            radius:6
        }
    }
    contentItem: FluText {
        text: control.text
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: control.textColor
    }
}
