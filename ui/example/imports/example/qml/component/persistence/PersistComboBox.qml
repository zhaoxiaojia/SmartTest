import FluentUI 1.0

FluComboBox {
    id: control
    property bool persistEnabled: true
    readonly property alias persistenceReady: state.persistenceReady
    PersistBinding {
        id: state
        target: control
        valueType: "int"
        defaultValue: control.currentIndex
        persistEnabled: control.persistEnabled
        readValue: function() { return control.currentIndex }
        writeValue: function(value) { control.currentIndex = value }
    }
    onCurrentIndexChanged: state.valueChanged()
}
