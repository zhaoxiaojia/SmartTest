import QtQml 2.15
import QtCore

Settings {
    category: "global/window"
    property int schemaVersion: 2
    property bool tourShown: false
    property bool rememberCloseAction: false
    property string closeAction: ""
    property bool fitsAppBarWindows: true
    property int windowX: -100000
    property int windowY: -100000
    property int windowWidth: 0
    property int windowHeight: 0
    property bool windowMaximized: false
    property bool navigationExpanded: true
}
