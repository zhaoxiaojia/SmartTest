import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import QtQuick.Layouts
import FluentUI

Button {
    property string contentDescription: ""
    property bool disabled: false
    property color borderNormalColor: checked ? FluTheme.primaryColor : FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.46) : Qt.rgba(0/255,178/255,255/255,0.50)
    property color borderDisableColor:  FluTheme.dark ? Qt.rgba(82/255,82/255,82/255,1) : Qt.rgba(198/255,198/255,198/255,1)
    property color normalColor: FluTheme.dark ? Qt.rgba(38/255,45/255,52/255,1) : Qt.rgba(250/255,253/255,255/255,1)
    property color hoverColor: checked ? normalColor : FluTheme.dark ? Qt.rgba(44/255,58/255,66/255,1) : Qt.rgba(236/255,250/255,255/255,1)
    property color disableColor: checked ? FluTheme.dark ? Qt.rgba(159/255,159/255,159/255,1) : Qt.rgba(159/255,159/255,159/255,1)  : FluTheme.dark ? Qt.rgba(43/255,43/255,43/255,1) : Qt.rgba(222/255,222/255,222/255,1)
    property alias textColor: btn_text.textColor
    property real size: 18
    property bool textRight: true
    property real textSpacing: 6
    property var clickListener : function(){
        checked = !checked
    }
    Accessible.role: Accessible.Button
    Accessible.name: control.text
    Accessible.description: contentDescription
    Accessible.onPressAction: control.clicked()
    id:control
    enabled: !disabled
    horizontalPadding:2
    verticalPadding: 2
    background: Item{
        FluFocusRectangle{
            visible: control.activeFocus
        }
    }
    focusPolicy:Qt.TabFocus
    font:FluTextStyle.Body
    onClicked: clickListener()
    contentItem: RowLayout{
        spacing: control.textSpacing
        layoutDirection:control.textRight ? Qt.LeftToRight : Qt.RightToLeft
        Rectangle{
            id:rect_check
            width: control.size
            height: control.size
            radius: size/2
            border.width: {
                if(checked&&!enabled){
                    return 3
                }
                if(pressed){
                    if(checked){
                        return 4
                    }
                    return 1
                }
                if(hovered){
                    if(checked){
                        return 3
                    }
                    return 1
                }
                return checked ? 4 : 1
            }
            Behavior on border.width {
                enabled: FluTheme.animationEnabled
                NumberAnimation{
                    duration: 167
                    easing.type: Easing.OutCubic
                }
            }
            border.color: {
                if(!enabled){
                    return borderDisableColor
                }
                return  borderNormalColor
            }
            color:{
                if(!enabled){
                    return disableColor
                }
                if(hovered){
                    return hoverColor
                }
                return normalColor
            }
            Rectangle{
                anchors.fill: parent
                anchors.margins: -5
                radius: parent.radius + 5
                color: "#00000000"
                border.width: (checked || hovered || control.activeFocus) && enabled ? 1 : 0
                border.color: checked ? (FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.55) : Qt.rgba(0/255,178/255,255/255,0.50)) : (FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.28) : Qt.rgba(0/255,178/255,255/255,0.24))
                opacity: (checked || hovered || control.activeFocus) && enabled ? 1 : 0
                Behavior on opacity {
                    enabled: FluTheme.animationEnabled
                    NumberAnimation{ duration: 167; easing.type: Easing.OutCubic }
                }
            }
        }
        FluText{
            id:btn_text
            text: control.text
            Layout.alignment: Qt.AlignVCenter
            font: control.font
            visible: text !== ""
        }
    }
}
