import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import QtQml 2.15
import FluentUI 1.0
import "../global"

FluPage {
    id: page_root
    title: qsTr("Test")
    property int footerHeight: 30

    property int stateVersion: 0
    property var selectedModel: []
    property var selectedCaseParamsModel: []
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

    Connections{
        target: RunBridge
        function onErrorOccurred(msg){
            showError(msg)
        }
    }

    Component.onCompleted: {
        TestPageBridge.discoverCases()
        refreshViewModels()
    }

    FluSplitLayout{
        id: layout_main
        anchors.fill: parent
        anchors.bottomMargin: footerHeight
        orientation: Qt.Horizontal

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
                        id: txt_filter
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
                            id: tree_cases
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
                        id: list_selected
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
                            id: row_sel
                            width: list_selected.width
                            height: 40
                            z: drag_area_sel.pressed ? 3 : 1
                            Rectangle{
                                id: sel_item_bg
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
                                    id: drag_area_sel
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
                        id: col_case_params
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
                                                    id: text_case_param
                                                    visible: fieldData.type === "string" || fieldData.type === "path" || fieldData.type === "float"
                                                    Layout.fillWidth: true
                                                    placeholderText: fieldData.default !== undefined && fieldData.default !== null ? (fieldData.default + "") : ""
                                                    Binding {
                                                        target: text_case_param
                                                        property: "text"
                                                        when: text_case_param.visible && !text_case_param.activeFocus
                                                        value: caseParamTextValue(caseNodeId, fieldData.key)
                                                    }
                                                    onTextChanged: TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, text)
                                                    onEditingFinished: TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, text)
                                                }

                                                FluSpinBox{
                                                    id: spin_case_param
                                                    property bool persistReady: false
                                                    property int _lastPersistedValue: 0
                                                    function syncFromState(){
                                                        if(!visible){
                                                            return
                                                        }
                                                        if(activeFocus){
                                                            return
                                                        }
                                                        if(contentItem && contentItem.activeFocus){
                                                            return
                                                        }
                                                        var nextValue = caseParamIntValue(caseNodeId, fieldData.key, fieldData.default)
                                                        if(value !== nextValue){
                                                            value = nextValue
                                                        }
                                                        _lastPersistedValue = nextValue
                                                    }
                                                    function persistParsedText(rawText, eventName){
                                                        if(!persistReady){
                                                            return
                                                        }
                                                        var parsed = parseInt(rawText, 10)
                                                        if(isNaN(parsed)){
                                                            return
                                                        }
                                                        if(parsed < from){
                                                            parsed = from
                                                        }
                                                        if(parsed > to){
                                                            parsed = to
                                                        }
                                                        if(_lastPersistedValue === parsed){
                                                            return
                                                        }
                                                        _lastPersistedValue = parsed
                                                        TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, parsed)
                                                    }
                                                    visible: fieldData.type === "int"
                                                    Layout.fillWidth: true
                                                    editable: true
                                                    from: -1000000
                                                    to: 1000000
                                                    Component.onCompleted: {
                                                        syncFromState()
                                                        persistReady = true
                                                    }
                                                    onVisibleChanged: syncFromState()
                                                    onActiveFocusChanged: {
                                                        if(!activeFocus){
                                                            syncFromState()
                                                        }
                                                    }
                                                    onValueModified: {
                                                        if(!persistReady){
                                                            return
                                                        }
                                                        _lastPersistedValue = value
                                                        TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, value)
                                                    }
                                                    Connections {
                                                        target: page_root
                                                        function onStateVersionChanged() {
                                                            spin_case_param.syncFromState()
                                                        }
                                                    }
                                                    Connections {
                                                        target: spin_case_param.contentItem
                                                        function onTextEdited() {
                                                            spin_case_param.persistParsedText(spin_case_param.contentItem.text)
                                                        }
                                                        function onEditingFinished() {
                                                            spin_case_param.persistParsedText(spin_case_param.contentItem.text)
                                                        }
                                                        function onActiveFocusChanged() {
                                                            if(!spin_case_param.contentItem.activeFocus){
                                                                spin_case_param.persistParsedText(spin_case_param.contentItem.text)
                                                                spin_case_param.syncFromState()
                                                            }
                                                        }
                                                    }
                                                }

                                                FluComboBox{
                                                    id: combo_case_param
                                                    visible: fieldData.type === "enum"
                                                    Layout.fillWidth: true
                                                    model: fieldData.enum_values || []
                                                    enabled: (fieldData.enum_values || []).length > 0
                                                    currentIndex: {
                                                        var currentValue = caseParamTextValue(caseNodeId, fieldData.key)
                                                        var options = fieldData.enum_values || []
                                                        return options.indexOf(currentValue)
                                                    }
                                                    onDownChanged: {
                                                        if(down && fieldData.key.indexOf(":bt_target") >= 0){
                                                            TestPageBridge.reloadState()
                                                        }
                                                    }
                                                    onActivated: {
                                                        if(currentIndex >= 0){
                                                            TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, currentText)
                                                        }
                                                    }
                                                }

                                                FluText{
                                                    visible: fieldData.type === "enum"
                                                             && fieldData.key.indexOf(":bt_target") >= 0
                                                             && (fieldData.enum_values || []).length === 0
                                                    Layout.fillWidth: true
                                                    text: qsTr("No paired Bluetooth devices found on the current DUT.")
                                                    font: FluTextStyle.Caption
                                                    color: FluTheme.fontSecondaryColor
                                                    wrapMode: Text.WordWrap
                                                }

                                                FluToggleSwitch{
                                                    visible: fieldData.type === "bool"
                                                    checked: caseParamBoolValue(caseNodeId, fieldData.key)
                                                    text: checked ? qsTr("Enabled") : qsTr("Disabled")
                                                    onClicked: TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, checked)
                                                }

                                                FluMultilineTextBox{
                                                    id: text_case_param_multiline
                                                    visible: fieldData.type === "multiline"
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 96
                                                    placeholderText: fieldData.default !== undefined && fieldData.default !== null ? (fieldData.default + "") : ""
                                                    isCtrlEnterForNewline: true
                                                    Binding {
                                                        target: text_case_param_multiline
                                                        property: "text"
                                                        when: text_case_param_multiline.visible && !text_case_param_multiline.activeFocus
                                                        value: caseParamTextValue(caseNodeId, fieldData.key)
                                                    }
                                                    onTextChanged: TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, text)
                                                    onCommit: TestPageBridge.setCaseParamValue(caseNodeId, fieldData.key, text)
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
                    id: col_right
                    width: parent.width
                    spacing: 10

                    FluText{
                        text: qsTr("DUT")
                        font: FluTextStyle.Subtitle
                    }

                    Repeater{
                        model: {
                            var _version = stateVersion
                            return TestPageBridge.globalSchema().fields
                        }
                        RowLayout{
                            Layout.fillWidth: true
                            spacing: 8
                            FluText{
                                text: modelData.label
                                Layout.preferredWidth: 140
                                elide: Text.ElideRight
                            }
                            FluComboBox{
                                id: combo_dut
                                visible: modelData.type === "enum"
                                Layout.fillWidth: true
                                model: modelData.enum_values || []
                                currentIndex: {
                                    var _version = stateVersion
                                    var options = modelData.enum_values || []
                                    var currentValue = TestPageBridge.globalContext()[modelData.key] + ""
                                    return options.indexOf(currentValue)
                                }
                                onDownChanged: {
                                    if(down && modelData.key === "dut"){
                                        TestPageBridge.refreshGlobalSchema()
                                    }
                                }
                                onActivated: {
                                    if(currentIndex >= 0){
                                        TestPageBridge.setGlobalValue(modelData.key, currentText)
                                    }
                                }
                            }
                            FluTextBox{
                                id: text_global_param
                                visible: modelData.type !== "enum"
                                Layout.fillWidth: true
                                Binding {
                                    target: text_global_param
                                    property: "text"
                                    when: text_global_param.visible && !text_global_param.activeFocus
                                    value: {
                                        var _version = stateVersion
                                        var value = TestPageBridge.globalContext()[modelData.key]
                                        return value === undefined || value === null ? "" : (value + "")
                                    }
                                }
                                onTextChanged: TestPageBridge.setGlobalValue(modelData.key, text)
                                onEditingFinished: TestPageBridge.setGlobalValue(modelData.key, text)
                            }
                        }
                    }

                    FluDivider{}
                }
            }
        }
    }

    FluFilledButton{
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: footerHeight
        text: RunBridge.isRunning ? qsTr("Stop") : qsTr("Start")
        onClicked: {
            if(RunBridge.isRunning){
                RunBridge.stopRun()
                return
            }
            ItemsOriginal.startPageByItem({ title: qsTr("Run"), url: "qrc:/example/qml/page/T_Run.qml" })
            RunBridge.startRun()
        }
    }
}
