import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0

Item {
    id: root
    property var cloneDrafts: []
    property string batchState: "idle"
    property int loaded: 0
    property int total: 0
    property string batchError: ""
    property string firstInvalidIssueId: ""
    property string firstInvalidFieldId: ""
    signal updateCloneDraft(string issueId, string fieldId, var value)
    signal submitCloneBatch()
    signal retryFailedClones()
    signal retryPrepareCloneDrafts()
    signal closeCloneBatch()
    signal searchCloneUsers(string issueId, string fieldId, string query)
    signal sourceLinkRequested(string url)

    visible: ["loading", "prepare_failed", "editing", "validating", "submitting", "completed", "partial_failed"].indexOf(batchState) >= 0
    z: 1000
    onFirstInvalidIssueIdChanged: Qt.callLater(focusFirstInvalidField)
    onFirstInvalidFieldIdChanged: Qt.callLater(focusFirstInvalidField)

    Rectangle { anchors.fill: parent; color: FluTheme.dark ? "#CC111111" : "#99000000" }
    FluFrame {
        anchors.centerIn: parent
        width: Math.max(0, parent.width - 32)
        height: Math.max(0, parent.height - 32)
        padding: 0
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            RowLayout {
                Layout.fillWidth: true; Layout.margins: 16
                FluText { text: qsTr("Clone Redmine issues to Jira"); font: FluTextStyle.Title }
                Item { Layout.fillWidth: true }
                FluButton { text: qsTr("Close"); disabled: root.batchState === "submitting"; onClicked: root.closeCloneBatch() }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: FluTheme.frameColor }
            Item {
                Layout.fillWidth: true; Layout.fillHeight: true
                ColumnLayout {
                    anchors.centerIn: parent
                    visible: root.batchState === "loading"
                    FluProgressRing { Layout.alignment: Qt.AlignHCenter }
                    FluText { text: qsTr("Preparing drafts %1/%2").arg(root.loaded).arg(root.total) }
                }
                ColumnLayout {
                    anchors.centerIn: parent
                    visible: root.batchState === "prepare_failed"
                    FluText { text: root.batchError; color: "#D13438"; wrapMode: Text.Wrap; Layout.maximumWidth: 640 }
                }
                ScrollView {
                    id: draftScroll
                    anchors.fill: parent
                    anchors.margins: 16
                    visible: root.batchState !== "loading" && root.batchState !== "prepare_failed"
                    clip: true
                    RowLayout {
                        width: Math.max(draftScroll.availableWidth, root.draftContentWidth())
                        spacing: 12
                        Repeater {
                            id: draftRepeater
                            model: root.cloneDrafts || []
                            JiraCreateDraftCard {
                                Layout.fillWidth: true
                                Layout.preferredWidth: root.draftCardWidth()
                                Layout.alignment: Qt.AlignTop
                                draft: modelData
                                disabled: root.batchState === "submitting"
                                onValueChanged: (issueId, fieldId, value) => root.updateCloneDraft(issueId, fieldId, value)
                                onUserSearchRequested: (issueId, fieldId, query) => root.searchCloneUsers(issueId, fieldId, query)
                                onSourceLinkRequested: url => root.sourceLinkRequested(url)
                            }
                        }
                    }
                    Connections {
                        target: draftScroll.contentItem
                        function onContentXChanged() { draftScroll.forceActiveFocus() }
                        function onContentYChanged() { draftScroll.forceActiveFocus() }
                    }
                }
            }
            FluText { Layout.fillWidth: true; Layout.leftMargin: 16; Layout.rightMargin: 16; visible: !!root.batchError; text: root.batchError; color: "#D13438"; wrapMode: Text.Wrap }
            Rectangle { Layout.fillWidth: true; height: 1; color: FluTheme.frameColor }
            RowLayout {
                Layout.fillWidth: true; Layout.margins: 16
                FluText { text: qsTr("%1 drafts").arg((root.cloneDrafts || []).length); color: FluTheme.fontSecondaryColor }
                Item { Layout.fillWidth: true }
                FluButton { text: qsTr("Cancel"); visible: root.batchState !== "completed"; disabled: root.batchState === "submitting"; onClicked: root.closeCloneBatch() }
                FluButton { objectName: "jiraCloneRetryButton"; text: qsTr("Retry failed"); visible: root.batchState === "partial_failed"; onClicked: root.retryFailedClones() }
                FluButton { objectName: "jiraCloneRetryPrepareButton"; text: qsTr("Retry preparation"); visible: root.batchState === "prepare_failed"; onClicked: root.retryPrepareCloneDrafts() }
                FluFilledButton { objectName: "jiraCloneBatchCreateButton"; text: qsTr("Batch Create"); visible: root.batchState === "editing" || root.batchState === "validating"; disabled: root.batchState === "validating"; onClicked: root.submitCloneBatch() }
            }
        }
    }

    function focusFirstInvalidField() {
        if (!root.firstInvalidIssueId || !root.firstInvalidFieldId) return
        for (var i = 0; i < draftRepeater.count; ++i) {
            var card = draftRepeater.itemAt(i)
            if (card && String(card.draft.issueId || "") === root.firstInvalidIssueId) {
                draftScroll.contentItem.contentX = Math.max(0, card.x)
                card.focusField(root.firstInvalidFieldId)
                return
            }
        }
    }
    function draftCardWidth() {
        var count = (root.cloneDrafts || []).length
        if (count <= 1) return draftScroll.availableWidth
        if (count === 2) return Math.max(240, (draftScroll.availableWidth - 12) / 2)
        return 520
    }
    function draftContentWidth() {
        var count = (root.cloneDrafts || []).length
        return count > 0 ? count * root.draftCardWidth() + Math.max(0, count - 1) * 12 : 0
    }
}
