import QtQuick 2.15
import FluentUI 1.0

FluTextBox {
    id: control
    property bool persistEnabled: true
    property bool persistSensitive: false
    readonly property alias persistenceReady: state.persistenceReady
    PersistBinding {
        id: state
        target: control
        valueType: "string"
        defaultValue: control.text
        persistEnabled: control.persistEnabled
        sensitive: control.persistSensitive || control.echoMode === TextInput.Password
        debounceMs: 300
        readValue: function() { return control.text }
        writeValue: function(value) { control.text = value }
    }
    onTextChanged: state.valueChanged()
}
