import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluPage {
    title: qsTr("Run")
    property int footerHeight: 30
    property int runVersion: 0
    property var stepRowsModel: []
    property var logRowsModel: []
    property string logTextModel: ""
    property int selectedStepIndex: -1
    property bool autoFollowLogs: true
    property int previousLogLineCount: 0
    property bool programmaticLogScroll: false
    property real logMovementStartY: 0

    ListModel{
        id: logListModel
    }

    function syncLogListModel(rows){
        if(rows.length < logListModel.count){
            logListModel.clear()
            for(var resetIndex = 0; resetIndex < rows.length; resetIndex++){
                logListModel.append(rows[resetIndex])
            }
            return
        }
        for(var appendIndex = logListModel.count; appendIndex < rows.length; appendIndex++){
            logListModel.append(rows[appendIndex])
        }
    }

    function followLatestLogs(reason){
        autoFollowLogs = true
        if(!logList || logListModel.count === 0){
            return
        }
        programmaticLogScroll = true
        Qt.callLater(function(){
            logList.positionViewAtIndex(logListModel.count - 1, ListView.End)
            Qt.callLater(function(){
                programmaticLogScroll = false
            })
        })
    }

    function refreshRunModels(){
        stepRowsModel = RunBridge.stepRows()
        logRowsModel = RunBridge.logRows()
        logTextModel = RunBridge.logText()
        syncLogListModel(logRowsModel)
        if(selectedStepIndex >= stepRowsModel.length){
            selectedStepIndex = stepRowsModel.length - 1
        }
        if(selectedStepIndex < 0 && stepRowsModel.length > 0){
            selectedStepIndex = stepRowsModel.length - 1
        }
        if(autoFollowLogs && logRowsModel.length !== previousLogLineCount){
            followLatestLogs("new-log-line")
        }
        previousLogLineCount = logRowsModel.length
    }

    function kindLabel(kind){
        if(kind === "action"){
            return "action"
        }
        if(kind === "loop"){
            return "loop"
        }
        if(kind === "setup"){
            return "setup"
        }
        if(kind === "teardown"){
            return "teardown"
        }
        return "case"
    }

    function statusColor(status){
        if(status === "running"){
            return FluTheme.primaryColor
        }
        if(status === "failed"){
            return "#C42B1C"
        }
        if(status === "passed"){
            return "#0F7B0F"
        }
        if(status === "skipped"){
            return FluTheme.fontSecondaryColor
        }
        return FluTheme.fontSecondaryColor
    }

    function rowBackgroundColor(status, selected){
        if(selected){
            return FluTools.withOpacity(FluTheme.primaryColor, FluTheme.dark ? 0.18 : 0.10)
        }
        if(status === "running"){
            return FluTools.withOpacity(FluTheme.primaryColor, FluTheme.dark ? 0.14 : 0.08)
        }
        if(status === "failed"){
            return Qt.rgba(196/255, 43/255, 28/255, 0.10)
        }
        if(status === "passed"){
            return Qt.rgba(15/255, 123/255, 15/255, 0.08)
        }
        return "transparent"
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
    }

    Component.onCompleted: {
        refreshRunModels()
    }

    FluSplitLayout{
        id: runSplit
        anchors.fill: parent
        anchors.bottomMargin: footerHeight
        orientation: Qt.Horizontal

        FluFrame{
            SplitView.fillWidth: true
            SplitView.preferredWidth: runSplit.width * 0.28
            SplitView.minimumWidth: 280
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
                    model: stepRowsModel
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: FluScrollBar{}
                    currentIndex: selectedStepIndex
                    onCurrentIndexChanged: selectedStepIndex = currentIndex

                    delegate: Rectangle{
                        width: ListView.view.width
                        height: contentLayout.implicitHeight + 12
                        radius: 6
                        color: rowBackgroundColor(modelData.status || "", ListView.isCurrentItem)
                        border.width: ListView.isCurrentItem ? 1 : 0
                        border.color: ListView.isCurrentItem ? FluTheme.primaryColor : "transparent"

                        ColumnLayout{
                            id: contentLayout
                            anchors.fill: parent
                            anchors.leftMargin: 10 + (Math.max(0, modelData.depth || 0) * 16)
                            anchors.rightMargin: 8
                            anchors.topMargin: 6
                            anchors.bottomMargin: 6
                            spacing: 8

                            RowLayout{
                                Layout.fillWidth: true
                                spacing: 8

                                Rectangle{
                                    Layout.alignment: Qt.AlignTop
                                    implicitWidth: kindText.implicitWidth + 12
                                    implicitHeight: kindText.implicitHeight + 4
                                    radius: height/2
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
                                    text: modelData.status || ""
                                    font: FluTextStyle.Caption
                                    color: statusColor(modelData.status || "")
                                }
                            }

                            FluText{
                                Layout.fillWidth: true
                                visible: (modelData.definition_id || "") !== "" || (modelData.case_nodeid || "") !== ""
                                text: (modelData.definition_id || "") !== ""
                                      ? (modelData.definition_id + "  |  " + (modelData.case_nodeid || ""))
                                      : (modelData.case_nodeid || "")
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
            SplitView.preferredWidth: runSplit.width * 0.72
            SplitView.minimumWidth: 360
            SplitView.fillHeight: true
            padding: 10

            ColumnLayout{
                anchors.fill: parent
                spacing: 8

                FluText{
                    text: qsTr("Logs")
                    font: FluTextStyle.Subtitle
                }

                Item{
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    ListView{
                        id: logList
                        anchors.fill: parent
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: logScrollBar
                        model: logListModel
                        spacing: 2
                        onMovementStarted: {
                            logMovementStartY = contentY
                        }
                        onMovementEnded: {
                            if(!programmaticLogScroll && autoFollowLogs && contentY < logMovementStartY){
                                autoFollowLogs = false
                            }
                        }

                        delegate: TextEdit{
                            width: logList.width - 20
                            readOnly: true
                            wrapMode: Text.WrapAnywhere
                            text: line || ""
                            color: FluTheme.fontPrimaryColor
                            font: FluTextStyle.Caption
                            selectByMouse: true
                            renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
                            leftPadding: 0
                            rightPadding: 0
                            topPadding: 0
                            bottomPadding: 0
                        }
                    }

                    FluScrollBar{
                        id: logScrollBar
                        anchors{
                            right: parent.right
                            rightMargin: 5
                            top: parent.top
                            bottom: parent.bottom
                            topMargin: 3
                            bottomMargin: 3
                        }
                    }

                    FluIconButton{
                        id: followLatestButton
                        visible: !autoFollowLogs
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.rightMargin: 18
                        anchors.bottomMargin: 18
                        width: 40
                        height: 40
                        radius: 20
                        iconSource: FluentIcons.Down
                        iconSize: 18
                        text: qsTr("Follow Latest")
                        z: 10
                        normalColor: FluTheme.primaryColor
                        hoverColor: Qt.darker(FluTheme.primaryColor, 1.08)
                        pressedColor: Qt.darker(FluTheme.primaryColor, 1.16)
                        iconColor: "#FFFFFF"
                        onClicked: {
                            followLatestLogs("floating-button")
                        }
                    }

                    WheelHandler{
                        target: null
                        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                        onWheel: function(event){
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
        text: RunBridge.isRunning ? qsTr("Stop") : qsTr("Start")
        onClicked: RunBridge.toggleRun()
    }
}
