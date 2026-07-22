import QtQuick 2.15
import "../issue"

JiraIssueBrowserLayout {
    id: root
    cloneSelectable: true
    cloneSelectionMode: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneSelectionMode : false
    cloneSelectedIds: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneSelectedIds : []
    statusFilters: [qsTr("All statuses"), "Open", "Closed"]
    typeFilters: [qsTr("All types"), "Bug", "Support"]
    onCloneSelectionRequested: RedmineBridge.beginCloneSelection()
    onCloneSelectionToggled: (issueId, selected) => RedmineBridge.toggleCloneSelection(issueId, selected)
    onCloneSelectionCancelled: RedmineBridge.cancelCloneSelection()
    onCloneSelectionConfirmed: RedmineBridge.prepareCloneDrafts()

    JiraCreateBatchDialog {
        anchors.fill: parent
        cloneDrafts: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneDrafts : []
        batchState: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneBatchState : "idle"
        loaded: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneBatchLoaded : 0
        total: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneBatchTotal : 0
        batchError: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneBatchError : ""
        firstInvalidIssueId: typeof RedmineBridge !== "undefined" ? RedmineBridge.firstInvalidIssueId : ""
        firstInvalidFieldId: typeof RedmineBridge !== "undefined" ? RedmineBridge.firstInvalidFieldId : ""
        onUpdateCloneDraft: (issueId, fieldId, value) => RedmineBridge.updateCloneDraft(issueId, fieldId, value)
        onSubmitCloneBatch: RedmineBridge.submitCloneBatch()
        onRetryFailedClones: RedmineBridge.retryFailedClones()
        onCloseCloneBatch: RedmineBridge.closeCloneBatch()
        onSearchCloneUsers: (issueId, fieldId, query) => RedmineBridge.searchCloneUsers(issueId, fieldId, query)
        onSourceLinkRequested: url => RedmineBridge.openWebUrl(url)
    }
}
