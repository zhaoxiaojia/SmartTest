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
    signal closeCloneBatch()
    signal searchCloneUsers(string issueId, string fieldId, string query)
    signal sourceLinkRequested(string url)

    visible: ["loading", "editing", "validating", "submitting", "completed", "partial_failed"].indexOf(batchState) >= 0
    z: 1000
    onFirstInvalidIssueIdChanged: Qt.callLater(focusFirstInvalidField)
    onFirstInvalidFieldIdChanged: Qt.callLater(focusFirstInvalidField)

    Rectangle { anchors.fill: parent; color: FluTheme.dark ? "#CC111111" : "#99000000" }
    FluFrame {
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 1040)
        height: Math.min(parent.height - 48, 760)
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
                ScrollView {
                    id: draftScroll
                    anchors.fill: parent
                    anchors.margins: 16
                    visible: root.batchState !== "loading"
                    clip: true
                    ColumnLayout {
                        width: draftScroll.availableWidth
                        spacing: 12
                        Repeater {
                            id: draftRepeater
                            model: root.cloneDrafts || []
                            JiraCreateDraftCard {
                                Layout.fillWidth: true
                                draft: modelData
                                disabled: root.batchState === "submitting"
                                onValueChanged: (issueId, fieldId, value) => root.updateCloneDraft(issueId, fieldId, value)
                                onUserSearchRequested: (issueId, fieldId, query) => root.searchCloneUsers(issueId, fieldId, query)
                                onSourceLinkRequested: url => root.sourceLinkRequested(url)
                            }
                        }
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
                FluFilledButton { objectName: "jiraCloneBatchCreateButton"; text: qsTr("Batch Create"); visible: root.batchState === "editing" || root.batchState === "validating"; disabled: root.batchState === "validating"; onClicked: root.submitCloneBatch() }
            }
        }
    }

    function focusFirstInvalidField() {
        if (!root.firstInvalidIssueId || !root.firstInvalidFieldId) return
        for (var i = 0; i < draftRepeater.count; ++i) {
            var card = draftRepeater.itemAt(i)
            if (card && String(card.draft.issueId || "") === root.firstInvalidIssueId) {
                draftScroll.contentItem.contentY = Math.max(0, card.y)
                card.focusField(root.firstInvalidFieldId)
                return
            }
        }
    }
}
