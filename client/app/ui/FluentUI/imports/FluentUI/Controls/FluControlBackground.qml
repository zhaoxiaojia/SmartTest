import QtQuick
import QtQuick.Controls
import FluentUI

Item{
    id:control
    property int radius: 6
    property bool shadow: true
    property bool neon: false
    property bool neonActive: false
    property color neonColor: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,1) : Qt.rgba(0/255,178/255,255/255,1)
    property color neonSecondaryColor: FluTheme.dark ? Qt.rgba(124/255,77/255,255/255,1) : Qt.rgba(75/255,111/255,255/255,1)
    property alias border: d.border
    property var bottomMargin: undefined
    property var topMargin: undefined
    property var leftMargin: undefined
    property var rightMargin: undefined
    property color color: FluTheme.dark ? Qt.rgba(42/255,42/255,42/255,1) : Qt.rgba(254/255,254/255,254/255,1)
    property alias gradient : rect_border.gradient
    Rectangle{
        id:d
        property color startColor: Qt.lighter(d.border.color,1.25)
        property color endColor: shadow ? control.border.color : startColor
        visible: false
        border.color: FluTheme.dark ? Qt.rgba(48/255,48/255,48/255,1) : Qt.rgba(188/255,188/255,188/255,1)
    }
    Rectangle{
        anchors.fill: parent
        anchors.margins: -7
        radius: control.radius + 7
        color: "#00000000"
        border.width: control.neon && control.neonActive ? 1 : 0
        border.color: FluTools.withOpacity(control.neonSecondaryColor, FluTheme.dark ? 0.30 : 0.22)
        opacity: control.neon && control.neonActive ? 1 : 0
        Behavior on opacity {
            enabled: FluTheme.animationEnabled
            NumberAnimation{
                easing.type: Easing.OutCubic
                duration: 167
            }
        }
    }
    Rectangle{
        anchors.fill: parent
        anchors.margins: -3
        radius: control.radius + 3
        color: "#00000000"
        border.width: control.neon && control.neonActive ? 2 : 0
        border.color: FluTools.withOpacity(control.neonColor, FluTheme.dark ? 0.50 : 0.42)
        opacity: control.neon && control.neonActive ? 1 : 0
        Behavior on opacity {
            enabled: FluTheme.animationEnabled
            NumberAnimation{
                easing.type: Easing.OutCubic
                duration: 167
            }
        }
    }
    Rectangle{
        id:rect_border
        anchors.fill: parent
        radius: control.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: d.startColor }
            GradientStop { position: 1 - 3/control.height; color: d.startColor }
            GradientStop { position: 1.0; color: d.endColor}
        }
    }
    Rectangle{
        id:rect_back
        anchors{
            fill: parent
            margins: control.border.width
            topMargin: control.topMargin
            bottomMargin: control.bottomMargin
            leftMargin: control.leftMargin
            rightMargin: control.rightMargin
        }
        Behavior on anchors.bottomMargin {
            NumberAnimation{
                easing.type: Easing.OutCubic
                duration: 167
            }
        }
        radius: control.radius
        color: control.color
        Behavior on color {
            enabled: FluTheme.animationEnabled
            ColorAnimation{
                duration: 167
            }
        }
    }
}
