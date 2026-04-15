import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import FluentUI 1.0
import "../global"

FluPage {
    title: qsTr("Test")

    property int stateVersion: 0
    property var selectedModel: []
    property var selectedCaseParamsModel: []
    property var selectedCaseTypesModel: []
    property var caseTreeDataSource: []
    property var caseExpandState: ({})
    property var caseParamExpandState: ({})

    function trimmedCasePath(filePath){
        var path = (filePath || "").toString()
        if(path.indexOf("testing/tests/") === 0){
            return path.substring("testing/tests/".length)
        }
        return path
    }

    function paramScopeLabel(scope){
        if(scope === "global_context"){
            return qsTr("Global")
        }
        if(scope === "case_type_shared"){
            return qsTr("Shared by Case Type")
        }
        return qsTr("Per Case")
    }

    function caseParamTextValue(nodeid, key){
        var _version = stateVersion
        var value = TestPageBridge.caseParamValue(nodeid, key)
        if(value === undefined || value === null){
            return ""
        }
        return value + ""
    }

    function caseParamIntValue(nodeid, key, fallbackValue){
        var _version = stateVersion
        var value = TestPageBridge.caseParamValue(nodeid, key)
        var parsed = parseInt(value, 10)
        if(!isNaN(parsed)){
            return parsed
        }
        var fallbackParsed = parseInt(fallbackValue, 10)
        return isNaN(fallbackParsed) ? 0 : fallbackParsed
    }

    function caseParamBoolValue(nodeid, key){
        var _version = stateVersion
        var value = TestPageBridge.caseParamValue(nodeid, key)
        if(value === true || value === false){
            return value
        }
        var text = (value === undefined || value === null) ? "" : (value + "").toLowerCase()
        return text === "true" || text === "1" || text === "yes" || text === "on"
    }

    function isCaseParamExpanded(nodeid, requiredCount){
        if(caseParamExpandState[nodeid] === undefined){
            caseParamExpandState[nodeid] = requiredCount > 0
        }
        return caseParamExpandState[nodeid] === true
    }

    function isExpandedByDefault(key){
        if(caseExpandState[key] === undefined){
            caseExpandState[key] = false
        }
        return caseExpandState[key] === true
    }

    function expandedKeys(){
        var keys = []
        for(var key in caseExpandState){
            if(caseExpandState[key] === true){
                keys.push(key)
            }
        }
        return keys
    }

    function decorateTreeNodes(nodes){
        var source = nodes || []
        var decorated = []
        for(var i = 0; i < source.length; i++){
            var node = source[i]
            var rowType = node.rowType || ""
            var iconSource = 0
            if(rowType === "folder" || rowType === "root"){
                iconSource = FluentIcons.Folder
            }else if(rowType === "file"){
                iconSource = FluentIcons.Document
            }
            var copy = {
                title: node.title,
                _key: node._key,
                rowType: rowType,
                iconSource: iconSource,
                expanded: node.expanded === true,
                file: node.file,
                checked: node.checked === true
            }
            if(node.children !== undefined){
                copy.children = decorateTreeNodes(node.children)
            }
            decorated.push(copy)
        }
        return decorated
    }

    function refreshViewModels(){
        caseTreeDataSource = decorateTreeNodes(TestPageBridge.caseTree((txt_filter.text || "").toString(), expandedKeys()))
        selectedModel = TestPageBridge.selectedFileRows()
        selectedCaseParamsModel = TestPageBridge.selectedCaseParamRows()
        selectedCaseTypesModel = TestPageBridge.activeCaseTypes()
    }

    Connections{
        target: TestPageBridge
        function onCasesChanged(){
            refreshViewModels()
        }
        function onStateChanged(){
            stateVersion = stateVersion + 1
            refreshViewModels()
        }
        function onErrorOccurred(msg){
            showError(msg)
        }
    }

    Component.onCompleted: {
        TestPageBridge.discoverCases()
        refreshViewModels()
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
                        placeholderText: qsTr("Filter by file...")
                        Layout.fillWidth: true
                        onTextChanged: refreshViewModels()
                    }
                    FluGroupBox{
                        title: ""
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        padding: 8
                        FluTreeView{
                            id:tree_cases
                            anchors.fill: parent
                            headerVisible: false
                            showLine: false
                            cellHeight: 32
                            depthPadding: 10
                            checkable: true
                            checkLeafOnly: true
                            clickLeafRowToToggleCheckOnly: true
                            columnSource: [{
                                title: "",
                                dataIndex: "title",
                                width: Math.max(220, tree_cases.width - 8)
                            }]
                            dataSource: caseTreeDataSource
                            onLeafCheckToggled: (rowData, checked)=>{
                                if(rowData && rowData.file){
                                    TestPageBridge.setFileSelected(rowData.file, checked === true)
                                }
                            }
                            onBranchToggled: (rowData, expanded)=>{
                                if(rowData && rowData._key){
                                    caseExpandState[rowData._key] = expanded === true
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
                                        text: trimmedCasePath(modelData.file)
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
                                            TestPageBridge.setFileSelected(modelData.file, false)
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
                                            TestPageBridge.moveSelectedFile(finalFromIndex, finalToIndex)
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

        // Middle: selected case parameters
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
                    text: qsTr("Case Parameters (%1)").arg(selectedCaseParamsModel.length)
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
                        FluText{
                            visible: selectedCaseParamsModel.length === 0
                            Layout.fillWidth: true
                            text: qsTr("Select one or more test files to inspect the required parameters for each case.")
                            font: FluTextStyle.Body
                            color: FluTheme.fontSecondaryColor
                            wrapMode: Text.WordWrap
                        }
                        Repeater{
                            model: selectedCaseParamsModel
                            FluExpander{
                                id: case_param_expander
                                property string caseNodeId: modelData.nodeid || ""
                                Layout.fillWidth: true
                                headerText: modelData.name + "  (" + modelData.required_params.length + ")"
                                expand: isCaseParamExpanded(caseNodeId, modelData.required_params.length)
                                contentHeight: expander_content.implicitHeight
                                onExpandChanged: {
                                    caseParamExpandState[caseNodeId] = expand
                                }

                                Item{
                                    id: expander_content
                                    width: parent.width
                                    implicitHeight: col_case_form.implicitHeight + 24

                                    ColumnLayout{
                                        id: col_case_form
                                        x: 12
                                        y: 12
                                        width: parent.width - 24
                                        spacing: 8

                                        FluText{
                                            text: trimmedCasePath(modelData.file)
                                            font: FluTextStyle.Caption
                                            color: FluTheme.fontSecondaryColor
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }

                                        FluText{
                                            visible: modelData.required_params.length === 0
                                            Layout.fillWidth: true
                                            text: qsTr("No configurable parameters are required for this case.")
                                            font: FluTextStyle.Body
                                            color: FluTheme.fontSecondaryColor
                                            wrapMode: Text.WordWrap
                                        }

                                        Repeater{
                                            model: TestPageBridge.caseParamFields(case_param_expander.caseNodeId)
                                            ColumnLayout{
                                                property string caseNodeId: case_param_expander.caseNodeId
                                                property var fieldData: modelData
                                                Layout.fillWidth: true
                                                spacing: 4

                                                FluText{
                                                    text: fieldData.label
                                                    font: FluTextStyle.BodyStrong
                                                    Layout.fillWidth: true
                                                    wrapMode: Text.WordWrap
                                                }

                                                FluText{
                                                    Layout.fillWidth: true
                                                    text: {
                                                        var summary = paramScopeLabel(fieldData.scope)
                                                        if(fieldData.description){
                                                            summary += " - " + fieldData.description
                                                        }
                                                        return summary
                                                    }
                                                    font: FluTextStyle.Caption
                                                    color: FluTheme.fontSecondaryColor
                                                    wrapMode: Text.WordWrap
                                                }

                                                FluTextBox{
                                                    visible: fieldData.type === "string" || fieldData.type === "path" || fieldData.type === "float"
                                                    Layout.fillWidth: true
                                                    text: caseParamTextValue(caseNodeId, fieldData.key)
                                                    placeholderText: fieldData.default !== undefined && fieldData.default !== null ? (fieldData.default + "") : ""
                                                    onEditingFinished: {
                                                        TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, text)
                                                    }
                                                }

                                                FluSpinBox{
                                                    visible: fieldData.type === "int"
                                                    Layout.fillWidth: true
                                                    editable: true
                                                    from: -1000000
                                                    to: 1000000
                                                    value: caseParamIntValue(caseNodeId, fieldData.key, fieldData.default)
                                                    onValueModified: {
                                                        TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, value)
                                                    }
                                                }

                                                FluComboBox{
                                                    visible: fieldData.type === "enum"
                                                    Layout.fillWidth: true
                                                    model: fieldData.enum_values || []
                                                    currentIndex: {
                                                        var currentValue = caseParamTextValue(caseNodeId, fieldData.key)
                                                        var options = fieldData.enum_values || []
                                                        return options.indexOf(currentValue)
                                                    }
                                                    onActivated: {
                                                        if(currentIndex >= 0){
                                                            TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, currentText)
                                                        }
                                                    }
                                                }

                                                FluToggleSwitch{
                                                    visible: fieldData.type === "bool"
                                                    checked: caseParamBoolValue(caseNodeId, fieldData.key)
                                                    text: checked ? qsTr("Enabled") : qsTr("Disabled")
                                                    onClicked: {
                                                        TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, checked)
                                                    }
                                                }

                                                FluMultilineTextBox{
                                                    visible: fieldData.type === "multiline"
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 96
                                                    text: caseParamTextValue(caseNodeId, fieldData.key)
                                                    placeholderText: fieldData.default !== undefined && fieldData.default !== null ? (fieldData.default + "") : ""
                                                    isCtrlEnterForNewline: true
                                                    onCommit: {
                                                        TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, text)
                                                    }
                                                    onActiveFocusChanged: {
                                                        if(!activeFocus){
                                                            TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, text)
                                                        }
                                                    }
                                                }

                                                FluDivider{
                                                    Layout.fillWidth: true
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
                                text: {
                                    var _version = stateVersion
                                    return TestPageBridge.globalContext()[modelData.key] + ""
                                }
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
                        model: selectedCaseTypesModel
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
                                            var _version = stateVersion
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
