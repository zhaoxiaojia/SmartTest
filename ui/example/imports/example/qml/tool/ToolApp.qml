import QtQuick 2.15
import FluentUI 1.0
import "../component/persistence" as Persistence

FluLauncher {
    id: app
    property string stateScope: "global"
    Persistence.PersistBinding {
        target: app
        stateKey: "darkMode"
        valueType: "int"
        defaultValue: 0
        readValue: function() { return FluTheme.darkMode }
        writeValue: function(value) { FluTheme.darkMode = value }
    }
    Component.onCompleted: {
        FluApp.init(app, Qt.locale(TranslateHelper.current))
        FluApp.windowIcon = "qrc:/example/res/image/taskbar_icon.png"
        FluTheme.animationEnabled = true
        FluTheme.nativeText = true
        FluRouter.routes = {
            "/": "qrc:/example/qml/tool/ToolWindow.qml",
            "/login": "qrc:/example/qml/window/LoginWindow.qml",
            "/about": "qrc:/example/qml/window/AboutWindow.qml"
        }
        FluRouter.navigate("/")
    }
}
