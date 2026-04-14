import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluPage {
    title: qsTr("Test")

    property var selectedModel: []
    property var selectedOrderNodeids: []
    ListModel{
        id: caseListModel
    }

    function refreshCasesModel(){
        var rawCases = TestPageBridge.cases()
        var keepChecked = {}
        for(var i = 0; i < caseListModel.count; i++){
            var current = caseListModel.get(i)
            keepChecked[current.nodeid] = current.checked === true
        }
        caseListModel.clear()
        for(var j = 0; j < rawCases.length; j++){
            var row = rawCases[j]
            caseListModel.append({
                nodeid: row.nodeid,
                name: row.name,
                checked: keepChecked[row.nodeid] === true
            })
        }
        rebuildSelectedModel()
    }

    function rebuildSelectedModel(){
        var checkedMap = {}
        for(var i = 0; i < caseListModel.count; i++){
            var current = caseListModel.get(i)
            if(current.checked === true){
                checkedMap[current.nodeid] = {
                    nodeid: current.nodeid,
                    name: current.name
                }
            }
        }
        var nextOrder = []
        for(var j = 0; j < selectedOrderNodeids.length; j++){
            var orderedNodeid = selectedOrderNodeids[j]
            if(checkedMap[orderedNodeid] !== undefined){
                nextOrder.push(orderedNodeid)
                delete checkedMap[orderedNodeid]
            }
        }
        for(var k = 0; k < caseListModel.count; k++){
            var row = caseListModel.get(k)
            if(row.checked === true && checkedMap[row.nodeid] !== undefined){
                nextOrder.push(row.nodeid)
                delete checkedMap[row.nodeid]
            }
        }
        selectedOrderNodeids = nextOrder

        var rows = []
        for(var m = 0; m < selectedOrderNodeids.length; m++){
            var nodeid = selectedOrderNodeids[m]
            for(var n = 0; n < caseListModel.count; n++){
                var item = caseListModel.get(n)
                if(item.nodeid === nodeid && item.checked === true){
                    rows.push({
                        nodeid: item.nodeid,
                        name: item.name
                    })
                    break
                }
            }
        }
        selectedModel = rows
    }

    function setCaseCheckedAt(index, checked, reason){
        if(index < 0 || index >= caseListModel.count){
            return
        }
        var current = caseListModel.get(index)
        caseListModel.setProperty(index, "checked", checked === true)
        rebuildSelectedModel()
    }

    function setCaseCheckedByNodeid(nodeid, checked, reason){
        for(var i = 0; i < caseListModel.count; i++){
            var current = caseListModel.get(i)
            if(current.nodeid === nodeid){
                setCaseCheckedAt(i, checked, reason)
                return
            }
        }
    }

    function moveSelectedLocal(fromIndex, toIndex){
        if(fromIndex < 0 || toIndex < 0){
            return
        }
        if(fromIndex >= selectedOrderNodeids.length || toIndex >= selectedOrderNodeids.length){
            return
        }
        if(fromIndex === toIndex){
            return
        }
        var nextOrder = selectedOrderNodeids.slice(0)
        var moved = nextOrder.splice(fromIndex, 1)[0]
        nextOrder.splice(toIndex, 0, moved)
        selectedOrderNodeids = nextOrder
        rebuildSelectedModel()
    }

    Connections{
        target: TestPageBridge
        function onCasesChanged(){
            refreshCasesModel()
        }
        function onStateChanged(){
        }
        function onErrorOccurred(msg){
            showError(msg)
        }
    }

    Component.onCompleted: {
        TestPageBridge.discoverCases()
        refreshCasesModel()
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
                    FluGroupBox{
                        title: ""
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        padding: 8
                        Flickable{
                            anchors.fill: parent
                            clip: true
                            contentHeight: col_cases.implicitHeight
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: FluScrollBar{}
                            ColumnLayout{
                                id:col_cases
                                width: parent.width
                                spacing: 6
                                Repeater{
                                    model: caseListModel
                                    Item{
                                        width: col_cases.width
                                        height: visible ? 42 : 0
                                        visible: {
                                            if(!txt_filter.text){
                                                return true
                                            }
                                            return (model.nodeid + "").indexOf(txt_filter.text) !== -1
                                        }
                                        RowLayout{
                                            anchors.fill: parent
                                            spacing: 8
                                            FluCheckBox{
                                                id: case_checkbox
                                                Layout.alignment: Qt.AlignTop
                                                checked: model.checked === true
                                                text: ""
                                                clickListener: function(){
                                                    var newChecked = !(model.checked === true)
                                                    setCaseCheckedAt(index, newChecked, "checkbox")
                                                }
                                            }
                                            Item{
                                                Layout.fillWidth: true
                                                Layout.fillHeight: true
                                                ColumnLayout{
                                                    anchors.fill: parent
                                                    spacing: 2
                                                    FluText{
                                                        text: model.name
                                                        elide: Text.ElideRight
                                                        Layout.fillWidth: true
                                                    }
                                                    FluText{
                                                        text: model.nodeid
                                                        font: FluTextStyle.Caption
                                                        color: FluTheme.fontSecondaryColor
                                                        elide: Text.ElideRight
                                                        Layout.fillWidth: true
                                                    }
                                                }
                                                MouseArea{
                                                    anchors.fill: parent
                                                    acceptedButtons: Qt.LeftButton
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        var newChecked = !(model.checked === true)
                                                        setCaseCheckedAt(index, newChecked, "text")
                                                    }
                                                }
                                            }
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
                        model: selectedModel
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: FluScrollBar{}
                        property bool dragActive: false
                        property int dragFromIndex: -1
                        property int dragToIndex: -1

                        move: Transition{
                            NumberAnimation{ properties: "y"; duration: 220; easing.type: Easing.OutCubic }
                        }
                        delegate: Item{
                            id:row_sel
                            width: list_selected.width
                            height: 40
                            z: drag_area_sel.pressed ? 3 : 1
                            Rectangle{
                                id:sel_item_bg
                                anchors.fill: parent
                                radius: 4
                                color: drag_area_sel.containsMouse ? FluTheme.itemHoverColor : "transparent"
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
                                        id: btn_remove
                                        iconSource: FluentIcons.ChromeClose
                                        iconSize: 12
                                        width: 30
                                        height: 30
                                        onClicked: {
                                            setCaseCheckedByNodeid(modelData.nodeid, false, "selected_remove")
                                        }
                                    }
                                }
                                MouseArea{
                                    id:drag_area_sel
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.rightMargin: 42
                                    z: 10
                                    acceptedButtons: Qt.LeftButton
                                    preventStealing: true
                                    hoverEnabled: true
                                    propagateComposedEvents: false
                                    drag.threshold: 1
                                    onPressed: (mouse)=>{
                                        list_selected.dragActive = true
                                        list_selected.dragFromIndex = index
                                        list_selected.dragToIndex = index
                                        mouse.accepted = true
                                    }
                                    onPositionChanged: (mouse)=>{
                                        if(!list_selected.dragActive){
                                            return
                                        }
                                        var pt = drag_area_sel.mapToItem(list_selected.contentItem, mouse.x, mouse.y)
                                        var hoverIndex = list_selected.indexAt(pt.x, pt.y)
                                        if(hoverIndex === -1){
                                            return
                                        }
                                        if(hoverIndex === list_selected.dragToIndex){
                                            return
                                        }
                                        list_selected.dragToIndex = hoverIndex
                                    }
                                    onReleased: (mouse)=>{
                                        var finalFromIndex = list_selected.dragFromIndex
                                        var finalToIndex = list_selected.dragToIndex
                                        list_selected.dragActive = false
                                        list_selected.dragFromIndex = -1
                                        list_selected.dragToIndex = -1
                                        if(finalFromIndex >= 0 && finalToIndex >= 0 && finalFromIndex !== finalToIndex){
                                            moveSelectedLocal(finalFromIndex, finalToIndex)
                                        }
                                    }
                                    onCanceled: {
                                        list_selected.dragActive = false
                                        list_selected.dragFromIndex = -1
                                        list_selected.dragToIndex = -1
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
                            model: selectedModel
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

}
