import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Window
import FluentUI

Page {
    property int launchMode: FluPageType.SingleTop
    property bool animationEnabled: FluTheme.animationEnabled
    property bool showTitleHeader: true
    property string url : ""
    id: control
    StackView.onRemoved: destroy()
    padding: 5
    visible: false
    opacity: visible
    transform: Translate {
        y: control.visible ? 0 : 80
        Behavior on y{
            enabled: control.animationEnabled && FluTheme.animationEnabled
            NumberAnimation{
                duration: 167
                easing.type: Easing.OutCubic
            }
        }
    }
    Behavior on opacity {
        enabled: control.animationEnabled && FluTheme.animationEnabled
        NumberAnimation{
            duration: 83
        }
    }
    background: Item{}
    header: FluLoader{
        visible: control.showTitleHeader
        height: visible ? implicitHeight : 0
        sourceComponent: control.showTitleHeader && control.title !== "" ? com_header : undefined
    }
    Component{
        id: com_header
        Item{
            implicitHeight: 40
            FluText{
                id:text_title
                text: control.title
                font: FluTextStyle.Title
                anchors{
                    left: parent.left
                    leftMargin: 5
                }
            }
        }
    }
    Component.onCompleted: {
        control.visible = true
    }
}
