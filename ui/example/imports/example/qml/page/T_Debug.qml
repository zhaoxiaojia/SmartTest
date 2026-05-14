import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.platform 1.1
import FluentUI 1.0
import "../global"

FluScrollablePage {
    title: qsTr("Debug")
    launchMode: FluPageType.SingleInstance
    focus: true

    property bool loadingVideo: false
    property var reviewSession: ({})
    property var currentFrame: ({})
    property var eventRows: []
    property int currentFrameIndex: -1
    property int frameCount: 0
    property int pendingStartFrame: -1
    property string frameJumpText: "0"
    property int processedFrames: 0
    property int totalFrames: 0
    property int progressPercent: 0
    property int activeFrameImageSlot: 0
    property string frameImageSourceA: ""
    property string frameImageSourceB: ""
    property string pendingFrameImageSource: ""

    function bilingual(en, zh) {
        return TranslateHelper.current === "zh_CN" ? zh : en
    }

    function fixedNumber(value, digits) {
        if (value === undefined || value === null || value === "") {
            return "-"
        }
        return Number(value).toFixed(digits)
    }

    function loadVideo(path) {
        videoPath.text = path
        loadingVideo = true
        reviewSession = ({video: path})
        currentFrame = ({})
        activeFrameImageSlot = 0
        frameImageSourceA = ""
        frameImageSourceB = ""
        pendingFrameImageSource = ""
        currentFrameIndex = -1
        frameCount = 0
        pendingStartFrame = -1
        eventRows = []
        processedFrames = 0
        totalFrames = 0
        progressPercent = 0
        DebugBridge.prepareKpiReview(path)
    }

    function loadFrame(frameIndex) {
        if (frameCount <= 0) {
            return
        }
        DebugBridge.loadKpiReviewFrame(Math.max(0, Math.min(frameCount - 1, Number(frameIndex))))
    }

    function stepFrame(delta) {
        if (frameCount <= 0) {
            return
        }
        DebugBridge.stepKpiReviewFrame(Number(delta))
    }

    function markFrame(marker) {
        if (currentFrameIndex < 0) {
            return
        }
        DebugBridge.markKpiReviewFrame(currentFrameIndex, marker)
    }

    function applyFrame(frame) {
        if (!frame) {
            return
        }
        currentFrame = frame
        currentFrameIndex = Number(frame.frame_index)
        frameJumpText = String(currentFrameIndex)
        var nextSource = frame.image_data_url || frame.image_url || ""
        var activeSource = activeFrameImageSlot === 0 ? frameImageSourceA : frameImageSourceB
        if (activeSource === "") {
            frameImageSourceA = nextSource
            activeFrameImageSlot = 0
        } else if (nextSource !== activeSource) {
            pendingFrameImageSource = nextSource
            if (activeFrameImageSlot === 0) {
                frameImageSourceB = nextSource
            } else {
                frameImageSourceA = nextSource
            }
        }
        pendingStartFrame = Number(frame.pending_start_frame === undefined ? pendingStartFrame : frame.pending_start_frame)
        eventRows = frame.events || eventRows
    }

    function markText() {
        if (!currentFrame || !currentFrame.mark) {
            return bilingual("Unmarked", "\u672a\u6807\u8bb0")
        }
        return currentFrame.mark === "start" ? "START" : "END"
    }

    Keys.onPressed: function(event) {
        if (frameCount <= 0) {
            return
        }
        if (event.key === Qt.Key_Left) {
            stepFrame(-1)
            event.accepted = true
        } else if (event.key === Qt.Key_Right) {
            stepFrame(1)
            event.accepted = true
        } else if (event.key === Qt.Key_S) {
            markFrame("start")
            event.accepted = true
        } else if (event.key === Qt.Key_E) {
            markFrame("end")
            event.accepted = true
        }
    }

    Connections {
        target: DebugBridge
        function onReviewProgress(payload) {
            if (!payload) {
                return
            }
            processedFrames = Number(payload.processed_frames || 0)
            totalFrames = Number(payload.frame_count || 0)
            progressPercent = Number(payload.progress_percent || 0)
        }
        function onReviewPrepared(session) {
            loadingVideo = false
            reviewSession = session || ({})
            frameCount = Number(reviewSession.frame_count || 0)
            totalFrames = frameCount
            progressPercent = frameCount > 0 ? 100 : progressPercent
            showSuccess(bilingual("KPI video loaded.", "KPI\u89c6\u9891\u5df2\u52a0\u8f7d\u3002"))
        }
        function onReviewFrameLoaded(frame) {
            applyFrame(frame)
        }
        function onReviewFrameMarked(frame) {
            applyFrame(frame)
            if (frame && frame.completed_event && frame.completed_event.elapsed_frames !== undefined) {
                showSuccess(bilingual("KPI interval recorded.", "KPI\u95f4\u9694\u5df2\u8bb0\u5f55\u3002"))
            }
        }
        function onErrorOccurred(msg) {
            loadingVideo = false
            showError(msg)
        }
    }

    FileDialog {
        id: videoFileDialog
        title: qsTr("Select video")
        nameFilters: [qsTr("Video files (*.mp4 *.mov *.mkv *.avi *.webm)"), qsTr("All files (*)")]
        onAccepted: loadVideo(currentFile)
    }

    FluFrame {
        Layout.fillWidth: true
        Layout.topMargin: 20
        padding: 12

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                FluText {
                    text: qsTr("KPI Video Tool")
                    font: FluTextStyle.Subtitle
                }

                Item { Layout.fillWidth: true }

                FluText {
                    text: bilingual("Manual start/end review", "\u624b\u52a8 start/end \u590d\u6838")
                    font: FluTextStyle.Caption
                    color: FluTheme.fontSecondaryColor
                }
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
                    enabled: !loadingVideo
                    onClicked: videoFileDialog.open()
                }

                FluFilledButton {
                    text: loadingVideo ? bilingual("Loading", "\u52a0\u8f7d\u4e2d") : bilingual("Load Video", "\u52a0\u8f7d\u89c6\u9891")
                    enabled: !loadingVideo
                    onClicked: loadVideo(videoPath.text)
                }
            }

            FluText {
                Layout.fillWidth: true
                text: loadingVideo
                      ? qsTr("%1 / %2 frames | %3%")
                            .arg(processedFrames)
                            .arg(totalFrames > 0 ? totalFrames : "-")
                            .arg(progressPercent)
                      : bilingual("Scroll through the video, mark one Start and one End. Each completed pair appends an interval result.",
                                  "\u6eda\u52a8\u6d4f\u89c8\u89c6\u9891\uff0c\u4f9d\u6b21\u6253 Start \u548c End\u3002\u6bcf\u5b8c\u6210\u4e00\u5bf9\u5c31\u8ffd\u52a0\u4e00\u6761\u95f4\u9694\u7ed3\u679c\u3002")
                font: FluTextStyle.Caption
                color: FluTheme.fontSecondaryColor
                wrapMode: Text.WordWrap
            }

            FluProgressBar {
                Layout.fillWidth: true
                visible: loadingVideo
                indeterminate: totalFrames <= 0
                value: totalFrames > 0 ? progressPercent / 100 : 0
            }
        }
    }

    FluFrame {
        visible: frameCount > 0
        Layout.fillWidth: true
        Layout.topMargin: 12
        Layout.preferredHeight: 760
        padding: 8

        RowLayout {
            anchors.fill: parent
            spacing: 8

            Rectangle {
                id: videoCanvas
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 640
                color: FluTheme.dark ? "#101010" : "#f6f6f6"
                border.width: 1
                border.color: FluTheme.frameColor
                clip: true

                RowLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 10
                    spacing: 8
                    z: 4

                    FluButton {
                        text: "<"
                        enabled: frameCount > 0
                        onClicked: stepFrame(-1)
                    }

                    FluTextBox {
                        Layout.preferredWidth: 110
                        text: frameJumpText
                        placeholderText: "frame"
                        onEditingFinished: {
                            var idx = Number(text)
                            if (!isNaN(idx)) {
                                loadFrame(idx)
                            }
                        }
                    }

                    FluButton {
                        text: ">"
                        enabled: frameCount > 0
                        onClicked: stepFrame(1)
                    }

                    FluText {
                        Layout.fillWidth: true
                        text: qsTr("%1 / %2  |  %3s  |  %4")
                              .arg(currentFrameIndex >= 0 ? currentFrameIndex : "-")
                              .arg(Math.max(0, frameCount - 1))
                              .arg(fixedNumber(currentFrame.frame_time, 3))
                              .arg(markText())
                        font: FluTextStyle.Caption
                        color: FluTheme.fontSecondaryColor
                        elide: Text.ElideRight
                    }
                }

                Image {
                    id: reviewImageA
                    anchors.fill: parent
                    anchors.leftMargin: 26
                    anchors.rightMargin: 26
                    anchors.topMargin: 46
                    anchors.bottomMargin: 92
                    source: frameImageSourceA
                    fillMode: Image.PreserveAspectFit
                    cache: false
                    opacity: activeFrameImageSlot === 0 ? 1 : 0
                    z: activeFrameImageSlot === 0 ? 1 : 0
                    onStatusChanged: {
                        if (status === Image.Ready && pendingFrameImageSource !== "" && pendingFrameImageSource === frameImageSourceA) {
                            activeFrameImageSlot = 0
                            pendingFrameImageSource = ""
                        }
                    }
                }

                Image {
                    id: reviewImageB
                    anchors.fill: parent
                    anchors.leftMargin: 26
                    anchors.rightMargin: 26
                    anchors.topMargin: 46
                    anchors.bottomMargin: 92
                    source: frameImageSourceB
                    fillMode: Image.PreserveAspectFit
                    cache: false
                    opacity: activeFrameImageSlot === 1 ? 1 : 0
                    z: activeFrameImageSlot === 1 ? 1 : 0
                    onStatusChanged: {
                        if (status === Image.Ready && pendingFrameImageSource !== "" && pendingFrameImageSource === frameImageSourceB) {
                            activeFrameImageSlot = 1
                            pendingFrameImageSource = ""
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: frameCount > 0
                    z: 3
                    acceptedButtons: Qt.NoButton
                    onWheel: function(wheel) {
                        if (wheel.angleDelta.y > 0) {
                            stepFrame(-1)
                        } else if (wheel.angleDelta.y < 0) {
                            stepFrame(1)
                        }
                        wheel.accepted = true
                    }
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 78
                    color: FluTheme.dark ? "#1b1b1b" : "#ffffff"
                    border.width: 1
                    border.color: FluTheme.frameColor
                    z: 5

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 10

                        FluText {
                            text: bilingual("Frame", "\u5e27")
                            font: FluTextStyle.Caption
                            color: FluTheme.fontSecondaryColor
                        }

                        FluSlider {
                            Layout.fillWidth: true
                            from: 0
                            to: Math.max(0, frameCount - 1)
                            stepSize: 1
                            value: currentFrameIndex >= 0 ? currentFrameIndex : 0
                            text: String(Math.round(value))
                            enabled: frameCount > 0
                            onMoved: loadFrame(Math.round(value))
                        }

                        FluFilledButton {
                            text: "Start"
                            enabled: currentFrameIndex >= 0
                            onClicked: markFrame("start")
                        }

                        FluFilledButton {
                            text: "End"
                            enabled: currentFrameIndex >= 0
                            onClicked: markFrame("end")
                        }

                        FluButton {
                            text: bilingual("Clear", "\u6e05\u9664")
                            enabled: currentFrameIndex >= 0 && currentFrame.mark
                            onClicked: markFrame("clear")
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.minimumWidth: 300
                Layout.preferredWidth: 360
                Layout.maximumWidth: 460
                Layout.fillHeight: true
                spacing: 10

                FluText {
                    text: bilingual("Current Pair", "\u5f53\u524d\u914d\u5bf9")
                    font: FluTextStyle.Subtitle
                }

                FluText {
                    Layout.fillWidth: true
                    text: pendingStartFrame >= 0
                          ? bilingual("Start frame: %1", "\u5f00\u59cb\u5e27\uff1a%1").arg(pendingStartFrame)
                          : bilingual("No pending start.", "\u5c1a\u672a\u8bbe\u7f6e start\u3002")
                    font: FluTextStyle.Body
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: FluTheme.frameColor
                }

                FluText {
                    text: bilingual("Results", "\u7ed3\u679c")
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
                        height: 104
                        radius: 6
                        color: index % 2 === 0 ? FluTools.withOpacity(FluTheme.primaryColor, FluTheme.dark ? 0.10 : 0.05) : "transparent"
                        border.width: 1
                        border.color: FluTheme.frameColor

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 4

                            FluText {
                                Layout.fillWidth: true
                                text: qsTr("#%1  start %2  end %3")
                                      .arg(modelData.sequence || index + 1)
                                      .arg(modelData.start_frame)
                                      .arg(modelData.end_frame)
                                font: FluTextStyle.BodyStrong
                                elide: Text.ElideRight
                            }

                            FluText {
                                Layout.fillWidth: true
                                text: bilingual("%1 frames  |  %2 seconds  |  %3 ms",
                                                "%1 \u5e27  |  %2 \u79d2  |  %3 ms")
                                      .arg(modelData.elapsed_frames)
                                      .arg(fixedNumber(modelData.elapsed_seconds, 3))
                                      .arg(fixedNumber(modelData.elapsed_ms, 3))
                                font: FluTextStyle.Body
                                elide: Text.ElideRight
                            }

                            FluText {
                                Layout.fillWidth: true
                                text: qsTr("%1s -> %2s")
                                      .arg(fixedNumber(modelData.start_time, 3))
                                      .arg(fixedNumber(modelData.end_time, 3))
                                font: FluTextStyle.Caption
                                color: FluTheme.fontSecondaryColor
                                elide: Text.ElideRight
                            }
                        }
                    }
                }

                FluText {
                    Layout.fillWidth: true
                    text: eventRows.length === 0
                          ? bilingual("No completed interval yet.", "\u8fd8\u6ca1\u6709\u5b8c\u6210\u7684\u95f4\u9694\u3002")
                          : bilingual("%1 interval(s)", "%1 \u6761\u95f4\u9694").arg(eventRows.length)
                    font: FluTextStyle.Caption
                    color: FluTheme.fontSecondaryColor
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
