import QtQml 2.15
import QtCore

Settings {
    category: "page/test"
    property int schemaVersion: 1
    property bool suitePanelExpanded: false
    property real suitePanelHeight: 220

    function updateSuitePanel(expanded, height) {
        suitePanelExpanded = expanded
        suitePanelHeight = height
        setValue("suitePanelExpanded", expanded)
        setValue("suitePanelHeight", height)
        sync()
    }
}
