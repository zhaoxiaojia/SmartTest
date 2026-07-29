import QtQuick 2.15

Item {
    id: root
    visible: false

    property var target
    property string stateKey: ""
    property string valueType
    property var defaultValue
    property var readValue
    property var writeValue
    property bool persistEnabled: true
    property bool sensitive: false
    property int debounceMs: 0
    readonly property bool persistenceReady: ready

    property bool ready: false
    property bool restoring: false
    property bool registered: false
    property var fallbackValue

    function scope() {
        var item = target
        while (item) {
            if (item.stateScope !== undefined && item.stateScope !== "") {
                return item.stateScope
            }
            item = item.parent
        }
        return ""
    }

    function key() {
        return stateKey || (target && target.objectName
                            ? String(target.objectName) : "")
    }

    function release(flush) {
        if (flush && saveTimer.running) {
            saveTimer.stop()
            commit()
        } else {
            saveTimer.stop()
        }
        if (registered) {
            FrontendStateBridge.release(scope(), key())
        }
        registered = false
        ready = false
    }

    function restore() {
        release(false)
        if (!persistEnabled) {
            ready = true
            return
        }
        var stateScope = scope()
        var stateKey = key()
        if (!stateScope) {
            throw new Error(
                        "PersistBinding requires a non-empty stateScope")
        }
        if (!stateKey) {
            throw new Error(
                        "PersistBinding requires stateKey or objectName")
        }
        restoring = true
        writeValue(FrontendStateBridge.restore(
                       stateScope, stateKey, valueType, fallbackValue))
        restoring = false
        registered = true
        ready = true
    }

    function commit() {
        if (ready && registered && !restoring) {
            FrontendStateBridge.save(
                        scope(), key(), valueType, readValue(), sensitive)
        }
    }

    function valueChanged() {
        if (!ready || !registered || restoring) {
            return
        }
        if (debounceMs) {
            saveTimer.restart()
        } else {
            commit()
        }
    }

    Timer {
        id: saveTimer
        interval: root.debounceMs
        onTriggered: root.commit()
    }
    Connections {
        target: FrontendStateBridge
        function onStateContextChanged() { root.restore() }
    }
    Component.onCompleted: {
        fallbackValue = defaultValue
        restore()
    }
    Component.onDestruction: release(true)
}
