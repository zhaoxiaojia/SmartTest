import QtQuick
import QtQuick.Controls
import FluentUI

FluControlBackground{
    property Item inputItem
    id:control
    radius: 6
    neon: true
    neonActive: inputItem && (inputItem.activeFocus || inputItem.hovered)
    neonColor: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,1) : Qt.rgba(0/255,178/255,255/255,1)
    neonSecondaryColor: FluTheme.dark ? Qt.rgba(124/255,77/255,255/255,1) : Qt.rgba(75/255,111/255,255/255,1)
    color: {
        if(inputItem && inputItem.disabled){
            return FluTheme.dark ? Qt.rgba(59/255,59/255,59/255,1) : Qt.rgba(252/255,252/255,252/255,1)
        }
        if(inputItem && inputItem.activeFocus){
            return FluTheme.dark ? Qt.rgba(36/255,36/255,36/255,1) : Qt.rgba(1,1,1,1)
        }
        if(inputItem && inputItem.hovered){
            return FluTheme.dark ? Qt.rgba(68/255,68/255,68/255,1) : Qt.rgba(251/255,251/255,251/255,1)
        }
        return FluTheme.dark ? Qt.rgba(62/255,62/255,62/255,1) : Qt.rgba(1,1,1,1)
    }
    border.width: 1
    border.color: {
        if(inputItem && inputItem.activeFocus){
            return control.neonColor
        }
        if(inputItem && inputItem.hovered){
            return FluTools.withOpacity(control.neonColor, FluTheme.dark ? 0.60 : 0.55)
        }
        return FluTheme.dark ? Qt.rgba(66/255,66/255,66/255,1) : Qt.rgba(210/255,230/255,240/255,1)
    }
    gradient: Gradient {
        GradientStop { position: 0.0; color: d.startColor }
        GradientStop { position: 1 - d.offsetSize/control.height; color: d.startColor }
        GradientStop { position: 1.0; color: d.endColor }
    }
    bottomMargin: 1
    QtObject{
        id:d
        property int offsetSize :  3
        property color startColor : {
            if(inputItem && inputItem.activeFocus){
                return FluTools.withOpacity(control.neonColor, FluTheme.dark ? 0.78 : 0.66)
            }
            return FluTheme.dark ? Qt.rgba(66/255,66/255,66/255,1) : Qt.rgba(210/255,230/255,240/255,1)
        }
        property color endColor: {
            if(!control.enabled){
                return d.startColor
            }
            if(inputItem && inputItem.activeFocus){
                return control.neonColor
            }
            return  FluTheme.dark ? Qt.rgba(123/255,123/255,123/255,1) : Qt.rgba(132/255,132/255,132/255,1)
        }
    }
    FluClip{
        anchors.fill: parent
        radius: [control.radius,control.radius,control.radius,control.radius]
        visible: inputItem && inputItem.activeFocus
        Rectangle{
            width: parent.width
            height: 3
            anchors.bottom: parent.bottom
            color: FluTheme.primaryColor
            Rectangle{
                anchors.fill: parent
                anchors.margins: -2
                color: FluTools.withOpacity(control.neonColor, FluTheme.dark ? 0.35 : 0.30)
                radius: 3
            }
        }
    }
}
