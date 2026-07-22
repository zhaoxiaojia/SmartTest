import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

ColumnLayout {
    id: root
    property var field: ({})
    property string issueId: ""
    property bool disabled: false
    signal valueChanged(string issueId, string fieldId, var value)
    signal userSearchRequested(string issueId, string fieldId, string query)

    Layout.fillWidth: true
    spacing: 4

    FluText {
        text: (root.field.name || root.field.fieldId || "") + (root.field.required ? " *" : "")
        font: FluTextStyle.BodyStrong
    }

    Loader {
        id: editorLoader
        Layout.fillWidth: true
        sourceComponent: root.field.control === "text" ? textEditor
            : root.field.control === "multiline" ? multilineEditor
            : root.field.control === "single" ? singleEditor
            : root.field.control === "multi" ? multiEditor
            : root.field.control === "cascade" ? cascadeEditor
            : root.field.control === "user" ? userEditor : textEditor
    }

    FluText {
        visible: !!root.field.error
        text: root.field.error || ""
        color: "#D13438"
        wrapMode: Text.Wrap
    }

    Component {
        id: textEditor
        FluTextBox {
            objectName: "jiraCreateText_" + (root.field.fieldId || "")
            text: root.field.value === undefined || root.field.value === null ? "" : String(root.field.value)
            disabled: root.disabled
            onEditingFinished: root.valueChanged(root.issueId, root.field.fieldId || "", text)
        }
    }
    Component {
        id: multilineEditor
        FluMultilineTextBox {
            objectName: "jiraCreateMultiline_" + (root.field.fieldId || "")
            text: root.field.value || ""
            disabled: root.disabled
            Layout.preferredHeight: 100
            onEditingFinished: root.valueChanged(root.issueId, root.field.fieldId || "", text)
        }
    }
    Component {
        id: singleEditor
        FluComboBox {
            objectName: "jiraCreateSingle_" + (root.field.fieldId || "")
            model: root.field.options || []
            textRole: "label"
            valueRole: "value"
            disabled: root.disabled
            Component.onCompleted: currentIndex = root.optionIndex(model, root.field.value)
            onActivated: root.valueChanged(root.issueId, root.field.fieldId || "", currentValue)
        }
    }
    Component {
        id: multiEditor
        Flow {
            width: parent ? parent.width : 0
            spacing: 8
            Repeater {
                model: root.field.options || []
                FluCheckBox {
                    text: modelData.label || modelData.value || ""
                    checked: root.containsValue(root.field.value, modelData.value)
                    disabled: root.disabled
                    onClicked: root.valueChanged(root.issueId, root.field.fieldId || "", root.toggledValues(root.field.value, modelData.value, checked))
                }
            }
        }
    }
    Component {
        id: cascadeEditor
        RowLayout {
            property var parentValue: (root.field.value || {}).parent || ""
            property var childValue: (root.field.value || {}).child || ""
            FluComboBox {
                Layout.fillWidth: true
                model: root.field.options || []
                textRole: "label"; valueRole: "value"; disabled: root.disabled
                Component.onCompleted: currentIndex = root.optionIndex(model, parent.parentValue)
                onActivated: root.valueChanged(root.issueId, root.field.fieldId || "", {"parent": currentValue, "child": ""})
            }
            FluComboBox {
                Layout.fillWidth: true
                model: root.childrenFor(root.field.options, parent.parentValue)
                textRole: "label"; valueRole: "value"; disabled: root.disabled
                Component.onCompleted: currentIndex = root.optionIndex(model, parent.childValue)
                onActivated: root.valueChanged(root.issueId, root.field.fieldId || "", {"parent": parent.parentValue, "child": currentValue})
            }
        }
    }
    Component {
        id: userEditor
        FluAutoSuggestBox {
            objectName: "jiraCreateUser_" + (root.field.fieldId || "")
            text: root.field.value || ""
            items: root.userSuggestions(root.field.options)
            disabled: root.disabled
            placeholderText: qsTr("Search Jira users")
            onTextChanged: if (activeFocus) root.userSearchRequested(root.issueId, root.field.fieldId || "", text)
            onItemClicked: data => root.valueChanged(root.issueId, root.field.fieldId || "", data.value || data.title || "")
            onCommit: root.valueChanged(root.issueId, root.field.fieldId || "", text)
        }
    }

    function optionIndex(options, value) {
        for (var i = 0; options && i < options.length; ++i) if (options[i].value === value) return i
        return -1
    }
    function containsValue(values, value) { return values && values.indexOf(value) >= 0 }
    function toggledValues(values, value, selected) {
        var result = values ? values.slice() : []
        var index = result.indexOf(value)
        if (selected && index < 0) result.push(value)
        if (!selected && index >= 0) result.splice(index, 1)
        return result
    }
    function childrenFor(options, parentValue) {
        for (var i = 0; options && i < options.length; ++i) if (options[i].value === parentValue) return options[i].children || []
        return []
    }
    function userSuggestions(options) {
        var result = []
        for (var i = 0; options && i < options.length; ++i) {
            result.push({"title": options[i].label || options[i].value || "", "value": options[i].value || ""})
        }
        return result
    }
    function focusEditor() {
        if (editorLoader.item) editorLoader.item.forceActiveFocus()
    }
}
