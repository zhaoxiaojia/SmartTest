import QtQuick 2.15
import FluentUI 1.0
import "../state"

FluLauncher {
    id: app
    property bool restoringApplicationState: true
    ApplicationState { id: applicationState }
    Connections {
        target: FluTheme
        function onDarkModeChanged() {
            if (!restoringApplicationState) applicationState.darkMode = FluTheme.darkMode
        }
    }
    Component.onCompleted: {
        FluTheme.darkMode = applicationState.darkMode
        restoringApplicationState = false
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
