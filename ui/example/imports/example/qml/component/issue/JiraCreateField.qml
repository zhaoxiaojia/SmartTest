import QtQuick 2.15
import QtQuick.Layouts 1.15
import FluentUI 1.0

ColumnLayout {
    id: root
    property var field: ({})
    property string issueId: ""
    property bool disabled: false
    property real labelColumnWidth: 180
    property bool hasVisibleLabel: !!String(root.field.name || root.field.fieldId || "").trim()
    signal valueChanged(string issueId, string fieldId, var value)
    signal userSearchRequested(string issueId, string fieldId, string query)

    Layout.fillWidth: true
    visible: root.hasVisibleLabel
    spacing: 3

    RowLayout {
        id: fieldRow
        Layout.fillWidth: true
        spacing: 12
        FluText {
            Layout.preferredWidth: root.labelColumnWidth
            Layout.minimumWidth: root.labelColumnWidth
            Layout.maximumWidth: root.labelColumnWidth
            Layout.alignment: Qt.AlignTop
            text: (root.field.name || root.field.fieldId || "") + (root.field.required ? " *" : "")
            font: FluTextStyle.BodyStrong
            wrapMode: Text.Wrap
        }
        Loader {
            id: editorLoader
            Layout.fillWidth: true
            active: root.hasVisibleLabel
            sourceComponent: root.field.control === "text" ? textEditor
                : root.field.control === "multiline" ? multilineEditor
                : root.field.control === "single" ? singleEditor
                : root.field.control === "multi" ? optionMultiEditor
                : root.field.control === "cascade" ? cascadeEditor
                : root.field.control === "user" ? userEditor : textEditor
        }
    }

    FluText {
        visible: !!root.field.error
        Layout.leftMargin: root.labelColumnWidth + 12
        Layout.fillWidth: true
        text: root.field.error || ""
        color: "#D13438"
        wrapMode: Text.Wrap
    }

    Component {
        id: textEditor
        FluTextBox { /* persistence-opt-out: transient */
            objectName: "jiraCreateText_" + (root.field.fieldId || "")
            text: root.field.value === undefined || root.field.value === null ? "" : String(root.field.value)
            disabled: root.disabled
            onEditingFinished: root.valueChanged(root.issueId, root.field.fieldId || "", text)
        }
    }
    Component {
        id: multilineEditor
        FluMultilineTextBox { /* persistence-opt-out: transient */
            objectName: "jiraCreateMultiline_" + (root.field.fieldId || "")
            text: root.field.value || ""
            disabled: root.disabled
            Layout.preferredHeight: 100
            onEditingFinished: root.valueChanged(root.issueId, root.field.fieldId || "", text)
        }
    }
    Component {
        id: singleEditor
        FluComboBox { /* persistence-opt-out: transient */
            objectName: "jiraCreateSingle_" + (root.field.fieldId || "")
            model: root.field.options || []
            textRole: "label"
            valueRole: "value"
            popupMaximumVisibleItems: 8
            disabled: root.disabled
            Component.onCompleted: currentIndex = root.optionIndex(model, root.field.value)
            onActivated: index => {
                root.valueChanged(root.issueId, root.field.fieldId || "",
                                  root.optionValue(model, index))
            }
        }
    }
    Component {
        id: optionMultiEditor
        JiraOptionMultiPicker {
            options: root.field.options || []
            value: root.field.value || []
            disabled: root.disabled
            placeholderText: qsTr("Select options")
            onSelectionChanged: value => {
                root.valueChanged(root.issueId, root.field.fieldId || "", value)
            }
        }
    }
    Component {
        id: cascadeEditor
        RowLayout {
            property var parentValue: (root.field.value || {}).parent || ""
            property var childValue: (root.field.value || {}).child || ""
            FluComboBox { /* persistence-opt-out: transient */
                Layout.fillWidth: true
                objectName: "jiraCreateCascadeParent_" + (root.field.fieldId || "")
                model: root.field.options || []
                textRole: "label"; valueRole: "value"; disabled: root.disabled
                Component.onCompleted: currentIndex = root.optionIndex(model, parent.parentValue)
                onActivated: index => {
                    var value = {
                        "parent": root.optionValue(model, index), "child": ""
                    }
                    root.valueChanged(
                        root.issueId, root.field.fieldId || "", value)
                }
            }
            FluComboBox { /* persistence-opt-out: transient */
                Layout.fillWidth: true
                objectName: "jiraCreateCascadeChild_" + (root.field.fieldId || "")
                model: root.childrenFor(root.field.options, parent.parentValue)
                textRole: "label"; valueRole: "value"; disabled: root.disabled
                Component.onCompleted: currentIndex = root.optionIndex(model, parent.childValue)
                onActivated: index => {
                    var value = {
                        "parent": parent.parentValue,
                        "child": root.optionValue(model, index)
                    }
                    root.valueChanged(
                        root.issueId, root.field.fieldId || "", value)
                }
            }
        }
    }
    Component {
        id: userEditor
        FluAutoSuggestBox { /* persistence-opt-out: transient */
            property string selectedValue: String(root.field.value || "")
            objectName: "jiraCreateUser_" + (root.field.fieldId || "")
            text: ""
            items: root.userSuggestions(root.field.options)
            disabled: root.disabled
            placeholderText: qsTr("Search Jira users")
            onTextEdited: {
                selectedValue = ""
                root.userSearchRequested(root.issueId, root.field.fieldId || "", text)
            }
            onItemClicked: data => {
                selectedValue = String(data.value || "")
                if (selectedValue) {
                    root.valueChanged(root.issueId, root.field.fieldId || "", selectedValue)
                }
            }
            onEditingFinished: {
                if (!selectedValue) {
                    var account = root.userAccountInput(root.field.options, text)
                    if (account) {
                        root.valueChanged(root.issueId, root.field.fieldId || "", account)
                    }
                }
            }
            Component.onCompleted: {
                updateText(root.optionLabel(root.field.options, root.field.value))
            }
        }
    }

    function optionIndex(options, value) {
        for (var i = 0; options && i < options.length; ++i) if (options[i].value === value) return i
        return -1
    }
    function optionValue(options, index) {
        if (!options || index < 0 || index >= options.length)
            return ""
        return options[index].value
    }
    function optionLabel(options, value) {
        for (var i = 0; options && i < options.length; ++i)
            if (String(options[i].value || "") === String(value || ""))
                return String(options[i].label || options[i].value || "")
        return String(value || "")
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
    function userAccountInput(options, text) {
        var candidate = String(text || "").trim()
        if (!/^[A-Za-z0-9._@-]+$/.test(candidate))
            return ""
        for (var i = 0; options && i < options.length; ++i) {
            if (String(options[i].label || "") === candidate
                    && String(options[i].value || "") !== candidate)
                return ""
        }
        return candidate
    }
    function focusEditor() {
        if (editorLoader.item) editorLoader.item.forceActiveFocus()
    }
}
