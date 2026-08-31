import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import FluentUI

ProgressBar{
    property int duration: 888
    property real strokeWidth: 6
    property bool progressVisible: false
    property color color: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,1) : Qt.rgba(0/255,178/255,255/255,1)
    property color backgroundColor : FluTheme.dark ? Qt.rgba(23/255,34/255,40/255,1) : Qt.rgba(230/255,247/255,255/255,1)
    id:control
    indeterminate : true
    QtObject{
        id:d
        property real _radius: strokeWidth/2
    }
    onIndeterminateChanged:{
        if(!indeterminate){
            animator_x.duration = 0
            rect_progress.x = 0
            animator_x.duration = control.duration
        }
    }
    background: Rectangle {
        implicitWidth: 150
        implicitHeight: control.strokeWidth
        color: control.backgroundColor
        radius: d._radius
        border.width: 1
        border.color: FluTheme.dark ? Qt.rgba(0/255,229/255,255/255,0.28) : Qt.rgba(0/255,178/255,255/255,0.35)
    }
    contentItem: FluClip {
        clip: true
        radius: [d._radius,d._radius,d._radius,d._radius]
        Rectangle {
            id:rect_progress
            width: {
                if(control.indeterminate){
                    return 0.5 * parent.width
                }
                return control.visualPosition * parent.width
            }
            height: parent.height
            radius: d._radius
            color: control.color
            Rectangle{
                anchors.fill: parent
                anchors.margins: -3
                radius: parent.radius + 3
                color: FluTools.withOpacity(control.color, FluTheme.dark ? 0.22 : 0.18)
            }
            Rectangle{
                width: Math.max(16, parent.width * 0.22)
                height: parent.height
                radius: parent.radius
                color: FluTheme.dark ? Qt.rgba(1,1,1,0.48) : Qt.rgba(1,1,1,0.70)
                x: control.indeterminate ? parent.width * 0.58 : Math.max(0, parent.width - width)
            }
            PropertyAnimation on x {
                id:animator_x
                running: control.indeterminate && control.visible
                from: -rect_progress.width
                to:control.width+rect_progress.width
                loops: Animation.Infinite
                duration: control.duration
            }
        }
    }
    FluText{
        text:(control.visualPosition * 100).toFixed(0) + "%"
        visible: {
            if(control.indeterminate){
                return false
            }
            return control.progressVisible
        }
        anchors{
            left: parent.left
            leftMargin: control.width+5
            verticalCenter: parent.verticalCenter
        }
    }
}
