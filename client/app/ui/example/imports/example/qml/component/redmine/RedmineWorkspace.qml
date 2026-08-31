import QtQuick 2.15
import "../issue"

JiraIssueBrowserLayout {
    id: root
    cloneSelectable: true
    cloneSelectionMode: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneSelectionMode : false
    cloneSelectedIds: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneSelectedIds : []
    watchedIssueText: typeof RedmineBridge !== "undefined" && typeof RedmineBridge.watchedIssueText !== "undefined" ? RedmineBridge.watchedIssueText : ""
    watchedIssueError: typeof RedmineBridge !== "undefined" && typeof RedmineBridge.watchedIssueError !== "undefined" ? RedmineBridge.watchedIssueError : ""
    onWatchedIssueIdsSaved: text => RedmineBridge.saveWatchedIssueIds(text)
    statusFilters: [qsTr("All statuses"), "Open", "Closed"]
    typeFilters: [qsTr("All types"), "Bug", "Support"]
    onCloneSelectionRequested: RedmineBridge.beginCloneSelection()
    onCloneSelectionToggled: (issueId, selected) => RedmineBridge.toggleCloneSelection(issueId, selected)
    onCloneSelectionCancelled: RedmineBridge.cancelCloneSelection()
    onCloneSelectionConfirmed: RedmineBridge.prepareCloneDrafts()

}
