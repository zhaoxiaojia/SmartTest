import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs
import FluentUI 1.0

ColumnLayout {
    id: root
    property string issueKey: ""
    property var attachments: []
    property bool loading: false
    property bool uploading: false
    property string error: ""
    signal filesSelected(string issueKey, var fileUrls)
    signal attachmentOpenRequested(string issueKey, var attachment)
    spacing: 8
    function selectFiles(fileUrls) { if (!uploading && (fileUrls || []).length > 0) filesSelected(issueKey, fileUrls) }
    RowLayout { Layout.fillWidth: true; FluText { text: qsTr("Attachments"); font: FluTextStyle.BodyStrong } Item { Layout.fillWidth: true } FluButton { text: qsTr("Select files"); disabled: root.uploading; onClicked: fileDialog.open() } }
    Rectangle { Layout.fillWidth: true; height: 1; color: FluTheme.dividerColor }
    FileDialog { id: fileDialog; objectName: "issueAttachmentFileDialog"; title: qsTr("Select attachments"); fileMode: FileDialog.OpenFiles; onAccepted: root.selectFiles(selectedFiles) }
    FluText { visible: root.loading; text: qsTr("Loading attachments..."); color: FluTheme.fontSecondaryColor }
    FluText { visible: !!root.error; text: root.error; color: FluTheme.dark ? "#FF8A80" : "#C62828"; wrapMode: Text.WrapAnywhere }
    Flow { Layout.fillWidth: true; spacing: 8; Repeater { model: root.attachments || []; IssueAttachmentCard { objectName: "issueAttachmentCard_" + index; attachment: modelData; onClicked: row => root.attachmentOpenRequested(root.issueKey, row) } } }
}
