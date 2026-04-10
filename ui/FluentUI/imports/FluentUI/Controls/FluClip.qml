import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import FluentUI

FluRectangle {
    id:control
    color: "#00000000"
    layer.enabled: !FluTools.isSoftware()
    layer.textureSize: Qt.size(control.width*2*Math.ceil(Screen.devicePixelRatio),control.height*2*Math.ceil(Screen.devicePixelRatio))
    layer.effect: MultiEffect {
        maskEnabled: true
        maskSource: ShaderEffectSource {
            sourceItem: FluRectangle {
                radius: control.radius
                width: control.width
                height: control.height
            }
        }
    }
}
