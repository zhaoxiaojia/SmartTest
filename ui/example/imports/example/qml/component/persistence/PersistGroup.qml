import QtQuick 2.15

PersistBinding {
    id: root

    property var entries: []
    valueType: "object"
    defaultValue: snapshot(true)
    readValue: function() { return snapshot(false) }
    writeValue: function(value) { applySnapshot(value) }

    function cloneValue(value) {
        return Array.isArray(value) ? value.slice() : value
    }

    function compatible(value, fallback) {
        if (Array.isArray(fallback)) {
            return value !== null
                    && typeof value === "object"
                    && typeof value.length === "number"
        }
        return typeof value === typeof fallback
    }

    function snapshot(useDefaults) {
        var value = {}
        for (var i = 0; i < entries.length; ++i) {
            var entry = entries[i]
            value[entry.key] = cloneValue(
                        useDefaults
                        ? entry.defaultValue
                        : entry.target[entry.propertyName])
        }
        return value
    }

    function applySnapshot(value) {
        var state = value || {}
        for (var i = 0; i < entries.length; ++i) {
            var entry = entries[i]
            var next = state[entry.key]
            if (!compatible(next, entry.defaultValue)) {
                next = entry.defaultValue
            }
            entry.target[entry.propertyName] = cloneValue(next)
        }
    }
}
