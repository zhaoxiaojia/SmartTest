pragma Singleton
import QtQml 2.15

QtObject {
    readonly property real scale: 0.70

    function metric(value, minimum) {
        return Math.max(minimum || 0, Math.round(value * scale))
    }

    function controlHeight(value) {
        return metric(value, 28)
    }
}
