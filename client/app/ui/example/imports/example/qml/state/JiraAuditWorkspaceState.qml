import QtQml 2.15
import QtCore

Settings {
    required property string account
    category: "users/" + account + "/jiraAudit"
    property int schemaVersion: 1
    property string auditInput: ""
}
