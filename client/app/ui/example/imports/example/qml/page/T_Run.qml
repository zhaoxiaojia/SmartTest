import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../component"

FluPage {
    id: page_root
    title: qsTr("Run")
    launchMode: FluPageType.SingleInstance

    property int footerHeight: 30
    property int runVersion: 0
    property var dutRowsModel: []
    property string validationDialogMessage: ""

    function refreshRunModels(){
        dutRowsModel = RunBridge.dutRunRows()
    }

    function statusColor(status){
        if(status === "running") return FluTheme.primaryColor
        if(status === "failed") return "#C42B1C"
        if(status === "passed") return "#0F7B0F"
        if(status === "stopped") return "#8A6A00"
        return FluTheme.fontSecondaryColor
    }

    function rowBackgroundColor(status){
        if(status === "running") return FluTools.withOpacity(FluTheme.primaryColor, FluTheme.dark ? 0.12 : 0.06)
        if(status === "failed") return Qt.rgba(196/255, 43/255, 28/255, 0.08)
        if(status === "passed") return Qt.rgba(15/255, 123/255, 15/255, 0.06)
        return "transparent"
    }

    function stepIndent(depth){
        return 12 + (Math.max(0, depth || 0) * 16)
    }

    Connections{
        target: RunBridge
        function onStepsChanged(){
            runVersion = runVersion + 1
            refreshRunModels()
        }
        function onLogsChanged(){
            runVersion = runVersion + 1
            refreshRunModels()
        }
        function onRunningChanged(){
            runVersion = runVersion + 1
            refreshRunModels()
        }
        function onErrorOccurred(msg){
            showError(msg)
        }
        function onValidationFailed(msg){
            validationDialogMessage = msg
            dialog_validation.open()
        }
    }

    Component.onCompleted: refreshRunModels()

    ColumnLayout{
        anchors.fill: parent
        anchors.bottomMargin: footerHeight
        spacing: 0

        Rectangle{
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            color: FluTheme.dark ? "#202020" : "#ffffff"
            border.width: 1
            border.color: FluTheme.dark ? "#3c3c3c" : "#e5e7eb"

            RowLayout{
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12

                FluText{
                    text: qsTr("DUT Progress")
                    font: FluTextStyle.Subtitle
                    Layout.fillWidth: true
                }
                FluText{
                    text: qsTr("Total %1").arg(dutRowsModel.length)
                    color: FluTheme.fontSecondaryColor
                }
                FluText{
                    text: qsTr("Running %1").arg(dutRowsModel.filter(function(row){ return row.status === "running" }).length)
                    color: statusColor("running")
                }
                FluText{
                    text: qsTr("Failed %1").arg(dutRowsModel.filter(function(row){ return row.status === "failed" }).length)
                    color: statusColor("failed")
                }
                FluText{
                    text: qsTr("Passed %1").arg(dutRowsModel.filter(function(row){ return row.status === "passed" }).length)
                    color: statusColor("passed")
                }
            }
        }

        ListView{
            id: dutList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: dutRowsModel
            spacing: 8
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: FluScrollBar{}
            leftMargin: 10
            rightMargin: 10
            topMargin: 10
            bottomMargin: 10

            delegate: Rectangle{
                id: dutPanel
                width: ListView.view.width - 20
                height: panelLayout.implicitHeight + 2
                radius: 6
                color: rowBackgroundColor(modelData.status || "")
                border.width: 1
                border.color: FluTheme.dark ? "#3c3c3c" : "#e5e7eb"

                property bool expanded: index === 0
                property bool logsExpanded: false

                ColumnLayout{
                    id: panelLayout
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 10
                    spacing: 8

                    RowLayout{
                        Layout.fillWidth: true
                        spacing: 8

                        Rectangle{
                            width: 10
                            height: 10
                            radius: 5
                            color: statusColor(modelData.status || "")
                        }
                        FluText{
                            text: modelData.dut_serial || qsTr("No DUT")
                            font: FluTextStyle.BodyStrong
                            Layout.fillWidth: true
                            elide: Text.ElideMiddle
                        }
                        FluText{
                            text: modelData.progress_text || "0/0"
                            color: FluTheme.fontSecondaryColor
                        }
                        FluText{
                            text: modelData.status || "-"
                            color: statusColor(modelData.status || "")
                        }
                        FluIconButton{
                            width: 30
                            height: 30
                            iconSource: dutPanel.expanded ? FluentIcons.ChevronUp : FluentIcons.ChevronDown
                            iconSize: 13
                            text: dutPanel.expanded ? qsTr("Collapse") : qsTr("Expand")
                            onClicked: dutPanel.expanded = !dutPanel.expanded
                        }
                    }

                    ProgressBar{
                        Layout.fillWidth: true
                        from: 0
                        to: Math.max(1, modelData.total || 0)
                        value: modelData.completed || 0
                    }

                    ColumnLayout{
                        visible: dutPanel.expanded
                        Layout.fillWidth: true
                        spacing: 4

                        Repeater{
                            model: modelData.steps || []
                            delegate: Rectangle{
                                Layout.fillWidth: true
                                implicitHeight: stepRow.implicitHeight + 8
                                radius: 4
                                color: "transparent"

                                RowLayout{
                                    id: stepRow
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.leftMargin: stepIndent(modelData.depth)
                                    anchors.rightMargin: 8
                                    spacing: 8

                                    FluText{
                                        text: modelData.kind === "case" ? qsTr("case") : qsTr("step")
                                        font: FluTextStyle.Caption
                                        color: statusColor(modelData.status || "")
                                    }
                                    FluText{
                                        Layout.fillWidth: true
                                        text: modelData.title || ""
                                        wrapMode: Text.Wrap
                                        maximumLineCount: 2
                                        elide: Text.ElideRight
                                    }
                                    FluText{
                                        text: modelData.status || ""
                                        font: FluTextStyle.Caption
                                        color: statusColor(modelData.status || "")
                                    }
                                }
                            }
                        }

                        Rectangle{
                            Layout.fillWidth: true
                            implicitHeight: logHeader.implicitHeight + 8
                            radius: 4
                            color: FluTools.withOpacity(FluTheme.fontSecondaryColor, FluTheme.dark ? 0.08 : 0.04)
                            RowLayout{
                                id: logHeader
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                FluText{
                                    text: qsTr("Logs (%1)").arg(modelData.log_count || 0)
                                    Layout.fillWidth: true
                                    color: FluTheme.fontSecondaryColor
                                }
                                FluIconButton{
                                    width: 28
                                    height: 28
                                    iconSource: dutPanel.logsExpanded ? FluentIcons.ChevronUp : FluentIcons.ChevronDown
                                    iconSize: 12
                                    text: dutPanel.logsExpanded ? qsTr("Hide logs") : qsTr("Show logs")
                                    onClicked: dutPanel.logsExpanded = !dutPanel.logsExpanded
                                }
                            }
                            MouseArea{
                                anchors.fill: parent
                                onClicked: dutPanel.logsExpanded = !dutPanel.logsExpanded
                            }
                        }

                        LogListView{
                            visible: dutPanel.logsExpanded
                            Layout.fillWidth: true
                            Layout.preferredHeight: 220
                            model: modelData.logs || []
                        }
                    }
                }
            }
        }
    }

    FluFilledButton{
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: footerHeight
        text: RunBridge.isRunning ? qsTr("Stop All") : qsTr("Start")
        onClicked: RunBridge.toggleRun()
    }

    FluContentDialog{
        id: dialog_validation
        title: qsTr("Required Parameters")
        buttonFlags: FluContentDialogType.PositiveButton
        positiveText: qsTr("OK")
        contentDelegate: Component{
            Item{
                implicitWidth: dialog_validation.width
                implicitHeight: validation_message_text.implicitHeight + 16
                FluText{
                    id: validation_message_text
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    anchors.topMargin: 4
                    text: page_root.validationDialogMessage
                    font: FluTextStyle.Body
                    wrapMode: Text.Wrap
                }
            }
        }
    }
}
