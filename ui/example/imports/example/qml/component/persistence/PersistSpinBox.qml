import FluentUI 1.0

FluSpinBox {
    id: control
    property bool persistEnabled: true
    readonly property alias persistenceReady: state.persistenceReady
    PersistBinding {
        id: state
        target: control
        valueType: "int"
        defaultValue: control.value
        persistEnabled: control.persistEnabled
        readValue: function() { return control.value }
        writeValue: function(value) { control.value = value }
    }
    onValueChanged: state.valueChanged()
}
