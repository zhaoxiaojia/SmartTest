import QtQuick 2.15
import QtWebEngine 1.10

Item {
    property url previewUrl: ""
    signal loadStatusChanged(string status)

    WebEngineProfile {
        id: dailyReportProfile
        storageName: "smarttest_daily_report_preview"
        offTheRecord: false
        httpCacheType: WebEngineProfile.DiskHttpCache
    }

    WebEngineView {
        anchors.fill: parent
        profile: dailyReportProfile
        url: parent.previewUrl
        onLoadingChanged: function(loadRequest) {
            if (loadRequest.status === WebEngineView.LoadStartedStatus) parent.loadStatusChanged(qsTr("Loading preview..."))
            else if (loadRequest.status === WebEngineView.LoadSucceededStatus) parent.loadStatusChanged(qsTr("Preview ready"))
            else if (loadRequest.status === WebEngineView.LoadFailedStatus) parent.loadStatusChanged(qsTr("Failed to load preview."))
        }
    }
}
