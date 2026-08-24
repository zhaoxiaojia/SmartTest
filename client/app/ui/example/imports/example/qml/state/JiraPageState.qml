import QtQml 2.15
import QtCore

Settings {
    required property string account
    category: "users/" + account + "/jira"
    property int schemaVersion: 1
    property var projects: ["all_supported_projects"]
    property var statuses: []
    property var priorities: []
    property var issueTypes: ["bug"]
    property var assignees: []
    property var reporters: []
    property var labels: []
    property string selectedBoardId: "open_work"
    property string selectedTimeframeId: "last_30_days"
    property string rawJql: ""
    property string keyword: ""
}
