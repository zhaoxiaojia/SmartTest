import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0
import "component/persistence" as Persistence

FluLauncher {
    id: app
    property string stateScope: "global"

    Persistence.PersistBinding {
        id: darkModeState
        target: app
        stateKey: "darkMode"
        valueType: "int"
        defaultValue: 0
        readValue: function() { return FluTheme.darkMode }
        writeValue: function(value) { FluTheme.darkMode = value }
    }
    Persistence.PersistBinding {
        id: systemAppBarState
        target: app
        stateKey: "useSystemAppBar"
        valueType: "bool"
        defaultValue: false
        readValue: function() { return FluApp.useSystemAppBar }
        writeValue: function(value) { FluApp.useSystemAppBar = value }
    }

    Connections{
        target: FluTheme
        function onDarkModeChanged(){
            darkModeState.valueChanged()
        }
    }
    Connections{
        target: FluApp
        function onUseSystemAppBarChanged(){
            systemAppBarState.valueChanged()
        }
    }
    Component.onCompleted: {
        FluApp.init(app,Qt.locale(TranslateHelper.current))
        // Window/taskbar icon (keep separate from the small navigation logo).
        FluApp.windowIcon = "qrc:/example/res/image/taskbar_icon.png"
        FluTheme.animationEnabled = true
        // Reduce text "ghosting" at non-integer split sizes on Windows by using
        // native text rendering for all FluentUI text controls.
        FluTheme.nativeText = true
        FluRouter.routes = {
            "/":"qrc:/example/qml/window/MainWindow.qml",
            "/about":"qrc:/example/qml/window/AboutWindow.qml",
            "/login":"qrc:/example/qml/window/LoginWindow.qml",
            "/hotload":"qrc:/example/qml/window/HotloadWindow.qml",
            "/crash":"qrc:/example/qml/window/CrashWindow.qml",
            "/singleTaskWindow":"qrc:/example/qml/window/SingleTaskWindow.qml",
            "/standardWindow":"qrc:/example/qml/window/StandardWindow.qml",
            "/singleInstanceWindow":"qrc:/example/qml/window/SingleInstanceWindow.qml",
            "/pageWindow":"qrc:/example/qml/window/PageWindow.qml",
            "/hotkey":"qrc:/example/qml/window/HotkeyWindow.qml"
        }
        var args = Qt.application.arguments
        if(args.length>=2 && args[1].startsWith("-crashed=")){
            FluRouter.navigate("/crash",{crashFilePath:args[1].replace("-crashed=","")})
        }else{
            FluRouter.navigate("/")
        }
    }
    property alias hotkeys: object_hotkey
    FluObject{
        id: object_hotkey
        FluHotkey{
            name: qsTr("Quit")
            sequence: "Ctrl+Alt+Q"
            onActivated: {
                FluRouter.exit()
            }
        }
        FluHotkey{
            name: qsTr("Test1")
            sequence: "Alt+A"
            onActivated: {
                FluRouter.navigate("/hotkey",{sequence:sequence})
            }
        }
        FluHotkey{
            name: qsTr("Test2")
            sequence: "Alt+B"
            onActivated: {
                FluRouter.navigate("/hotkey",{sequence:sequence})
            }
        }
        FluHotkey{
            name: qsTr("Test3")
            sequence: "Alt+C"
            onActivated: {
                FluRouter.navigate("/hotkey",{sequence:sequence})
            }
        }
        FluHotkey{
            name: qsTr("Test4")
            sequence: "Alt+D"
            onActivated: {
                FluRouter.navigate("/hotkey",{sequence:sequence})
            }
        }
        FluHotkey{
            name: qsTr("Test5")
            sequence: "Alt+E"
            onActivated: {
                FluRouter.navigate("/hotkey",{sequence:sequence})
            }
        }
        FluHotkey{
            name: qsTr("Test6")
            sequence: "Alt+F"
            onActivated: {
                FluRouter.navigate("/hotkey",{sequence:sequence})
            }
        }
        FluHotkey{
            name: qsTr("Test7")
            sequence: "Alt+G"
            onActivated: {
                FluRouter.navigate("/hotkey",{sequence:sequence})
            }
        }
        FluHotkey{
            name: qsTr("Test8")
            sequence: "Alt+H"
            onActivated: {
                FluRouter.navigate("/hotkey",{sequence:sequence})
            }
        }
    }
}
