import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import QtWebEngine 1.10
import FluentUI 1.0

FluPage {
    id: page
    title: qsTr("AI Assistant")
    launchMode: FluPageType.SingleInstance

    property url aiUrl: "https://aichat.amlogic.com"
    property bool loading: web_view.loading
    property string statusText: ""
    property color pageBg: FluTheme.dark ? "#202020" : "#ffffff"
    property color toolbarBg: FluTheme.dark ? "#2b2b2b" : "#f7f7f7"
    property color borderColor: FluTheme.dark ? "#3c3c3c" : "#e5e7eb"
    property color primaryText: FluTheme.dark ? "#f3f4f6" : "#111827"
    property color secondaryText: FluTheme.dark ? "#a1a1aa" : "#6b7280"

    function reloadAi(){
        statusText = ""
        web_view.reload()
    }

    function openExternal(){
        Qt.openUrlExternally(aiUrl)
    }

    WebEngineProfile {
        id: ai_web_profile
        storageName: "smarttest_ai_web"
        offTheRecord: false
        httpCacheType: WebEngineProfile.DiskHttpCache
        persistentCookiesPolicy: WebEngineProfile.ForcePersistentCookies
    }

    Rectangle {
        anchors.fill: parent
        color: pageBg

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                color: toolbarBg
                border.width: 1
                border.color: borderColor

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8

                    Image {
                        Layout.preferredWidth: 20
                        Layout.preferredHeight: 20
                        source: "qrc:/example/res/svg/deepseek-logo-icon.svg"
                        fillMode: Image.PreserveAspectFit
                    }

                    FluText {
                        text: qsTr("DeepSeek")
                        color: primaryText
                        font: FluTextStyle.BodyStrong
                    }

                    FluText {
                        Layout.fillWidth: true
                        text: loading ? qsTr("Loading...") : statusText
                        color: secondaryText
                        elide: Text.ElideRight
                    }

                    FluIconButton {
                        iconSource: FluentIcons.Refresh
                        iconSize: 16
                        text: qsTr("Reload")
                        onClicked: reloadAi()
                    }

                    FluIconButton {
                        iconSource: FluentIcons.OpenInNewWindow
                        iconSize: 16
                        text: qsTr("Open in browser")
                        onClicked: openExternal()
                    }
                }
            }

            WebEngineView {
                id: web_view
                Layout.fillWidth: true
                Layout.fillHeight: true
                profile: ai_web_profile
                url: page.aiUrl

                onLoadingChanged: function(loadRequest) {
                    if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                        statusText = qsTr("Ready")
                    } else if (loadRequest.status === WebEngineView.LoadFailedStatus) {
                        statusText = qsTr("Failed to load DeepSeek. Check intranet/VPN.")
                    } else if (loadRequest.status === WebEngineView.LoadStartedStatus) {
                        statusText = qsTr("Loading...")
                    }
                }
            }
        }
    }
}
