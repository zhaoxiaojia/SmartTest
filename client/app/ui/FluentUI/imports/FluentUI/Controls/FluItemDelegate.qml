import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Templates as T
import FluentUI

T.ItemDelegate {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)
    padding: 0
    verticalPadding: 8
    horizontalPadding: 10
    icon.color: control.palette.text
    contentItem:FluText {
        text: control.text
        font: control.font
        color:{
            if(control.down){
                return FluTheme.dark ? FluColors.Grey80 : FluColors.Grey120
            }
            return FluTheme.dark ? FluColors.White : FluColors.Grey220
        }
    }
    background: Rectangle {
        implicitWidth: 100
        implicitHeight: 30
        radius: 6
        color:{
            if(FluTheme.dark){
                return Qt.rgba(0/255,229/255,255/255,0.10)
            }else{
                return Qt.rgba(0/255,178/255,255/255,0.10)
            }
        }
        border.width: control.highlighted || control.visualFocus ? 1 : 0
        border.color: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.72) : Qt.rgba(0/255,178/255,255/255,0.72)
        Rectangle{
            anchors.fill: parent
            anchors.margins: -4
            radius: parent.radius + 4
            color: "#00000000"
            border.width: control.highlighted || control.visualFocus ? 1 : 0
            border.color: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.30) : Qt.rgba(0/255,178/255,255/255,0.24)
            opacity: control.highlighted || control.visualFocus ? 1 : 0
        }
        visible: control.down || control.highlighted || control.visualFocus
    }
}
