import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluScrollablePage {
    id: page

    launchMode: FluPageType.SingleTask
    animationEnabled: false
    header: Item {}

    property color panelColor: FluTheme.dark ? "#202020" : "#ffffff"
    property color panelBorderColor: FluTheme.dark ? "#363636" : "#e5e7eb"
    property color mutedTextColor: FluTheme.dark ? "#b6b6b6" : "#667085"
    property color strongTextColor: FluTheme.dark ? "#ffffff" : "#101828"
    property string fallbackWallpaper: "qrc:/example/res/image/bg_home_header.png"
    property bool compactLayout: page.width < 760
    property bool wideLayout: page.width > 1180
    property var metricRows: [
        { "label": qsTr("My Jira"), "value": "12", "trend": qsTr("3 waiting for test"), "accent": "#0C66E4" },
        { "label": qsTr("Confluence"), "value": "6", "trend": qsTr("new hot pages"), "accent": "#36B37E" },
        { "label": qsTr("DUT Online"), "value": "1", "trend": qsTr("latest device alive"), "accent": "#6554C0" },
        { "label": qsTr("Failed Runs"), "value": "2", "trend": qsTr("need review"), "accent": "#DE350B" }
    ]
    property var jiraRows: [
        { "key": "IPTV-4821", "title": qsTr("Auto reboot case loses client status after DUT reboot"), "status": qsTr("In Progress"), "level": qsTr("High") },
        { "key": "IPTV-4790", "title": qsTr("Packaged runner cannot locate Android signing resources"), "status": qsTr("Ready"), "level": qsTr("Medium") },
        { "key": "IPTV-4755", "title": qsTr("Report logs should preserve scrollable full output"), "status": qsTr("Review"), "level": qsTr("Low") }
    ]
    property var confluenceRows: [
        { "title": qsTr("S6 U1 platform test checklist"), "meta": qsTr("updated today") },
        { "title": qsTr("ADB privileged app install flow"), "meta": qsTr("14 readers") },
        { "title": qsTr("SmartTest packaged runtime notes"), "meta": qsTr("new comment") }
    ]
    property var internalRows: [
        { "title": qsTr("IPTV daily build is green"), "meta": qsTr("Jenkins signal") },
        { "title": qsTr("Two DUTs need USB reconnection"), "meta": qsTr("lab status") },
        { "title": qsTr("MCP connector health check pending"), "meta": qsTr("intranet") }
    ]

    Component.onCompleted: HomeBridge.refreshWallpaper()

    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: page.compactLayout ? 240 : 300
        Layout.leftMargin: 10
        Layout.rightMargin: 10
        Layout.topMargin: 10

        Image {
            id: wallpaper
            anchors.fill: parent
            source: HomeBridge.wallpaperUrl.length > 0 ? HomeBridge.wallpaperUrl : page.fallbackWallpaper
            sourceSize: Qt.size(1440, 720)
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
        }

        Rectangle {
            anchors.fill: parent
            color: "#000000"
            opacity: FluTheme.dark ? 0.42 : 0.28
        }

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#bf000000" }
                GradientStop { position: 0.68; color: "#33000000" }
                GradientStop { position: 1.0; color: "#05000000" }
            }
        }

        ColumnLayout {
            anchors {
                left: parent.left
                right: parent.right
                bottom: parent.bottom
                margins: 28
            }
            spacing: 14

            RowLayout {
                spacing: 8
                StatusPill { text: qsTr("Intranet first") }
                StatusPill { text: qsTr("MCP ready layout") }
                StatusPill { text: qsTr("Bing daily wallpaper") }
            }

            FluText {
                Layout.fillWidth: true
                text: qsTr("SmartTest Workbench")
                color: "#ffffff"
                font: FluTextStyle.TitleLarge
                wrapMode: Text.Wrap
            }

            FluText {
                Layout.fillWidth: true
                text: HomeBridge.wallpaperCopyright.length > 0 ? HomeBridge.wallpaperCopyright : qsTr("Focused view for tests, issues, knowledge and internal signals.")
                color: "#e8e8e8"
                font: FluTextStyle.Body
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }
    }

    GridLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 10
        Layout.rightMargin: 10
        Layout.topMargin: 14
        columns: page.wideLayout ? 4 : page.width > 520 ? 2 : 1
        columnSpacing: 12
        rowSpacing: 12

        Repeater {
            model: page.metricRows
            delegate: MetricTile {
                Layout.fillWidth: true
                Layout.preferredHeight: page.compactLayout ? 86 : 100
                label: modelData.label
                value: modelData.value
                trend: modelData.trend
                accent: modelData.accent
            }
        }
    }

    GridLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 10
        Layout.rightMargin: 10
        Layout.topMargin: 14
        Layout.bottomMargin: 18
        columns: page.width > 1080 ? 3 : 1
        columnSpacing: 12
        rowSpacing: 12

        DashboardPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: page.width > 1080 ? 390 : 330
            title: qsTr("My Jira")
            subtitle: qsTr("Personal issues from intranet MCP")

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 10
                Repeater {
                    model: page.jiraRows
                    delegate: IssueRow {
                        Layout.fillWidth: true
                        issueKey: modelData.key
                        issueTitle: modelData.title
                        status: modelData.status
                        level: modelData.level
                    }
                }
                Item { Layout.fillHeight: true }
                FluButton {
                    text: qsTr("Open Jira")
                    Layout.alignment: Qt.AlignRight
                    onClicked: ItemsOriginal.navigateWithAuth({
                        "title": "Jira",
                        "url": "qrc:/example/qml/page/T_Jira.qml"
                    })
                }
            }
        }

        DashboardPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: page.width > 1080 ? 390 : 310
            title: qsTr("Confluence Hotspots")
            subtitle: qsTr("Pages likely useful for today's work")

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 8
                Repeater {
                    model: page.confluenceRows
                    delegate: LinkRow {
                        Layout.fillWidth: true
                        title: modelData.title
                        meta: modelData.meta
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: page.panelBorderColor
                }
                QuickAction {
                    Layout.fillWidth: true
                    iconSource: FluentIcons.Search
                    title: qsTr("Search knowledge base")
                    meta: qsTr("Reserved for Confluence MCP")
                }
                Item { Layout.fillHeight: true }
            }
        }

        DashboardPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: page.width > 1080 ? 390 : 310
            title: qsTr("Internal Signals")
            subtitle: qsTr("Company and lab information")

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 8
                Repeater {
                    model: page.internalRows
                    delegate: LinkRow {
                        Layout.fillWidth: true
                        title: modelData.title
                        meta: modelData.meta
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: page.panelBorderColor
                }
                QuickAction {
                    Layout.fillWidth: true
                    iconSource: FluentIcons.PlaySolid
                    title: qsTr("Continue test workflow")
                    meta: qsTr("Open Test, Run or Report from the sidebar")
                }
                Item { Layout.fillHeight: true }
            }
        }
    }

    component StatusPill: Rectangle {
        property alias text: label.text

        height: 28
        radius: 14
        color: "#33000000"
        border.width: 1
        border.color: "#55ffffff"

        implicitWidth: label.implicitWidth + 22

        FluText {
            id: label
            anchors.centerIn: parent
            color: "#ffffff"
            font: FluTextStyle.Caption
        }
    }

    component MetricTile: Rectangle {
        property string label
        property string value
        property string trend
        property color accent

        radius: 8
        color: page.panelColor
        border.width: 1
        border.color: page.panelBorderColor

        Rectangle {
            width: 4
            radius: 2
            color: accent
            anchors {
                left: parent.left
                top: parent.top
                bottom: parent.bottom
                margins: 14
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 28
            anchors.rightMargin: 18
            anchors.topMargin: 14
            anchors.bottomMargin: 14
            spacing: 4

            FluText {
                text: label
                color: page.mutedTextColor
                font: FluTextStyle.Caption
            }
            FluText {
                text: value
                color: page.strongTextColor
                font.pixelSize: page.compactLayout ? 24 : 30
                font.family: FluTextStyle.family
                font.weight: Font.DemiBold
            }
            FluText {
                Layout.fillWidth: true
                text: trend
                color: page.mutedTextColor
                font: FluTextStyle.Caption
                elide: Text.ElideRight
            }
        }
    }

    component DashboardPanel: Rectangle {
        property string title
        property string subtitle
        default property alias content: body.data

        radius: 8
        color: page.panelColor
        border.width: 1
        border.color: page.panelBorderColor

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 18
                Layout.rightMargin: 18
                Layout.topMargin: 16
                Layout.bottomMargin: 12
                spacing: 2
                FluText {
                    Layout.fillWidth: true
                    text: title
                    color: page.strongTextColor
                    font: FluTextStyle.Subtitle
                    elide: Text.ElideRight
                }
                FluText {
                    Layout.fillWidth: true
                    text: subtitle
                    color: page.mutedTextColor
                    font: FluTextStyle.Caption
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: page.panelBorderColor
            }

            Item {
                id: body
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }
    }

    component IssueRow: Rectangle {
        property string issueKey
        property string issueTitle
        property string status
        property string level

        radius: 6
        color: FluTheme.itemNormalColor
        border.width: 1
        border.color: page.panelBorderColor
        Layout.preferredHeight: page.compactLayout ? 66 : 72

        RowLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Rectangle {
                Layout.preferredWidth: 6
                Layout.fillHeight: true
                radius: 3
                color: level === qsTr("High") ? "#DE350B" : level === qsTr("Medium") ? "#FFAB00" : "#36B37E"
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                FluText {
                    text: issueKey + "  " + status
                    color: page.mutedTextColor
                    font: FluTextStyle.Caption
                    elide: Text.ElideRight
                }
                FluText {
                    Layout.fillWidth: true
                    text: issueTitle
                    color: page.strongTextColor
                    font: FluTextStyle.Body
                    maximumLineCount: 2
                    wrapMode: Text.Wrap
                    elide: Text.ElideRight
                }
            }
        }
    }

    component LinkRow: Rectangle {
        property string title
        property string meta

        Layout.preferredHeight: page.compactLayout ? 50 : 56
        radius: 6
        color: rowMouse.containsMouse ? FluTheme.itemHoverColor : "transparent"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 10

            FluIcon {
                Layout.preferredWidth: 18
                Layout.preferredHeight: 18
                iconSource: FluentIcons.Page
                iconSize: 15
                color: page.mutedTextColor
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                FluText {
                    Layout.fillWidth: true
                    text: title
                    color: page.strongTextColor
                    font: FluTextStyle.Body
                    elide: Text.ElideRight
                }
                FluText {
                    Layout.fillWidth: true
                    text: meta
                    color: page.mutedTextColor
                    font: FluTextStyle.Caption
                    elide: Text.ElideRight
                }
            }
        }

        MouseArea {
            id: rowMouse
            anchors.fill: parent
            hoverEnabled: true
        }
    }

    component QuickAction: Rectangle {
        id: quickAction

        property int iconSource
        property string title
        property string meta

        Layout.preferredHeight: 64
        radius: 6
        color: FluTheme.itemNormalColor
        border.width: 1
        border.color: page.panelBorderColor

        RowLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            FluIcon {
                Layout.preferredWidth: 20
                Layout.preferredHeight: 20
                iconSource: quickAction.iconSource
                iconSize: 18
                color: FluTheme.primaryColor
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                FluText {
                    Layout.fillWidth: true
                    text: title
                    color: page.strongTextColor
                    font: FluTextStyle.BodyStrong
                    elide: Text.ElideRight
                }
                FluText {
                    Layout.fillWidth: true
                    text: meta
                    color: page.mutedTextColor
                    font: FluTextStyle.Caption
                    elide: Text.ElideRight
                }
            }
        }
    }
}
