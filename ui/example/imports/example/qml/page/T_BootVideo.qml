import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.platform 1.1
import FluentUI 1.0

FluScrollablePage {
    title: qsTr("Boot Video")
    launchMode: FluPageType.SingleInstance

    property var cameraRows: []
    property var cameraModes: []
    property var bootSettings: ({})
    property bool probingModes: false
    property string previewSource: ""
    property bool previewFrontVisible: true
    property string currentState: "idle"
    property real logoScore: 0
    property real homeScore: 0
    property real glareRatio: 0
    property int logoMs: -1
    property int homeMs: -1
    property int bootMs: -1
    property string resultDir: ""

    function loadSettings() {
        bootSettings = BootVideoBridge.settings()
        deviceId.text = String(bootSettings.device_id || 0)
        syncModeSelection()
        analysisFpsInput.text = String(bootSettings.analysis_fps || 5)
        roiX.text = String((bootSettings.roi || {}).x || 0)
        roiY.text = String((bootSettings.roi || {}).y || 0)
        roiW.text = String((bootSettings.roi || {}).width || 1280)
        roiH.text = String((bootSettings.roi || {}).height || 720)
        logoTemplate.text = bootSettings.logo_template_path || ""
        homeTemplate.text = bootSettings.home_template_path || ""
        logoThreshold.text = String(bootSettings.logo_threshold || 0.8)
        homeThreshold.text = String(bootSettings.home_threshold || 0.8)
        logoFrames.text = String(bootSettings.logo_confirm_frames || 3)
        homeFrames.text = String(bootSettings.home_confirm_frames || 3)
        homeStable.text = String(bootSettings.home_stable_duration_s || 0.5)
        powerDelayInput.text = String(bootSettings.power_delay_seconds === undefined ? 0 : bootSettings.power_delay_seconds)
        glareSkipInput.text = String(bootSettings.glare_skip_ratio === undefined ? 0.08 : bootSettings.glare_skip_ratio)
        timeoutInput.text = String(bootSettings.timeout_seconds || 30)
        resultDir = bootSettings.last_result_dir || ""
    }

    function collectSettings() {
        var selectedMode = cameraModes.length > modeCombo.currentIndex && modeCombo.currentIndex >= 0 ? cameraModes[modeCombo.currentIndex] : {}
        return {
            device_id: Number(deviceId.text),
            width: Number(selectedMode.width || bootSettings.width || 1280),
            height: Number(selectedMode.height || bootSettings.height || 720),
            fps: Number(selectedMode.fps || bootSettings.fps || 30),
            analysis_fps: Number(analysisFpsInput.text),
            roi: {
                x: Number(roiX.text),
                y: Number(roiY.text),
                width: Number(roiW.text),
                height: Number(roiH.text)
            },
            logo_template_path: logoTemplate.text,
            home_template_path: homeTemplate.text,
            logo_threshold: Number(logoThreshold.text),
            home_threshold: Number(homeThreshold.text),
            logo_confirm_frames: Number(logoFrames.text),
            home_confirm_frames: Number(homeFrames.text),
            home_stable_duration_s: Number(homeStable.text),
            power_delay_seconds: Number(powerDelayInput.text),
            glare_skip_ratio: Number(glareSkipInput.text),
            timeout_seconds: Number(timeoutInput.text),
            last_result_dir: resultDir
        }
    }

    function syncModeSelection() {
        if (!modeModel) {
            return
        }
        modeModel.clear()
        var selectedIndex = 0
        for (var i = 0; i < cameraModes.length; i++) {
            var mode = cameraModes[i]
            modeModel.append({ text: mode.label || (mode.width + " x " + mode.height + " @ " + mode.fps + " fps") })
            if (Number(mode.width) === Number(bootSettings.width) && Number(mode.height) === Number(bootSettings.height) && Number(mode.fps) === Number(bootSettings.fps)) {
                selectedIndex = i
            }
        }
        modeCombo.currentIndex = cameraModes.length > 0 ? selectedIndex : -1
    }

    function metricText(value) {
        return value >= 0 ? qsTr("%1 ms").arg(value) : "-"
    }

    Component.onCompleted: {
        loadSettings()
        BootVideoBridge.refreshCameras()
    }

    Component.onDestruction: {
        BootVideoBridge.stopTest()
        BootVideoBridge.closeCamera()
    }

    Connections {
        target: BootVideoBridge
        function onCamerasChanged() {
            cameraRows = BootVideoBridge.cameraRows()
        }
        function onCameraModesChanged() {
            cameraModes = BootVideoBridge.cameraModes()
            probingModes = BootVideoBridge.isProbingCameraModes()
            syncModeSelection()
        }
        function onStateChanged() {
            loadSettings()
        }
        function onPreviewChanged(source) {
            previewSource = source
            if (previewFrontVisible) {
                previewBack.source = source
            } else {
                previewFront.source = source
            }
        }
        function onStatusUpdated(payload) {
            if (!payload) {
                return
            }
            currentState = payload.state || currentState
            logoScore = Number(payload.logo_score || logoScore)
            homeScore = Number(payload.home_score || homeScore)
            glareRatio = Number(payload.glare_ratio || glareRatio)
            var durations = payload.durations_ms || {}
            logoMs = durations.logo_appearance === undefined || durations.logo_appearance === null ? logoMs : Number(durations.logo_appearance)
            homeMs = durations.home_appearance === undefined || durations.home_appearance === null ? homeMs : Number(durations.home_appearance)
            bootMs = durations.boot_total === undefined || durations.boot_total === null ? bootMs : Number(durations.boot_total)
        }
        function onTestFinished(result) {
            if (result && result.result_dir) {
                resultDir = result.result_dir
            }
            if (result && result.status === "completed") {
                showSuccess(qsTr("Boot video test completed."))
            } else if (result && result.status === "timeout") {
                showInfo(result.failure_reason || qsTr("Boot video test timed out."))
            } else if (result && result.status === "cancelled") {
                showInfo(result.failure_reason || qsTr("Boot video test cancelled."))
            } else if (result && result.failure_reason) {
                showError(result.failure_reason)
            }
        }
        function onErrorOccurred(message) {
            showError(message)
        }
    }

    FileDialog {
        id: logoDialog
        title: qsTr("Select Logo Template")
        nameFilters: [qsTr("Image files (*.png *.jpg *.jpeg *.bmp)"), qsTr("All files (*)")]
        onAccepted: logoTemplate.text = BootVideoBridge.localPath(currentFile)
    }

    FileDialog {
        id: homeDialog
        title: qsTr("Select Home Template")
        nameFilters: [qsTr("Image files (*.png *.jpg *.jpeg *.bmp)"), qsTr("All files (*)")]
        onAccepted: homeTemplate.text = BootVideoBridge.localPath(currentFile)
    }

    FluFrame {
        Layout.fillWidth: true
        Layout.preferredHeight: 720
        Layout.topMargin: 20
        padding: 10

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Rectangle {
                id: previewPanel
                Layout.fillWidth: true
                Layout.preferredHeight: 500
                Layout.minimumHeight: 360
                color: FluTheme.dark ? "#101010" : "#f6f6f6"
                border.width: 1
                border.color: FluTheme.frameColor
                clip: true

                Image {
                    id: previewFront
                    anchors.fill: parent
                    anchors.margins: 8
                    visible: previewFrontVisible
                    cache: false
                    fillMode: Image.PreserveAspectFit
                    onStatusChanged: {
                        if (status === Image.Ready && source.length > 0) {
                            previewFrontVisible = true
                        }
                    }
                }

                Image {
                    id: previewBack
                    anchors.fill: parent
                    anchors.margins: 8
                    visible: !previewFrontVisible
                    cache: false
                    fillMode: Image.PreserveAspectFit
                    onStatusChanged: {
                        if (status === Image.Ready && source.length > 0) {
                            previewFrontVisible = false
                        }
                    }
                }

                FluText {
                    anchors.centerIn: parent
                    visible: previewSource.length === 0
                    text: qsTr("Camera preview")
                    font: FluTextStyle.Subtitle
                    color: FluTheme.fontSecondaryColor
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.leftMargin: 12
                    anchors.topMargin: 12
                    width: 260
                    height: 116
                    color: FluTheme.dark ? "#202020" : "#ffffff"
                    opacity: 0.9
                    border.width: 1
                    border.color: FluTheme.frameColor

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        FluText { text: qsTr("State: %1").arg(currentState); font: FluTextStyle.Caption }
                        FluText { text: qsTr("Logo Score: %1").arg(logoScore.toFixed(3)); font: FluTextStyle.Caption }
                        FluText { text: qsTr("Home Score: %1").arg(homeScore.toFixed(3)); font: FluTextStyle.Caption }
                        FluText { text: qsTr("Glare: %1%").arg((glareRatio * 100).toFixed(1)); font: FluTextStyle.Caption }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                FluText { text: qsTr("Camera"); font: FluTextStyle.Subtitle }
                RowLayout {
                    Layout.fillWidth: true
                    FluTextBox { id: deviceId; Layout.fillWidth: true; placeholderText: qsTr("Device ID") }
                    FluButton {
                        text: qsTr("Refresh")
                        onClicked: {
                            BootVideoBridge.refreshCameras()
                        }
                    }
                }
                FluText {
                    Layout.fillWidth: true
                    text: probingModes ? qsTr("Detecting camera modes...") : (cameraRows.length > 0 ? qsTr("%1 camera(s) found").arg(cameraRows.length) : qsTr("No camera detected"))
                    font: FluTextStyle.Caption
                    color: FluTheme.fontSecondaryColor
                }
                RowLayout {
                    Layout.fillWidth: true
                    FluComboBox {
                        id: modeCombo
                        Layout.fillWidth: true
                        model: ListModel { id: modeModel }
                        disabled: cameraModes.length === 0
                        onCurrentIndexChanged: {
                            if (cameraModes.length > currentIndex && currentIndex >= 0) {
                                var mode = cameraModes[currentIndex]
                                bootSettings.width = mode.width
                                bootSettings.height = mode.height
                                bootSettings.fps = mode.fps
                                roiW.text = String(mode.width)
                                roiH.text = String(mode.height)
                            }
                        }
                    }
                    FluButton {
                        text: qsTr("Refresh Modes")
                        onClicked: BootVideoBridge.refreshCameraModes(Number(deviceId.text))
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    FluButton { text: qsTr("Open Camera"); Layout.fillWidth: true; enabled: cameraRows.length > 0; onClicked: BootVideoBridge.openCamera(collectSettings()) }
                    FluButton { text: qsTr("Close"); Layout.fillWidth: true; onClicked: BootVideoBridge.closeCamera() }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    FluText { text: qsTr("Result"); font: FluTextStyle.Subtitle }
                    FluText { text: qsTr("Logo: %1").arg(metricText(logoMs)); font: FluTextStyle.Body }
                    FluText { text: qsTr("Home: %1").arg(metricText(homeMs)); font: FluTextStyle.Body }
                    FluText { text: qsTr("Total: %1").arg(metricText(bootMs)); font: FluTextStyle.Body }
                    Item { Layout.fillWidth: true }
                    FluButton {
                        text: qsTr("Open Result Folder")
                        enabled: resultDir.length > 0
                        onClicked: BootVideoBridge.openResultFolder()
                    }
                }
            }
        }
    }

    FluFrame {
        Layout.fillWidth: true
        Layout.topMargin: 12
        padding: 12

        ColumnLayout {
            anchors.fill: parent
            spacing: 10
            FluText { text: qsTr("Analysis Settings"); font: FluTextStyle.Subtitle }
            RowLayout {
                Layout.fillWidth: true
                FluTextBox { id: roiX; Layout.fillWidth: true; placeholderText: "ROI X" }
                FluTextBox { id: roiY; Layout.fillWidth: true; placeholderText: "ROI Y" }
                FluTextBox { id: roiW; Layout.fillWidth: true; placeholderText: qsTr("ROI Width") }
                FluTextBox { id: roiH; Layout.fillWidth: true; placeholderText: qsTr("ROI Height") }
            }
            RowLayout {
                Layout.fillWidth: true
                FluTextBox { id: logoTemplate; Layout.fillWidth: true; placeholderText: qsTr("Logo template path") }
                FluButton { text: qsTr("Browse"); onClicked: logoDialog.open() }
                FluButton { text: qsTr("Capture"); onClicked: BootVideoBridge.captureTemplate("logo", collectSettings()) }
            }
            RowLayout {
                Layout.fillWidth: true
                FluTextBox { id: homeTemplate; Layout.fillWidth: true; placeholderText: qsTr("Home template path") }
                FluButton { text: qsTr("Browse"); onClicked: homeDialog.open() }
                FluButton { text: qsTr("Capture"); onClicked: BootVideoBridge.captureTemplate("home", collectSettings()) }
            }
            RowLayout {
                Layout.fillWidth: true
                FluTextBox { id: logoThreshold; Layout.fillWidth: true; placeholderText: qsTr("Logo threshold") }
                FluTextBox { id: homeThreshold; Layout.fillWidth: true; placeholderText: qsTr("Home threshold") }
                FluTextBox { id: logoFrames; Layout.fillWidth: true; placeholderText: qsTr("Logo frames") }
                FluTextBox { id: homeFrames; Layout.fillWidth: true; placeholderText: qsTr("Home frames") }
            }
            RowLayout {
                Layout.fillWidth: true
                FluTextBox { id: homeStable; Layout.fillWidth: true; placeholderText: qsTr("Home stable seconds") }
                FluTextBox { id: powerDelayInput; Layout.fillWidth: true; placeholderText: qsTr("Power delay seconds") }
                FluTextBox { id: glareSkipInput; Layout.fillWidth: true; placeholderText: qsTr("Glare skip ratio") }
                FluTextBox { id: timeoutInput; Layout.fillWidth: true; placeholderText: qsTr("Timeout seconds") }
                FluTextBox { id: analysisFpsInput; Layout.fillWidth: true; placeholderText: qsTr("Analysis FPS") }
            }
            RowLayout {
                Layout.fillWidth: true
                FluFilledButton {
                    text: qsTr("Start Boot Test")
                    enabled: !BootVideoBridge.isRunning()
                    onClicked: BootVideoBridge.startTest(collectSettings())
                }
                FluButton {
                    text: qsTr("Stop Test")
                    enabled: BootVideoBridge.isRunning()
                    onClicked: BootVideoBridge.stopTest()
                }
                Item { Layout.fillWidth: true }
            }
        }
    }
}
