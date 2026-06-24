import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import QtWebEngine 1.10
import FluentUI 1.0

FluPage {
    title: qsTr("Report")
    launchMode: FluPageType.SingleInstance

    property var reportRowsModel: []
    property string selectedRunId: ""
    property url selectedReportUrl: ""
    property bool loading: reportView.loading
    property string statusText: ""

    function reportIndex(runId){
        if(runId === undefined || runId === ""){
            return -1
        }
        for(var i = 0; i < reportRowsModel.length; i++){
            if(reportRowsModel[i].run_id === runId){
                return i
            }
        }
        return -1
    }

    function refreshReports(preferredRunId){
        ReportBridge.refresh()
        reportRowsModel = ReportBridge.reportRows()
        if(reportRowsModel.length === 0){
            selectedRunId = ""
            selectedReportUrl = ""
            statusText = qsTr("Run a test to generate the first report.")
            return
        }
        var preferredIndex = reportIndex(preferredRunId)
        selectReport(preferredIndex >= 0 ? preferredIndex : Math.max(0, reportIndex(selectedRunId)))
    }

    function selectReport(index){
        if(index < 0 || index >= reportRowsModel.length){
            return
        }
        selectedRunId = reportRowsModel[index].run_id
        selectedReportUrl = ReportBridge.reportHtmlUrl(selectedRunId)
        reportList.currentIndex = index
        statusText = qsTr("Loading...")
    }

    function statusColor(status){
        var colors = {"passed": "#0F7B0F", "failed": "#C42B1C", "running": FluTheme.primaryColor, "stopped": "#8A6A00"}
        return colors[status] || FluTheme.fontSecondaryColor
    }

    function rowBackgroundColor(status, selected){
        if(selected){
            return FluTools.withOpacity(FluTheme.primaryColor, FluTheme.dark ? 0.18 : 0.10)
        }
        var colors = {"failed": Qt.rgba(196/255, 43/255, 28/255, 0.08), "passed": Qt.rgba(15/255, 123/255, 15/255, 0.06)}
        return colors[status] || "transparent"
    }

    Connections{
        target: ReportBridge
        function onReportsChanged(){
            reportRowsModel = ReportBridge.reportRows()
        }
        function onErrorOccurred(msg){
            showError(msg)
        }
    }

    Connections{
        target: RunBridge
        function onRunningChanged(){
            if(!RunBridge.isRunning){
                refreshReports()
            }
        }
        function onRunFinished(result){
            refreshReports((result || {}).run_id || "")
        }
    }

    WebEngineProfile {
        id: reportProfile
        storageName: "smarttest_report_web"
        offTheRecord: false
        httpCacheType: WebEngineProfile.DiskHttpCache
    }

    Component.onCompleted: refreshReports()

    FluSplitLayout{
        anchors.fill: parent
        orientation: Qt.Horizontal

        FluFrame{
            SplitView.preferredWidth: 330
            SplitView.minimumWidth: 280
            SplitView.fillHeight: true
            padding: 10

            ColumnLayout{
                anchors.fill: parent
                spacing: 8

                RowLayout{
                    Layout.fillWidth: true
                    spacing: 8

                    FluText{ text: qsTr("Runs"); font: FluTextStyle.Subtitle; Layout.fillWidth: true }

                    FluIconButton{
                        width: 34; height: 34; iconSource: FluentIcons.Refresh; iconSize: 16
                        text: qsTr("Refresh")
                        onClicked: refreshReports()
                    }

                    FluIconButton{
                        width: 34; height: 34; iconSource: FluentIcons.OpenFolderHorizontal; iconSize: 16
                        text: qsTr("Open report folder")
                        enabled: selectedRunId !== ""
                        onClicked: ReportBridge.openReportFolder(selectedRunId)
                    }
                }

                ListView{
                    id: reportList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: reportRowsModel
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: FluScrollBar{}

                    delegate: Rectangle{
                        width: ListView.view.width
                        height: reportRowLayout.implicitHeight + 14
                        radius: 6
                        color: rowBackgroundColor(modelData.status || "", ListView.isCurrentItem)
                        border.width: ListView.isCurrentItem ? 1 : 0
                        border.color: ListView.isCurrentItem ? FluTheme.primaryColor : "transparent"

                        ColumnLayout{
                            id: reportRowLayout
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 6

                            RowLayout{
                                Layout.fillWidth: true
                                spacing: 8

                                FluText{ text: modelData.finished_at || qsTr("Unknown time"); Layout.fillWidth: true; font: FluTextStyle.Body; elide: Text.ElideRight }

                                FluText{
                                    text: modelData.status || "-"
                                    font: FluTextStyle.Caption
                                    color: statusColor(modelData.status || "")
                                }
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: qsTr("Total %1  Passed %2  Failed %3").arg(modelData.total || 0).arg(modelData.passed || 0).arg(modelData.failed || 0)
                                font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor; elide: Text.ElideRight
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: (modelData.adb_serial || qsTr("No DUT")) + "  |  " + (modelData.duration || "-")
                                font: FluTextStyle.Caption; color: FluTheme.fontSecondaryColor; elide: Text.ElideMiddle
                            }
                        }

                        MouseArea{
                            anchors.fill: parent
                            onClicked: selectReport(index)
                        }
                    }
                }
            }
        }

        Rectangle{
            SplitView.fillWidth: true
            SplitView.minimumWidth: 680
            SplitView.fillHeight: true
            color: FluTheme.dark ? "#202020" : "#ffffff"

            ColumnLayout{
                anchors.fill: parent
                spacing: 0

                Rectangle{
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    color: FluTheme.dark ? "#2b2b2b" : "#f7f7f7"
                    border.width: 1
                    border.color: FluTheme.dark ? "#3c3c3c" : "#e5e7eb"

                    RowLayout{
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 8

                        FluText{ text: loading ? qsTr("Loading...") : statusText; Layout.fillWidth: true; color: FluTheme.fontSecondaryColor; elide: Text.ElideRight }

                        FluIconButton{
                            width: 34; height: 34; iconSource: FluentIcons.Refresh; iconSize: 16
                            text: qsTr("Reload")
                            enabled: selectedReportUrl !== ""
                            onClicked: reportView.reload()
                        }

                        FluIconButton{
                            width: 34; height: 34; iconSource: FluentIcons.PDF; iconSize: 16
                            text: qsTr("Export PDF")
                            enabled: selectedRunId !== ""
                            onClicked: ReportBridge.exportPdf(selectedRunId)
                        }

                        FluIconButton{
                            width: 34; height: 34; iconSource: FluentIcons.OpenInNewWindow; iconSize: 16
                            text: qsTr("Open in browser")
                            enabled: selectedReportUrl !== ""
                            onClicked: Qt.openUrlExternally(selectedReportUrl)
                        }
                    }
                }

                WebEngineView{
                    id: reportView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    profile: reportProfile
                    url: selectedReportUrl

                    onLoadingChanged: function(loadRequest) {
                        if(selectedReportUrl === ""){
                            return
                        }
                        if(loadRequest.status === WebEngineView.LoadSucceededStatus){
                            statusText = qsTr("Ready")
                        } else if(loadRequest.status === WebEngineView.LoadFailedStatus){
                            statusText = qsTr("Failed to load report.")
                        } else if(loadRequest.status === WebEngineView.LoadStartedStatus){
                            statusText = qsTr("Loading...")
                        }
                    }
                }
            }
        }
    }
}
