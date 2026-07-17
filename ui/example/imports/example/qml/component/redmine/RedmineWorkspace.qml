import QtQuick 2.15
import "../issue"

JiraIssueBrowserLayout {
    id: root
    statusFilters: [qsTr("All statuses"), "Open", "Closed"]
    typeFilters: [qsTr("All types"), "Bug", "Support"]
}
