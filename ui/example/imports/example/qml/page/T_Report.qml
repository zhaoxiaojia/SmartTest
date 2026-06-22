import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../component"
import "../global"

FluPage {
    title: qsTr("Report")
    launchMode: FluPageType.SingleInstance

    property var reportRowsModel: []
    property var selectedReport: ({})
    property string selectedRunId: ""
    property int selectedStepIndex: -1

    function refreshReports(preferredRunId){
        ReportBridge.refresh()
        reportRowsModel = ReportBridge.reportRows()
        if(reportRowsModel.length === 0){
            selectedRunId = ""
            selectedReport = ({})
            selectedStepIndex = -1
            return
        }
        var keepIndex = 0
        if(preferredRunId !== undefined && preferredRunId !== ""){
            for(var preferredIndex = 0; preferredIndex < reportRowsModel.length; preferredIndex++){
                if(reportRowsModel[preferredIndex].run_id === preferredRunId){
                    keepIndex = preferredIndex
                    selectReport(keepIndex)
                    return
                }
            }
        }
        for(var i = 0; i < reportRowsModel.length; i++){
            if(reportRowsModel[i].run_id === selectedRunId){
                keepIndex = i
                break
            }
        }
        selectReport(keepIndex)
    }

    function selectReport(index){
        if(index < 0 || index >= reportRowsModel.length){
            return
        }
        selectedRunId = reportRowsModel[index].run_id
        selectedReport = ReportBridge.reportDetail(selectedRunId)
        reportList.currentIndex = index
        selectedStepIndex = firstFailedStepIndex()
        if(selectedStepIndex < 0 && (selectedReport.steps || []).length > 0){
            selectedStepIndex = 0
        }
    }

    function firstFailedStepIndex(){
        var rows = selectedReport.steps || []
        for(var i = 0; i < rows.length; i++){
            if(rows[i].status === "failed"){
                return i
            }
        }
        return -1
    }

    function selectedStep(){
        var rows = selectedReport.steps || []
        if(selectedStepIndex < 0 || selectedStepIndex >= rows.length){
            return ({})
        }
        return rows[selectedStepIndex]
    }

    function selectedLogRows(){
        return selectedReport.logs || []
    }

    function statusColor(status){
        if(status === "passed"){
            return "#0F7B0F"
        }
        if(status === "failed"){
            return "#C42B1C"
        }
        if(status === "running"){
            return FluTheme.primaryColor
        }
        if(status === "planned"){
            return "#8764B8"
        }
        if(status === "stopped"){
            return "#8A6A00"
        }
        return FluTheme.fontSecondaryColor
    }

    function rowBackgroundColor(status, selected){
        if(selected){
            return FluTools.withOpacity(FluTheme.primaryColor, FluTheme.dark ? 0.18 : 0.10)
        }
        if(status === "failed"){
            return Qt.rgba(196/255, 43/255, 28/255, 0.08)
        }
        if(status === "passed"){
            return Qt.rgba(15/255, 123/255, 15/255, 0.06)
        }
        if(status === "running"){
            return FluTools.withOpacity(FluTheme.primaryColor, FluTheme.dark ? 0.14 : 0.08)
        }
        return "transparent"
    }

    function kindLabel(kind){
        if(kind === "case") return "case"
        if(kind === "setup") return "setup"
        if(kind === "teardown") return "teardown"
        if(kind === "check") return "check"
        return "step"
    }

    function metricValue(key){
        if(!selectedReport || selectedRunId === ""){
            return "-"
        }
        var value = selectedReport[key]
        return value === undefined || value === null || value === "" ? "-" : String(value)
    }

    function objectText(value){
        if(value === undefined || value === null || value === ""){
            return "-"
        }
        if(typeof value === "string"){
            return value
        }
        return JSON.stringify(value, null, 2)
    }

    function detailRows(){
        var step = selectedStep()
        var rows = [
            {label: qsTr("DUT"), value: selectedReport.adb_serial || qsTr("No DUT")},
            {label: qsTr("Run Status"), value: selectedReport.status || "-"},
            {label: qsTr("Return Code"), value: metricValue("returncode")},
            {label: qsTr("Stopped"), value: selectedReport.stopped ? qsTr("Yes") : qsTr("No")}
        ]
        if(step && step.id){
            rows.push({label: qsTr("Step Status"), value: step.status || "-"})
            rows.push({label: qsTr("Kind"), value: step.kind || "-"})
            rows.push({label: qsTr("Duration"), value: String(step.duration_ms || 0) + " ms"})
            rows.push({label: qsTr("Definition"), value: step.definition_id || "-"})
            rows.push({label: qsTr("Case"), value: step.case_nodeid || "-"})
            if(step.error !== undefined && step.error !== null && step.error !== "" && JSON.stringify(step.error) !== "{}"){
                rows.push({label: qsTr("Error"), value: objectText(step.error)})
            }
        }
        return rows
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

                    FluText{
                        text: qsTr("Runs")
                        font: FluTextStyle.Subtitle
                        Layout.fillWidth: true
                    }

                    FluIconButton{
                        width: 34
                        height: 34
                        iconSource: FluentIcons.Refresh
                        iconSize: 16
                        text: qsTr("Refresh")
                        onClicked: refreshReports()
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

                                FluText{
                                    text: modelData.finished_at || qsTr("Unknown time")
                                    Layout.fillWidth: true
                                    font: FluTextStyle.Body
                                    elide: Text.ElideRight
                                }

                                FluText{
                                    text: modelData.status || "-"
                                    font: FluTextStyle.Caption
                                    color: statusColor(modelData.status || "")
                                }
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: qsTr("Total %1  Passed %2  Failed %3").arg(modelData.total || 0).arg(modelData.passed || 0).arg(modelData.failed || 0)
                                font: FluTextStyle.Caption
                                color: FluTheme.fontSecondaryColor
                                elide: Text.ElideRight
                            }

                            FluText{
                                Layout.fillWidth: true
                                text: (modelData.adb_serial || qsTr("No DUT")) + "  |  " + (modelData.duration || "-")
                                font: FluTextStyle.Caption
                                color: FluTheme.fontSecondaryColor
                                elide: Text.ElideMiddle
                            }
                        }

                        MouseArea{
                            anchors.fill: parent
                            onClicked: {
                                selectReport(index)
                                ReportBridge.openReportFolder(modelData.run_id || "")
                            }
                        }
                    }
                }
            }
        }

        Item{
            SplitView.fillWidth: true
            SplitView.minimumWidth: 680
            SplitView.fillHeight: true

            ColumnLayout{
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10

                FluText{
                    visible: selectedRunId === ""
                    text: qsTr("Run a test to generate the first report.")
                    font: FluTextStyle.Body
                    color: FluTheme.fontSecondaryColor
                    wrapMode: Text.WordWrap
                }

                ColumnLayout{
                    visible: selectedRunId !== ""
                    Layout.fillWidth: true
                    spacing: 10

                    RowLayout{
                        Layout.fillWidth: true
                        spacing: 10

                        FluText{
                            text: metricValue("finished_at")
                            font: FluTextStyle.Subtitle
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        FluText{
                            text: metricValue("status")
                            font: FluTextStyle.BodyStrong
                            color: statusColor(selectedReport.status || "")
                        }
                    }

                    RowLayout{
                        Layout.fillWidth: true
                        spacing: 8

                        Repeater{
                            model: [
                                {label: qsTr("Total"), value: metricValue("total"), color: FluTheme.fontPrimaryColor},
                                {label: qsTr("Passed"), value: metricValue("passed"), color: "#0F7B0F"},
                                {label: qsTr("Failed"), value: metricValue("failed"), color: "#C42B1C"},
                                {label: qsTr("Skipped"), value: metricValue("skipped"), color: FluTheme.fontSecondaryColor},
                                {label: qsTr("Duration"), value: metricValue("duration"), color: FluTheme.fontPrimaryColor}
                            ]

                            delegate: Item{
                                Layout.fillWidth: true
                                implicitHeight: 48

                                ColumnLayout{
                                    anchors.fill: parent
                                    spacing: 4

                                    FluText{
                                        text: modelData.label
                                        font: FluTextStyle.Caption
                                        color: FluTheme.fontSecondaryColor
                                    }

                                    FluText{
                                        text: modelData.value
                                        font: FluTextStyle.BodyStrong
                                        color: modelData.color
                                    }
                                }
                            }
                        }
                    }
                }

                FluSplitLayout{
                    visible: selectedRunId !== ""
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    orientation: Qt.Horizontal

                    FluFrame{
                        SplitView.preferredWidth: 520
                        SplitView.minimumWidth: 360
                        SplitView.fillHeight: true
                        padding: 10

                        ColumnLayout{
                            anchors.fill: parent
                            spacing: 8

                            FluText{
                                text: qsTr("Steps")
                                font: FluTextStyle.Subtitle
                            }

                            ListView{
                                id: stepList
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                model: selectedReport.steps || []
                                currentIndex: selectedStepIndex
                                boundsBehavior: Flickable.StopAtBounds
                                ScrollBar.vertical: FluScrollBar{}
                                onCurrentIndexChanged: selectedStepIndex = currentIndex

                                delegate: Rectangle{
                                    width: ListView.view.width
                                    height: stepRow.implicitHeight + 12
                                    radius: 6
                                    color: rowBackgroundColor(modelData.status || "", ListView.isCurrentItem)
                                    border.width: ListView.isCurrentItem ? 1 : 0
                                    border.color: ListView.isCurrentItem ? FluTheme.primaryColor : "transparent"

                                    ColumnLayout{
                                        id: stepRow
                                        anchors.fill: parent
                                        anchors.leftMargin: 8 + (Math.max(0, modelData.depth || 0) * 16)
                                        anchors.rightMargin: 8
                                        anchors.topMargin: 6
                                        anchors.bottomMargin: 6
                                        spacing: 5

                                        RowLayout{
                                            Layout.fillWidth: true
                                            spacing: 8

                                            Rectangle{
                                                implicitWidth: kindText.implicitWidth + 12
                                                implicitHeight: kindText.implicitHeight + 4
                                                radius: height / 2
                                                color: FluTools.withOpacity(statusColor(modelData.status || ""), 0.12)

                                                FluText{
                                                    id: kindText
                                                    anchors.centerIn: parent
                                                    text: kindLabel(modelData.kind || "")
                                                    font: FluTextStyle.Caption
                                                    color: statusColor(modelData.status || "")
                                                }
                                            }

                                            FluText{
                                                text: modelData.title || ""
                                                Layout.fillWidth: true
                                                wrapMode: Text.Wrap
                                                maximumLineCount: 2
                                                elide: Text.ElideRight
                                            }

                                            FluText{
                                                text: modelData.status || "-"
                                                font: FluTextStyle.Caption
                                                color: statusColor(modelData.status || "")
                                            }
                                        }

                                        FluText{
                                            Layout.fillWidth: true
                                            text: modelData.definition_id || modelData.case_nodeid || ""
                                            font: FluTextStyle.Caption
                                            color: FluTheme.fontSecondaryColor
                                            elide: Text.ElideMiddle
                                        }
                                    }

                                    MouseArea{
                                        anchors.fill: parent
                                        onClicked: stepList.currentIndex = index
                                    }
                                }
                            }
                        }
                    }

                    FluFrame{
                        SplitView.fillWidth: true
                        SplitView.minimumWidth: 360
                        SplitView.fillHeight: true
                        padding: 10

                        ColumnLayout{
                            anchors.fill: parent
                            spacing: 8

                            FluText{
                                text: qsTr("Step Detail")
                                font: FluTextStyle.Subtitle
                            }

                            Flow{
                                Layout.fillWidth: true
                                spacing: 8

                                Repeater{
                                    model: detailRows()

                                    delegate: Rectangle{
                                        width: Math.min(parent.width, Math.max(170, detailValue.implicitWidth + 18))
                                        height: detailLabel.implicitHeight + detailValue.implicitHeight + 12
                                        radius: 4
                                        color: FluTools.withOpacity(FluTheme.fontSecondaryColor, FluTheme.dark ? 0.08 : 0.06)

                                        ColumnLayout{
                                            anchors.fill: parent
                                            anchors.margins: 6
                                            spacing: 2

                                            FluText{
                                                id: detailLabel
                                                text: modelData.label
                                                font: FluTextStyle.Caption
                                                color: FluTheme.fontSecondaryColor
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }

                                            FluText{
                                                id: detailValue
                                                text: modelData.value
                                                font: FluTextStyle.Caption
                                                color: modelData.label === qsTr("Error") ? statusColor("failed") : FluTheme.fontPrimaryColor
                                                elide: Text.ElideMiddle
                                                maximumLineCount: 2
                                                wrapMode: Text.WrapAnywhere
                                                Layout.fillWidth: true
                                            }
                                        }
                                    }
                                }
                            }

                            FluText{
                                text: qsTr("Logs")
                                font: FluTextStyle.Subtitle
                            }

                            LogListView{
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                model: selectedLogRows()
                            }
                        }
                    }
                }
            }
        }
    }
}
