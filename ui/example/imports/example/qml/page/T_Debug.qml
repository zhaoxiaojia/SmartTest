import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.platform 1.1
import FluentUI 1.0
import "../global"

FluScrollablePage {
    title: qsTr("Debug")
    launchMode: FluPageType.SingleInstance

    property bool analyzing: false
    property var analysisResult: ({})
    property var eventRows: []
    property var transitionRows: []

    function analyze(path){
        videoPath.text = path
        analyzing = true
        eventRows = []
        transitionRows = []
        analysisResult = ({})
        DebugBridge.analyzeKpiVideo(path)
    }

    function applyAnalysisResult(result){
        analysisResult = result || ({})
        eventRows = analysisResult.events || analysisResult.candidates || []
        transitionRows = analysisResult.transitions || []
    }

    function resultText(key, fallback){
        var value = analysisResult[key]
        if(value === undefined || value === null || value === ""){
            return fallback || "-"
        }
        return String(value)
    }

    function fixedNumber(value, digits){
        if(value === undefined || value === null || value === ""){
            return "-"
        }
        return Number(value).toFixed(digits)
    }

    Connections {
        target: DebugBridge
        function onAnalysisStarted(path){
            analyzing = true
            videoPath.text = path
        }
        function onAnalysisFinished(result){
            analyzing = false
            applyAnalysisResult(result)
        }
        function onErrorOccurred(msg){
            analyzing = false
            showError(msg)
        }
    }

    FileDialog {
        id: videoFileDialog
        title: qsTr("Select video")
        nameFilters: [qsTr("Video files (*.mp4 *.mov *.mkv *.avi *.webm)"), qsTr("All files (*)")]
        onAccepted: {
            analyze(currentFile)
        }
    }

    FluFrame {
        Layout.fillWidth: true
        Layout.topMargin: 20
        padding: 12

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            FluText {
                text: qsTr("KPI Video Frame Counter")
                font: FluTextStyle.Subtitle
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                FluTextBox {
                    id: videoPath
                    Layout.fillWidth: true
                    placeholderText: qsTr("Select a recorded video")
                }

                FluButton {
                    text: qsTr("Browse")
                    enabled: !analyzing
                    onClicked: videoFileDialog.open()
                }

                FluFilledButton {
                    text: analyzing ? qsTr("Analyzing") : qsTr("Analyze")
                    enabled: !analyzing
                    onClicked: analyze(videoPath.text)
                }
            }

            FluText {
                Layout.fillWidth: true
                text: analyzing
                      ? qsTr("Reading frames and detecting visual state transitions...")
                      : qsTr("The tool detects repeated red-light actions and playback start frames for review.")
                font: FluTextStyle.Caption
                color: FluTheme.fontSecondaryColor
                wrapMode: Text.WordWrap
            }
        }
    }

    FluFrame {
        visible: resultText("video", "") !== ""
        Layout.fillWidth: true
        Layout.topMargin: 12
        padding: 12

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            FluText {
                text: qsTr("Detected Summary")
                font: FluTextStyle.Subtitle
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 4
                rowSpacing: 8
                columnSpacing: 16

                Repeater {
                    model: [
                        {label: qsTr("Start Frame"), value: resultText("start_frame")},
                        {label: qsTr("End Frame"), value: resultText("end_frame")},
                        {label: qsTr("Elapsed Frames"), value: resultText("elapsed_frames")},
                        {label: qsTr("Elapsed"), value: resultText("elapsed_ms") + " ms"},
                        {label: qsTr("Actions"), value: String(eventRows.length)},
                        {label: qsTr("FPS"), value: fixedNumber(analysisResult.fps, 3)},
                        {label: qsTr("Frames"), value: resultText("frame_count")},
                        {label: qsTr("Duration"), value: fixedNumber(analysisResult.duration_seconds, 3) + " s"}
                    ]

                    delegate: ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        FluText {
                            text: modelData.label
                            font: FluTextStyle.Caption
                            color: FluTheme.fontSecondaryColor
                        }

                        FluText {
                            text: modelData.value
                            font: FluTextStyle.BodyStrong
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }

    FluFrame {
        visible: eventRows.length > 0
        Layout.fillWidth: true
        Layout.topMargin: 12
        Layout.preferredHeight: Math.min(760, eventRows.length * 246 + 58)
        padding: 12

        ColumnLayout {
            anchors.fill: parent
            spacing: 8

            FluText {
                text: qsTr("Repeated Action Detections")
                font: FluTextStyle.Subtitle
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: eventRows
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: FluScrollBar {}

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 238
                    radius: 6
                    color: index % 2 === 0 ? FluTools.withOpacity(FluTheme.primaryColor, FluTheme.dark ? 0.10 : 0.05) : "transparent"
                    border.width: 1
                    border.color: FluTheme.frameColor

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 5

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            FluText {
                                text: "#" + String(index + 1)
                                font: FluTextStyle.BodyStrong
                            }

                            FluText {
                                Layout.fillWidth: true
                                text: qsTr("start %1  end %2  delta %3 frames  %4 ms")
                                      .arg(modelData.start_frame)
                                      .arg(modelData.end_frame)
                                      .arg(modelData.elapsed_frames)
                                      .arg(modelData.elapsed_ms)
                                font: FluTextStyle.Body
                                elide: Text.ElideRight
                            }

                            FluText {
                                text: fixedNumber(modelData.confidence, 2)
                                font: FluTextStyle.Caption
                                color: FluTheme.primaryColor
                            }
                        }

                        FluText {
                            Layout.fillWidth: true
                            text: qsTr("time %1s -> %2s | red light score %3  playback score %4")
                                  .arg(fixedNumber(modelData.start_time, 3))
                                  .arg(fixedNumber(modelData.end_time, 3))
                                  .arg(fixedNumber(modelData.start_score, 3))
                                  .arg(fixedNumber(modelData.end_score, 3))
                            font: FluTextStyle.Caption
                            color: FluTheme.fontSecondaryColor
                            elide: Text.ElideRight
                        }

                        FluText {
                            Layout.fillWidth: true
                            text: qsTr("red light at %1,%2 area %3 | transition frame %4 | luminance %5->%6")
                                  .arg(fixedNumber(modelData.start_red_x, 3))
                                  .arg(fixedNumber(modelData.start_red_y, 3))
                                  .arg(modelData.start_red_area || "-")
                                  .arg(modelData.transition_frame || "-")
                                  .arg(fixedNumber(modelData.end_luminance_before, 1))
                                  .arg(fixedNumber(modelData.end_luminance_after, 1))
                            font: FluTextStyle.Caption
                            color: FluTheme.fontSecondaryColor
                            elide: Text.ElideRight
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                FluText {
                                    text: qsTr("Start frame %1").arg(modelData.start_frame || "-")
                                    font: FluTextStyle.Caption
                                    color: FluTheme.fontSecondaryColor
                                }

                                Image {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 128
                                    fillMode: Image.PreserveAspectFit
                                    source: modelData.start_image_url || ""
                                    cache: false
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                FluText {
                                    text: qsTr("End frame %1").arg(modelData.end_frame || "-")
                                    font: FluTextStyle.Caption
                                    color: FluTheme.fontSecondaryColor
                                }

                                Image {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 128
                                    fillMode: Image.PreserveAspectFit
                                    source: modelData.end_image_url || ""
                                    cache: false
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    FluFrame {
        visible: transitionRows.length > 0
        Layout.fillWidth: true
        Layout.topMargin: 12
        Layout.preferredHeight: 260
        padding: 12

        ColumnLayout {
            anchors.fill: parent
            spacing: 8

            FluText {
                text: qsTr("Detected State Changes")
                font: FluTextStyle.Subtitle
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: transitionRows
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: FluScrollBar {}

                delegate: RowLayout {
                    width: ListView.view.width
                    height: 30
                    spacing: 10

                    FluText {
                        Layout.preferredWidth: 80
                        text: qsTr("frame %1").arg(modelData.frame)
                        font: FluTextStyle.Caption
                    }

                    FluText {
                        Layout.preferredWidth: 70
                        text: fixedNumber(modelData.time, 3) + "s"
                        font: FluTextStyle.Caption
                        color: FluTheme.fontSecondaryColor
                    }

                    FluText {
                        Layout.preferredWidth: 90
                        text: qsTr("score %1").arg(fixedNumber(modelData.score, 3))
                        font: FluTextStyle.Caption
                        color: FluTheme.fontSecondaryColor
                    }

                    FluText {
                        Layout.fillWidth: true
                        text: qsTr("luma %1 -> %2  sat %3 -> %4")
                              .arg(fixedNumber(modelData.luminance_before, 1))
                              .arg(fixedNumber(modelData.luminance_after, 1))
                              .arg(fixedNumber(modelData.saturation_before, 1))
                              .arg(fixedNumber(modelData.saturation_after, 1))
                        font: FluTextStyle.Caption
                        color: FluTheme.fontSecondaryColor
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
}
