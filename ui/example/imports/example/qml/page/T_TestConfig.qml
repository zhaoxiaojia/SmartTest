import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluPage {
    title: qsTr("Test")

    Component.onCompleted: {
        TestPageBridge.reloadState()
        TestPageBridge.discoverCases()
    }

    FluSplitLayout{
        id:layout_main
        anchors.fill: parent
        orientation: Qt.Horizontal

        // Left: case library + selected list (vertical split)
        FluSplitLayout{
            SplitView.fillWidth: true
            SplitView.preferredWidth: layout_main.width/3
            SplitView.minimumWidth: 260
            SplitView.fillHeight: true
            orientation: Qt.Vertical

            FluFrame{
                SplitView.fillHeight: true
                padding: 10
                ColumnLayout{
                    anchors.fill: parent
                    spacing: 8
                    FluText{
                        text: qsTr("Test Cases")
                        font: FluTextStyle.Subtitle
                    }
                    FluTextBox{
                        id:txt_filter
                        placeholderText: qsTr("Filter by nodeid...")
                        Layout.fillWidth: true
                    }
                    ListView{
                        id:list_cases
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: TestPageBridge.cases()
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: FluScrollBar{}
                        delegate: Item{
                            id:row_case
                            width: list_cases.width
                            height: 42
                            visible: {
                                if(!txt_filter.text){ return true }
                                return (modelData.nodeid + "").indexOf(txt_filter.text) !== -1
                            }
                            FluControl{
                                id:case_item_ctl
                                anchors.fill: parent
                                onClicked: {
                                    var newChecked = !TestPageBridge.isCaseSelected(modelData.nodeid)
                                    TestPageBridge.setCaseSelected(modelData.nodeid, newChecked)
                                }
                                Rectangle{
                                    anchors.fill: parent
                                    radius: 4
                                    color: case_item_ctl.hovered ? FluTheme.itemHoverColor : "transparent"
                                }
                                RowLayout{
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    spacing: 8
                                    FluCheckBox{
                                        id:chk_case
                                        checked: TestPageBridge.isCaseSelected(modelData.nodeid)
                                        text: ""
                                        clickListener: function(){
                                            TestPageBridge.setCaseSelected(modelData.nodeid, !chk_case.checked)
                                        }
                                    }
                                    ColumnLayout{
                                        Layout.fillWidth: true
                                        spacing: 2
                                        FluText{
                                            text: modelData.name
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                        FluText{
                                            text: modelData.nodeid
                                            font: FluTextStyle.Caption
                                            color: FluTheme.fontSecondaryColor
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            FluFrame{
                SplitView.preferredHeight: 240
                padding: 10
                ColumnLayout{
                    anchors.fill: parent
                    spacing: 8
                    RowLayout{
                        Layout.fillWidth: true
                        FluText{
                            text: qsTr("Selected (%1)").arg(list_selected.count)
                            font: FluTextStyle.Subtitle
                        }
                    }
                    ListView{
                        id:list_selected
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: TestPageBridge.selectedCases()
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: FluScrollBar{}
                        delegate: Item{
                            id:row_sel
                            width: list_selected.width
                            height: 40
                            FluControl{
                                id:sel_ctl
                                anchors.fill: parent
                                Rectangle{
                                    anchors.fill: parent
                                    radius: 4
                                    color: sel_ctl.hovered ? FluTheme.itemHoverColor : "transparent"
                                }
                                RowLayout{
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    spacing: 8
                                    FluText{
                                        text: (index+1) + "."
                                        font: FluTextStyle.Caption
                                        color: FluTheme.fontSecondaryColor
                                    }
                                    FluText{
                                        text: modelData.nodeid
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    FluIconButton{
                                        iconSource: FluentIcons.ChromeClose
                                        iconSize: 12
                                        width: 30
                                        height: 30
                                        onClicked: {
                                            TestPageBridge.setCaseSelected(modelData.nodeid, false)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Middle: per-case parameters (v1 placeholder)
        FluFrame{
            SplitView.fillWidth: true
            SplitView.preferredWidth: layout_main.width/3
            SplitView.minimumWidth: 260
            SplitView.fillHeight: true
            padding: 10
            ColumnLayout{
                anchors.fill: parent
                spacing: 8
                FluText{
                    text: qsTr("Case Parameters")
                    font: FluTextStyle.Subtitle
                }
                Flickable{
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentHeight: col_case_params.implicitHeight
                    ScrollBar.vertical: FluScrollBar{}
                    ColumnLayout{
                        id:col_case_params
                        width: parent.width
                        spacing: 8
                        Repeater{
                            model: TestPageBridge.selectedCases()
                            FluFrame{
                                Layout.fillWidth: true
                                padding: 10
                                ColumnLayout{
                                    width: parent.width
                                    spacing: 6
                                    FluText{
                                        text: modelData.nodeid
                                        font: FluTextStyle.BodyStrong
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    FluText{
                                        text: qsTr("Per-case parameters schema will be generated from Python (factory) in the next step.")
                                        font: FluTextStyle.Caption
                                        color: FluTheme.fontSecondaryColor
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Right: global context + type special params (multi-type)
        FluFrame{
            SplitView.fillWidth: true
            SplitView.preferredWidth: layout_main.width/3
            SplitView.minimumWidth: 260
            SplitView.fillHeight: true
            padding: 10
            Flickable{
                anchors.fill: parent
                clip: true
                contentHeight: col_right.implicitHeight
                ScrollBar.vertical: FluScrollBar{}
                ColumnLayout{
                    id:col_right
                    width: parent.width
                    spacing: 10

                    FluText{
                        text: qsTr("Global (DUT / Environment)")
                        font: FluTextStyle.Subtitle
                    }

                    Repeater{
                        model: TestPageBridge.globalSchema().fields
                        RowLayout{
                            Layout.fillWidth: true
                            spacing: 8
                            FluText{
                                text: modelData.label
                                Layout.preferredWidth: 140
                                elide: Text.ElideRight
                            }
                            FluTextBox{
                                Layout.fillWidth: true
                                text: (TestPageBridge.globalContext()[modelData.key] + "")
                                onEditingFinished: {
                                    TestPageBridge.setGlobalValue(modelData.key, text)
                                }
                            }
                        }
                    }

                    FluDivider{}

                    FluText{
                        text: qsTr("Special Params (by Case Type)")
                        font: FluTextStyle.Subtitle
                    }

                    Repeater{
                        model: TestPageBridge.activeCaseTypes()
                        ColumnLayout{
                            property string caseType: modelData
                            Layout.fillWidth: true
                            spacing: 6
                            FluText{
                                text: caseType
                                font: FluTextStyle.BodyStrong
                            }
                            Repeater{
                                model: TestPageBridge.caseTypeSchema(caseType).fields
                                RowLayout{
                                    Layout.fillWidth: true
                                    spacing: 8
                                    FluText{
                                        text: modelData.label
                                        Layout.preferredWidth: 140
                                        elide: Text.ElideRight
                                    }
                                    FluTextBox{
                                        Layout.fillWidth: true
                                        text: {
                                            var cfg = TestPageBridge.caseTypeConfig(caseType)
                                            if(cfg && cfg[modelData.key] !== undefined){
                                                return cfg[modelData.key] + ""
                                            }
                                            return modelData.default + ""
                                        }
                                        onEditingFinished: {
                                            TestPageBridge.setCaseTypeValue(caseType, modelData.key, text)
                                        }
                                    }
                                }
                            }
                            FluDivider{}
                        }
                    }
                }
            }
        }
    }

    Connections{
        target: TestPageBridge
        function onStateChanged(){
            // force bindings to refresh for function-return models
            list_cases.model = TestPageBridge.cases()
            list_selected.model = TestPageBridge.selectedCases()
        }
        function onCasesChanged(){
            list_cases.model = TestPageBridge.cases()
        }
        function onErrorOccurred(msg){
            showError(msg)
        }
    }
}
