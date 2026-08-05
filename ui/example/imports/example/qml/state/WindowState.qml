import QtQml 2.15
import QtCore

Settings {
    category: "global/window"
    property int schemaVersion: 1
    property bool tourShown: false
    property bool rememberCloseAction: false
    property string closeAction: ""
    property bool fitsAppBarWindows: true
}
