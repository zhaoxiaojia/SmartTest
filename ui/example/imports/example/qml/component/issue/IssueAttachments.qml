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
    function isLocalFileUrl(value) { var text = value === undefined || value === null ? "" : value.toString(); return /^file:\/{3}[^\s]+$/i.test(text) }
    function localFiles(fileUrls) { return (fileUrls || []).filter(value => isLocalFileUrl(value)) }
    function selectFiles(fileUrls) { var accepted = localFiles(fileUrls); if (!uploading && accepted.length > 0) filesSelected(issueKey, accepted) }
    RowLayout { Layout.fillWidth: true; FluText { text: qsTr("Attachments"); font: FluTextStyle.BodyStrong } Item { Layout.fillWidth: true } FluButton { text: qsTr("Select files"); disabled: root.uploading; onClicked: fileDialog.open() } }
    Rectangle { Layout.fillWidth: true; height: 1; color: FluTheme.dividerColor }
    FileDialog { id: fileDialog; objectName: "issueAttachmentFileDialog"; title: qsTr("Select attachments"); fileMode: FileDialog.OpenFiles; onAccepted: root.selectFiles(selectedFiles) }
    Rectangle {
        objectName: "issueAttachmentDropSurface"
        Layout.fillWidth: true; Layout.preferredHeight: 76; radius: 6
        color: FluTheme.dark ? "#20242A" : "#F7F8FA"; opacity: root.uploading ? 0.55 : 1
        Canvas { anchors.fill: parent; onPaint: { var c=getContext("2d"); c.clearRect(0,0,width,height); c.strokeStyle=FluTheme.dark ? "#7B8490" : "#7A869A"; c.lineWidth=1; c.setLineDash([6,4]); c.strokeRect(1,1,width-2,height-2) } }
        ColumnLayout { anchors.centerIn: parent; FluIcon { Layout.alignment: Qt.AlignHCenter; iconSource: FluentIcons.Upload; iconSize: 20; color: FluTheme.primaryColor } FluText { text: root.uploading ? qsTr("Uploading...") : qsTr("Drop files here or select files"); color: FluTheme.fontSecondaryColor } }
        MouseArea { anchors.fill: parent; enabled: !root.uploading; cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: fileDialog.open() }
    }
    FluText { visible: root.loading; text: qsTr("Loading attachments..."); color: FluTheme.fontSecondaryColor }
    FluText { visible: !!root.error; text: root.error; color: FluTheme.dark ? "#FF8A80" : "#C62828"; wrapMode: Text.WrapAnywhere }
    Flow { Layout.fillWidth: true; spacing: 8; Repeater { model: root.attachments || []; IssueAttachmentCard { objectName: "issueAttachmentCard_" + index; attachment: modelData; onClicked: row => root.attachmentOpenRequested(root.issueKey, row) } } }
}
