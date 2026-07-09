import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import QtQuick.Layouts
import FluentUI

Button {
    property bool disabled: false
    property string contentDescription: ""
    property color borderNormalColor: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.46) : Qt.rgba(0/255,178/255,255/255,0.50)
    property color bordercheckedColor: FluTheme.primaryColor
    property color borderHoverColor: FluTheme.dark ? Qt.rgba(167/255,167/255,167/255,1) : Qt.rgba(135/255,135/255,135/255,1)
    property color borderDisableColor: FluTheme.dark ? Qt.rgba(82/255,82/255,82/255,1) : Qt.rgba(199/255,199/255,199/255,1)
    property color borderPressedColor: FluTheme.dark ? Qt.rgba(90/255,90/255,90/255,1) : Qt.rgba(191/255,191/255,191/255,1)
    property color normalColor: FluTheme.dark ? Qt.rgba(38/255,45/255,52/255,1) : Qt.rgba(250/255,253/255,255/255,1)
    property color checkedColor: FluTheme.primaryColor
    property color hoverColor: FluTheme.dark ? Qt.rgba(44/255,58/255,66/255,1) : Qt.rgba(236/255,250/255,255/255,1)
    property color checkedHoverColor: FluTheme.dark ? Qt.darker(checkedColor,1.15) : Qt.lighter(checkedColor,1.15)
    property color checkedPreesedColor: FluTheme.dark ? Qt.darker(checkedColor,1.3) : Qt.lighter(checkedColor,1.3)
    property color checkedDisableColor: FluTheme.dark ? Qt.rgba(82/255,82/255,82/255,1) : Qt.rgba(199/255,199/255,199/255,1)
    property color disableColor: FluTheme.dark ? Qt.rgba(50/255,50/255,50/255,1) : Qt.rgba(253/255,253/255,253/255,1)
    property real size: 18
    property alias textColor: btn_text.textColor
    property bool textRight: true
    property real textSpacing: 6
    property bool animationEnabled: FluTheme.animationEnabled
    property var clickListener : function(){
        checked = !checked
    }
    property bool indeterminate : false
    id:control
    enabled: !disabled
    onClicked: clickListener()
    onCheckableChanged: {
        if(checkable){
            checkable = false
        }
    }
    background: Item{
        FluFocusRectangle{
            radius: 4
            visible: control.activeFocus
        }
    }
    focusPolicy:Qt.TabFocus
    font:FluTextStyle.Body
    horizontalPadding:0
    verticalPadding: 0
    padding: 0
    Accessible.role: Accessible.Button
    Accessible.name: control.text
    Accessible.description: contentDescription
    Accessible.onPressAction: control.clicked()
    contentItem: RowLayout{
        spacing: control.textSpacing
        layoutDirection:control.textRight ? Qt.LeftToRight : Qt.RightToLeft
        Rectangle{
            width: control.size
            height: control.size
            radius: 4
            border.color: {
                if(!enabled){
                    return borderDisableColor
                }
                if(checked){
                    return bordercheckedColor
                }
                if(pressed){
                    return borderPressedColor
                }
                if(hovered){
                    return borderHoverColor
                }
                return borderNormalColor
            }
            border.width: 1
            color: {
                if(checked){
                    if(!enabled){
                        return checkedDisableColor
                    }
                    if(pressed){
                        return checkedPreesedColor
                    }
                    if(hovered){
                        return checkedHoverColor
                    }
                    return checkedColor
                }
                if(!enabled){
                    return disableColor
                }
                if(hovered){
                    return hoverColor
                }
                return normalColor
            }
            Behavior on color {
                enabled: control.animationEnabled
                ColorAnimation{
                    duration: 83
                }
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
                    enabled: control.animationEnabled
                    NumberAnimation{ duration: 167; easing.type: Easing.OutCubic }
                }
            }

            FluIcon {
                anchors.centerIn: parent
                iconSource: FluentIcons.CheckboxIndeterminate
                iconSize: 14
                visible: indeterminate
                iconColor: FluTheme.dark ? Qt.rgba(0,0,0,1) : Qt.rgba(1,1,1,1)
                Behavior on visible {
                    enabled: control.animationEnabled
                    NumberAnimation{
                        duration: 83
                    }
                }
            }

            FluIcon {
                anchors.centerIn: parent
                iconSource: FluentIcons.AcceptMedium
                iconSize: 14
                visible: checked && !indeterminate
                iconColor: FluTheme.dark ? Qt.rgba(0,0,0,1) : Qt.rgba(1,1,1,1)
                Behavior on visible {
                    enabled: control.animationEnabled
                    NumberAnimation{
                        duration: 83
                    }
                }
            }
        }
        FluText{
            id:btn_text
            text: control.text
            Layout.alignment: Qt.AlignVCenter
            visible: text !== ""
            font: control.font
        }
    }
}
