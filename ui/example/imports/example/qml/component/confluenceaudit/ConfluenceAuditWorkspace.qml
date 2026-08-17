import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0
import "../../state"

Item {
    id: root
    readonly property var view: ConfluenceAuditBridge.viewState
    readonly property bool catalogBusy: root.view.catalogStatus === "first_loading"
                                        || root.view.catalogStatus === "refreshing"
    readonly property bool auditBusy: root.view.state === "discovering"
                                      || root.view.state === "reviewing"

    Loader {
        id: collectionStateLoader
        active: AuthBridge.authenticated === true
                && (AuthBridge.pageStateAccount || "").length > 0
        sourceComponent: Component {
            ConfluenceAuditWorkspaceState { account: AuthBridge.pageStateAccount }
        }
        onLoaded: ConfluenceAuditBridge.restoreCollectionState({
            hasAppliedFilters: item.hasAppliedFilters,
            selectedProductLineKeys: item.selectedProductLineKeys,
            years: item.years,
            supportModes: item.supportModes,
            projectStatuses: item.projectStatuses
        })
    }

    FluWindowResultLauncher {
        id: loginLauncher
        objectName: "confluenceAuditLoginLauncher"
        path: "/login"
    }

    Connections {
        target: AuthBridge
        ignoreUnknownSignals: true
        function onRuntimeCredentialSupplyRequired() {
            loginLauncher.launch({
                username: AuthBridge.username,
                credentialSupply: AuthBridge.authenticated
            })
        }
    }

    Connections {
        target: ConfluenceAuditBridge
        function onCollectionFilterApplied(criteria) {
            if (!collectionStateLoader.item)
                return
            collectionStateLoader.item.selectedProductLineKeys = criteria.selectedProductLineKeys
            collectionStateLoader.item.years = criteria.years
            collectionStateLoader.item.supportModes = criteria.supportModes
            collectionStateLoader.item.projectStatuses = criteria.projectStatuses
            collectionStateLoader.item.hasAppliedFilters = true
            collectionStateLoader.item.sync()
        }
    }

    function shortDate(value) {
        return value && value.length >= 10 ? value.substring(0, 10) : ""
    }

    function pickerDate(value) {
        const parts = String(value).split("-")
        return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
    }

    function statusColor(status) {
        if (status === "invalid_format")
            return FluTheme.dark ? "#FF99A4" : "#D13438"
        if (status === "not_updated")
            return FluTheme.dark ? "#FCE100" : "#986F0B"
        if (status === "updated")
            return FluTheme.dark ? "#7EE787" : "#107C10"
        return FluTheme.fontSecondaryColor
    }

    function containsValue(values, value) {
        if (!values)
            return false
        for (var i = 0; i < values.length; ++i) {
            if (String(values[i]) === String(value))
                return true
        }
        return false
    }

    function selectedValuesText(values) {
        return values && values.length ? values.join(", ") : qsTr("Any")
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        FluFrame {
            id: collectionFrame
            Layout.fillWidth: true
            Layout.preferredHeight: collectionColumn.implicitHeight + 20
            padding: 10

            ColumnLayout {
                id: collectionColumn
                anchors.fill: parent
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    FluText {
                        text: qsTr("Project collection")
                        font: FluTextStyle.Subtitle
                    }
                    FluText {
                        text: qsTr("Source") + ":"
                        color: FluTheme.fontSecondaryColor
                    }
                    FluText {
                        objectName: "confluenceAuditSourceLabel"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: root.view.sourceLabel || ""
                        elide: Text.ElideMiddle
                        color: FluTheme.fontSecondaryColor
                    }
                    FluButton {
                        objectName: "confluenceAuditRefreshCollectionButton"
                        text: qsTr("Refresh filter options")
                        disabled: root.catalogBusy || root.auditBusy
                        onClicked: ConfluenceAuditBridge.refreshCollection()
                    }
                    FluProgressRing {
                        objectName: "confluenceAuditCatalogProgressRing"
                        visible: root.catalogBusy
                        implicitWidth: 18
                        implicitHeight: 18
                    }
                    FluText {
                        text: root.view.catalogStatusText || ""
                        color: FluTheme.fontSecondaryColor
                        font: FluTextStyle.Caption
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    rowSpacing: 8
                    columnSpacing: 8
                    columns: width < 800 ? 1 : 4

                    ColumnLayout {
                        objectName: "confluenceAuditProductLineFilter"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 120
                        Layout.preferredWidth: 0
                        FluText {
                            text: qsTr("Product lines") + " ("
                                  + (root.view.productLines || []).length
                                  + " " + qsTr("available") + ")"
                            font: FluTextStyle.Caption
                        }
                        FluDropDownButton {
                            objectName: "confluenceAuditProductLineDropDown"
                            Layout.fillWidth: true
                            text: root.selectedValuesText(
                                      (root.view.productLines || []).filter(function(item) {
                                          return root.containsValue(root.view.selectedProductLineKeys,
                                                                    item.key)
                                      }).map(function(item) { return item.displayName }))
                            Repeater {
                                model: root.view.productLines || []
                                FluMenuItem { /* persistence-opt-out: owner:ConfluenceAuditBridge */
                                    required property var modelData
                                    text: modelData.displayName
                                    checkable: true
                                    checked: root.containsValue(root.view.selectedProductLineKeys,
                                                                 modelData.key)
                                    onTriggered: ConfluenceAuditBridge.toggleProductLine(modelData.key)
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        objectName: "confluenceAuditYearFilter"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 120
                        Layout.preferredWidth: 0
                        FluText {
                            text: qsTr("Years") + " ("
                                  + (root.view.availableFilterValues.years || []).length
                                  + " " + qsTr("available") + ")"
                            font: FluTextStyle.Caption
                        }
                        FluDropDownButton {
                            objectName: "confluenceAuditYearDropDown"
                            Layout.fillWidth: true
                            text: root.selectedValuesText(root.view.filter.years)
                            Repeater {
                                model: root.view.availableFilterValues.years || []
                                FluMenuItem { /* persistence-opt-out: owner:ConfluenceAuditBridge */
                                        required property var modelData
                                        objectName: "confluenceAuditYearOption_" + String(modelData)
                                    text: String(modelData)
                                    checkable: true
                                    checked: root.containsValue(root.view.filter.years, modelData)
                                    onTriggered: ConfluenceAuditBridge.toggleFilterValue(
                                                     "years", modelData)
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        objectName: "confluenceAuditSupportModeFilter"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 120
                        Layout.preferredWidth: 0
                        FluText {
                            text: qsTr("Support modes") + " ("
                                  + (root.view.availableFilterValues.supportModes || []).length
                                  + " " + qsTr("available") + ")"
                            font: FluTextStyle.Caption
                        }
                        FluDropDownButton {
                            objectName: "confluenceAuditSupportModeDropDown"
                            Layout.fillWidth: true
                            text: root.selectedValuesText(root.view.filter.supportModes)
                            Repeater {
                                model: root.view.availableFilterValues.supportModes || []
                                FluMenuItem { /* persistence-opt-out: owner:ConfluenceAuditBridge */
                                        required property var modelData
                                        objectName: "confluenceAuditSupportModeOption_" + String(modelData)
                                    text: String(modelData)
                                    checkable: true
                                    checked: root.containsValue(root.view.filter.supportModes, modelData)
                                    onTriggered: ConfluenceAuditBridge.toggleFilterValue(
                                                     "supportModes", modelData)
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        objectName: "confluenceAuditProjectStatusFilter"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 120
                        Layout.preferredWidth: 0
                        FluText {
                            text: qsTr("Project statuses") + " ("
                                  + (root.view.availableFilterValues.projectStatuses || []).length
                                  + " " + qsTr("available") + ")"
                            font: FluTextStyle.Caption
                        }
                        FluDropDownButton {
                            objectName: "confluenceAuditProjectStatusDropDown"
                            Layout.fillWidth: true
                            text: root.selectedValuesText(root.view.filter.projectStatuses)
                            Repeater {
                                model: root.view.availableFilterValues.projectStatuses || []
                                FluMenuItem { /* persistence-opt-out: owner:ConfluenceAuditBridge */
                                        required property var modelData
                                        objectName: "confluenceAuditProjectStatusOption_" + String(modelData)
                                    text: String(modelData)
                                    checkable: true
                                    checked: root.containsValue(root.view.filter.projectStatuses, modelData)
                                    onTriggered: ConfluenceAuditBridge.toggleFilterValue(
                                                     "projectStatuses", modelData)
                                }
                            }
                        }
                    }
                    FluFilledButton {
                        objectName: "confluenceAuditApplyFilterButton"
                        text: qsTr("Apply filters")
                        disabled: !root.view.canStart || root.view.filterApplying === true
                        onClicked: ConfluenceAuditBridge.applyCollectionFilter()
                    }
                    FluProgressRing {
                        objectName: "confluenceAuditApplyFilterProgress"
                        visible: root.view.filterApplying === true
                        Layout.preferredWidth: 24
                        Layout.preferredHeight: 24
                    }
                }

                Flickable {
                    id: candidateSectionList
                    objectName: "confluenceAuditProductLineProjectChecklist"
                    visible: (root.view.candidateSections || []).length > 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(
                        candidateSectionColumn.implicitHeight,
                        Math.max(240, Math.min(520, root.height * 0.55)))
                    clip: true
                    contentWidth: width
                    contentHeight: candidateSectionColumn.implicitHeight
                    flickableDirection: Flickable.VerticalFlick
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: FluScrollBar {
                        interactive: true
                        policy: ScrollBar.AsNeeded
                    }

                    ColumnLayout {
                        id: candidateSectionColumn
                        width: candidateSectionList.width
                        spacing: 8

                        Repeater {
                            model: root.view.candidateSections || []
                            ColumnLayout {
                                required property var modelData
                                property var sectionData: modelData
                                Layout.fillWidth: true
                                spacing: 4
                                RowLayout {
                                    Layout.fillWidth: true
                                    FluText {
                                        Layout.fillWidth: true
                                        text: sectionData.displayName
                                        font: FluTextStyle.BodyStrong
                                    }
                                    FluButton {
                                        text: qsTr("Select all")
                                        disabled: !(sectionData.projects || []).length
                                        onClicked: ConfluenceAuditBridge.selectAllProjectsForLine(sectionData.key)
                                    }
                                    FluButton {
                                        text: qsTr("Clear selection")
                                        onClicked: ConfluenceAuditBridge.clearSelectedProjectsForLine(sectionData.key)
                                    }
                                }
                                GridLayout {
                                    id: candidateSectionGrid
                                    Layout.fillWidth: true
                                    columns: 3
                                    columnSpacing: 12
                                    rowSpacing: 4
                                    Repeater {
                                        model: sectionData.projects || []
                                        RowLayout {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            Layout.preferredWidth: 0
                                            FluCheckBox { /* persistence-opt-out: owner:ConfluenceAuditBridge */
                                                checked: root.containsValue(root.view.selectedProjectIds,
                                                                             modelData.projectIdentity)
                                                onClicked: ConfluenceAuditBridge.toggleProject(modelData.projectIdentity)
                                            }
                                            FluText {
                                                Layout.preferredWidth: 110
                                                text: (modelData.matchingYears || [modelData.year]).join(", ")
                                            }
                                            FluText {
                                                Layout.fillWidth: true
                                                text: modelData.displayName || modelData.name
                                                wrapMode: Text.WrapAnywhere
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    visible: !(root.view.candidateSections || []).length
                    Layout.fillWidth: true
                    FluText {
                        text: qsTr("Candidate projects") + ": "
                              + (root.view.collectionSummary.candidateCount || 0)
                    }
                    FluButton {
                        objectName: "confluenceAuditSelectAllProjectsButton"
                        text: qsTr("Select all")
                        disabled: !(root.view.candidateProjects || []).length
                        onClicked: ConfluenceAuditBridge.selectAllProjects()
                    }
                    FluButton {
                        objectName: "confluenceAuditClearSelectedProjectsButton"
                        text: qsTr("Clear selection")
                        disabled: !(root.view.selectedProjectIds || []).length
                        onClicked: ConfluenceAuditBridge.clearSelectedProjects()
                    }
                    FluText {
                        Layout.fillWidth: true
                        text: qsTr("Selected") + ": "
                              + (root.view.selectedProjectIds || []).length
                        color: FluTheme.fontSecondaryColor
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    FluFilledButton {
                        objectName: "confluenceAuditEnableWeeklyPlanButton"
                        text: qsTr("Enable weekly plan")
                        disabled: !root.view.canStart
                                  || !(root.view.collectionSummary.candidateCount || 0)
                                  || !(root.view.selectedProjectIds || []).length
                        onClicked: ConfluenceAuditBridge.enableWeeklyPlan()
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.preferredWidth: 32 }
                    FluText {
                        Layout.preferredWidth: 110
                        Layout.minimumWidth: 86
                        text: qsTr("Year")
                        font: FluTextStyle.Caption
                    }
                    FluText {
                        Layout.fillWidth: true
                        text: qsTr("Project name")
                        font: FluTextStyle.Caption
                    }
                }

                Flickable {
                    id: candidateList
                    objectName: "confluenceAuditProjectChecklist"
                    visible: !(root.view.candidateSections || []).length
                    Layout.fillWidth: true
                    readonly property int candidateColumnCount: width < 800 ? 1 : (width < 1200 ? 2 : 3)
                    readonly property int candidateTotalRowCount: Math.ceil(
                        (root.view.candidateProjects || []).length
                        / candidateColumnCount)
                    readonly property int candidateVisibleRowCount: Math.min(
                        6, candidateTotalRowCount)
                    readonly property real candidateViewportHeight:
                        visibleHeight(candidateGrid.implicitHeight)
                    function visibleHeight(layoutRevision) {
                        let bottom = 0
                        const visibleItems = Math.min(
                            (root.view.candidateProjects || []).length,
                            candidateVisibleRowCount * candidateColumnCount)
                        for (let index = 0; index < visibleItems; ++index) {
                            const item = candidateRepeater.itemAt(index)
                            if (item)
                                bottom = Math.max(bottom, item.y + item.height)
                        }
                        return bottom
                    }
                    Layout.preferredHeight: candidateViewportHeight
                    clip: true
                    contentWidth: width
                    contentHeight: candidateGrid.implicitHeight
                    flickableDirection: Flickable.VerticalFlick
                    GridLayout {
                        id: candidateGrid
                        width: candidateList.width
                        columns: candidateList.candidateColumnCount
                        columnSpacing: 12
                        rowSpacing: 4
                        Repeater {
                            id: candidateRepeater
                            model: root.view.candidateProjects || []
                            Item {
                                required property var modelData
                                objectName: "confluenceAuditProjectRow_" + modelData.projectIdentity
                                Layout.fillWidth: true
                                Layout.preferredWidth: 0
                                Layout.preferredHeight: Math.max(
                                    42, candidateName.contentHeight + 16)
                                FluCheckBox { /* persistence-opt-out: owner:ConfluenceAuditBridge */
                                    id: candidateCheck
                                    objectName: "confluenceAuditProjectOption_" + modelData.projectIdentity
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    text: ""
                                    checked: root.containsValue(root.view.selectedProjectIds,
                                                                modelData.projectIdentity)
                                    onClicked: ConfluenceAuditBridge.toggleProject(modelData.projectIdentity)
                                }
                                FluText {
                                    id: candidateYears
                                    anchors.left: candidateCheck.right
                                    anchors.leftMargin: 6
                                    anchors.top: parent.top
                                    width: Math.min(110, Math.max(86, parent.width * 0.24))
                                    text: (modelData.matchingYears
                                           || [modelData.year]).join(", ")
                                    wrapMode: Text.Wrap
                                    color: FluTheme.fontSecondaryColor
                                }
                                FluText {
                                    id: candidateName
                                    objectName: "confluenceAuditProjectName_" + modelData.projectIdentity
                                    anchors.left: candidateYears.right
                                    anchors.leftMargin: 6
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    text: modelData.displayName || modelData.name
                                    wrapMode: Text.WrapAnywhere
                                }
                            }
                        }
                    }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: root.width < 800 ? 2 : 4
            FluText {
                text: qsTr("Start date")
            }
            FluDatePicker { // persistence-opt-out: owner:ConfluenceAuditBridge
                objectName: "confluenceAuditStartDatePicker"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: 220
                current: root.pickerDate(root.view.manualAuditPeriod.startDate)
                disabled: root.auditBusy
                onAccepted: ConfluenceAuditBridge.setManualAuditStartDate(
                    Qt.formatDate(current, "yyyy-MM-dd"))
            }
            FluText {
                text: qsTr("End date")
            }
            FluDatePicker { // persistence-opt-out: owner:ConfluenceAuditBridge
                objectName: "confluenceAuditEndDatePicker"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: 220
                current: root.pickerDate(root.view.manualAuditPeriod.endDate)
                disabled: root.auditBusy
                onAccepted: ConfluenceAuditBridge.setManualAuditEndDate(
                    Qt.formatDate(current, "yyyy-MM-dd"))
            }
        }
        RowLayout {
            Layout.fillWidth: true
            FluFilledButton {
                objectName: "startConfluenceAuditButton"
                text: qsTr("Audit All Projects Now")
                disabled: !root.view.canStart
                onClicked: ConfluenceAuditBridge.startAudit()
            }
            FluButton {
                objectName: "exportConfluenceAuditExcelButton"
                text: qsTr("Export Excel")
                disabled: !root.view.canExport
                onClicked: ConfluenceAuditBridge.exportExcel()
            }
            FluButton {
                objectName: "openConfluenceAuditReportDirectoryButton"
                text: qsTr("Open report directory")
                visible: !!root.view.exportPath
                onClicked: ConfluenceAuditBridge.openReportDirectory()
            }
            FluText {
                Layout.fillWidth: true
                text: root.view.statusText
                wrapMode: Text.WordWrap
            }
        }
        FluText {
            text: qsTr("Audit period") + ": "
                  + root.shortDate(root.view.period.start) + " — "
                  + root.shortDate(root.view.period.displayEnd)
            color: FluTheme.fontSecondaryColor
        }
        FluText {
            text: qsTr("Reviewed") + ": " + (root.view.summary.reviewedCount || 0)
                  + "  " + qsTr("Follow-up") + ": " + (root.view.summary.followUpCount || 0)
        }
        FluProgressBar {
            Layout.fillWidth: true
            visible: root.auditBusy
            indeterminate: !(root.view.progress.total > 0)
            from: 0
            to: Math.max(1, root.view.progress.total || 1)
            value: root.view.progress.processed || 0
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            ListView {
                id: projectList
                objectName: "confluenceAuditProjectList"
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: root.view.projects
                delegate: Rectangle {
                    required property var modelData
                    width: projectList.width
                    height: projectColumn.implicitHeight + 18
                    radius: 6
                    color: root.view.selectedProject === modelData.projectId
                           ? (FluTheme.dark ? "#243849" : "#EAF6FF")
                           : "transparent"
                    border.color: FluTheme.frameColor

                    ColumnLayout {
                        id: projectColumn
                        anchors.fill: parent
                        anchors.margins: 9
                        spacing: 3

                        FluText {
                            objectName: "confluenceAuditProjectName"
                            Layout.fillWidth: true
                            text: modelData.name
                            wrapMode: Text.WrapAnywhere
                            font: FluTextStyle.BodyStrong
                        }
                        FluText {
                            objectName: "confluenceAuditProjectStatus"
                            text: modelData.status
                            color: root.statusColor(modelData.status)
                            font: FluTextStyle.Caption
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: ConfluenceAuditBridge.selectProject(modelData.projectId)
                    }
                }
            }
            ListView {
                id: findingList
                objectName: "confluenceAuditFindingList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: root.view.findings
                delegate: FluFrame {
                    required property var modelData
                    width: findingList.width
                    height: findingColumn.implicitHeight + 16
                    ColumnLayout {
                        id: findingColumn
                        anchors.fill: parent
                        anchors.margins: 8
                        FluText { text: modelData.pageTitle + " · " + modelData.status; font: FluTextStyle.BodyStrong }
                        FluText {
                            Layout.fillWidth: true
                            text: modelData.ruleId
                            wrapMode: Text.WordWrap
                            color: FluTheme.fontSecondaryColor
                        }
                        FluText {
                            Layout.fillWidth: true
                            text: qsTr("Reason") + ": " + modelData.reason
                            wrapMode: Text.WordWrap
                        }
                        FluText {
                            objectName: "confluenceAuditExplanation"
                            Layout.fillWidth: true
                            visible: (modelData.explanation || "").length > 0
                            text: modelData.explanation || ""
                            wrapMode: Text.WordWrap
                            color: FluTheme.fontSecondaryColor
                        }
                        FluButton {
                            text: qsTr("Open Confluence")
                            visible: modelData.url.length > 0
                            onClicked: Qt.openUrlExternally(modelData.url)
                        }
                    }
                }
            }
        }
        FluText {
            visible: (root.view.summary.reviewedCount || 0) > 0
                     && (root.view.summary.followUpCount || 0) === 0
            text: qsTr("No projects require follow-up.")
            color: FluTheme.fontSecondaryColor
        }
    }
}
