import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluPage {
    title: qsTr("Report")

    property var reportRowsModel: []
    property var selectedReport: ({})
    property string selectedRunId: ""

    function refreshReports(){
        ReportBridge.refresh()
        reportRowsModel = ReportBridge.reportRows()
        if(reportRowsModel.length === 0){
            selectedRunId = ""
            selectedReport = ({})
            return
        }
        var keepIndex = -1
        for(var i = 0; i < reportRowsModel.length; i++){
            if(reportRowsModel[i].run_id === selectedRunId){
                keepIndex = i
                break
            }
        }
        if(keepIndex < 0){
            keepIndex = 0
        }
        selectedRunId = reportRowsModel[keepIndex].run_id
        selectedReport = ReportBridge.reportDetail(selectedRunId)
        reportList.currentIndex = keepIndex
    }

    function selectReport(index){
        if(index < 0 || index >= reportRowsModel.length){
            return
        }
        selectedRunId = reportRowsModel[index].run_id
        selectedReport = ReportBridge.reportDetail(selectedRunId)
        reportList.currentIndex = index
    }

    function statusColor(status){
        if(status === "passed"){
            return "#0F7B0F"
        }
        if(status === "failed"){
            return "#C42B1C"
        }
        if(status === "stopped"){
            return "#8A6A00"
        }
        if(status === "running"){
            return FluTheme.primaryColor
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
        return "transparent"
    }

    function metricValue(key){
        if(!selectedReport || selectedRunId === ""){
            return "-"
        }
        var value = selectedReport[key]
        return value === undefined || value === null || value === "" ? "-" : String(value)
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

                FluText{
                    Layout.fillWidth: true
                    visible: reportRowsModel.length === 0
                    text: qsTr("No reports yet.")
                    font: FluTextStyle.Body
                    color: FluTheme.fontSecondaryColor
                    wrapMode: Text.WordWrap
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
                                    text: modelData.finished_at ? modelData.finished_at.replace("T", " ").substring(0, 19) : qsTr("Unknown time")
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
                            onClicked: selectReport(index)
                        }
                    }
                }
            }
        }

        Item{
            SplitView.fillWidth: true
            SplitView.minimumWidth: 520
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
                            text: metricValue("finished_at").replace("T", " ").substring(0, 19)
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
                                implicitHeight: 52

                                ColumnLayout{
                                    anchors.fill: parent
                                    anchors.leftMargin: 4
                                    anchors.rightMargin: 4
                                    spacing: 4

                                    FluText{
                                        text: modelData.label
                                        font: FluTextStyle.Caption
                                        color: FluTheme.fontSecondaryColor
                                        elide: Text.ElideRight
                                    }

                                    FluText{
                                        text: modelData.value
                                        font: FluTextStyle.BodyStrong
                                        color: modelData.color
                                        elide: Text.ElideRight
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
                    orientation: Qt.Vertical

                    FluFrame{
                        SplitView.fillWidth: true
                        SplitView.preferredHeight: 260
                        SplitView.minimumHeight: 180
                        padding: 10

                        ColumnLayout{
                            anchors.fill: parent
                            spacing: 8

                            FluText{
                                text: qsTr("Cases")
                                font: FluTextStyle.Subtitle
                            }

                            ListView{
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                model: selectedReport.cases || []
                                boundsBehavior: Flickable.StopAtBounds
                                ScrollBar.vertical: FluScrollBar{}

                                delegate: Rectangle{
                                    width: ListView.view.width
                                    height: caseRow.implicitHeight + 12
                                    radius: 6
                                    color: rowBackgroundColor(modelData.status || "", false)

                                    ColumnLayout{
                                        id: caseRow
                                        anchors.fill: parent
                                        anchors.leftMargin: 8
                                        anchors.rightMargin: 8
                                        anchors.topMargin: 6
                                        anchors.bottomMargin: 6
                                        spacing: 4

                                        RowLayout{
                                            Layout.fillWidth: true
                                            spacing: 8

                                            FluText{
                                                text: modelData.title || modelData.case_nodeid || ""
                                                Layout.fillWidth: true
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
                                            text: modelData.case_nodeid || ""
                                            font: FluTextStyle.Caption
                                            color: FluTheme.fontSecondaryColor
                                            elide: Text.ElideMiddle
                                        }
                                    }
                                }
                            }
                        }
                    }

                    FluFrame{
                        SplitView.fillWidth: true
                        SplitView.fillHeight: true
                        SplitView.minimumHeight: 180
                        padding: 10

                        ColumnLayout{
                            anchors.fill: parent
                            spacing: 8

                            FluText{
                                text: qsTr("Logs")
                                font: FluTextStyle.Subtitle
                            }

                            TextEdit{
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                readOnly: true
                                selectByMouse: true
                                wrapMode: Text.WrapAnywhere
                                text: selectedReport.log_text || ""
                                color: FluTheme.fontPrimaryColor
                                font: FluTextStyle.Caption
                                renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
                            }
                        }
                    }
                }
            }
        }
    }
}
