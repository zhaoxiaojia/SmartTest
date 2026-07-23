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

    property bool cloneBatchActive: typeof RedmineBridge !== "undefined"
        && ["loading", "prepare_failed", "editing", "validating", "submitting", "completed", "partial_failed"].indexOf(RedmineBridge.cloneBatchState) >= 0

    Loader {
        id: cloneBatchLoader
        anchors.fill: parent
        active: root.cloneBatchActive
        source: active ? "../issue/JiraCreateBatchDialog.qml" : ""
    }

    Binding { target: cloneBatchLoader.item; property: "cloneDrafts"; value: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneDrafts : []; when: cloneBatchLoader.status === Loader.Ready }
    Binding { target: cloneBatchLoader.item; property: "batchState"; value: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneBatchState : "idle"; when: cloneBatchLoader.status === Loader.Ready }
    Binding { target: cloneBatchLoader.item; property: "loaded"; value: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneBatchLoaded : 0; when: cloneBatchLoader.status === Loader.Ready }
    Binding { target: cloneBatchLoader.item; property: "total"; value: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneBatchTotal : 0; when: cloneBatchLoader.status === Loader.Ready }
    Binding { target: cloneBatchLoader.item; property: "batchError"; value: typeof RedmineBridge !== "undefined" ? RedmineBridge.cloneBatchError : ""; when: cloneBatchLoader.status === Loader.Ready }
    Binding { target: cloneBatchLoader.item; property: "firstInvalidIssueId"; value: typeof RedmineBridge !== "undefined" ? RedmineBridge.firstInvalidIssueId : ""; when: cloneBatchLoader.status === Loader.Ready }
    Binding { target: cloneBatchLoader.item; property: "firstInvalidFieldId"; value: typeof RedmineBridge !== "undefined" ? RedmineBridge.firstInvalidFieldId : ""; when: cloneBatchLoader.status === Loader.Ready }

    Connections {
        target: cloneBatchLoader.item
        ignoreUnknownSignals: true
        function onUpdateCloneDraft(issueId, fieldId, value) { RedmineBridge.updateCloneDraft(issueId, fieldId, value) }
        function onSubmitCloneBatch() { RedmineBridge.submitCloneBatch() }
        function onRetryFailedClones() { RedmineBridge.retryFailedClones() }
        function onRetryPrepareCloneDrafts() { RedmineBridge.prepareCloneDrafts() }
        function onCloseCloneBatch() { RedmineBridge.closeCloneBatch() }
        function onSearchCloneUsers(issueId, fieldId, query) { RedmineBridge.searchCloneUsers(issueId, fieldId, query) }
        function onSourceLinkRequested(url) { RedmineBridge.openWebUrl(url) }
    }
}
