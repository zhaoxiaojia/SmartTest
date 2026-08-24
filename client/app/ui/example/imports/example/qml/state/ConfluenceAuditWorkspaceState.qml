import QtQml 2.15
import QtCore

Settings {
    required property string account
    category: "users/" + account + "/confluenceAudit"
    property int schemaVersion: 1
    property bool hasAppliedFilters: false
    property var selectedProductLineKeys: []
    property var years: []
    property var supportModes: []
    property var projectStatuses: []
}
