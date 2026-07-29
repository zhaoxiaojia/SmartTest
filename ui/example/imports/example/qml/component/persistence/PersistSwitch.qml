import FluentUI 1.0

FluToggleSwitch {
    id: control
    property bool persistEnabled: true
    readonly property alias persistenceReady: state.persistenceReady
    PersistBinding {
        id: state
        target: control
        valueType: "bool"
        defaultValue: control.checked
        persistEnabled: control.persistEnabled
        readValue: function() { return control.checked }
        writeValue: function(value) { control.checked = value }
    }
    onCheckedChanged: state.valueChanged()
}
