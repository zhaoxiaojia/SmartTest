from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_test_page_parameter_display_uses_single_read_model():
    qml_source = (ROOT / "ui/example/imports/example/qml/page/T_TestConfig.qml").read_text(encoding="utf-8")
    bridge_source = (ROOT / "ui/example/bridge/TestPageBridge.py").read_text(encoding="utf-8")

    assert "TestPageBridge.selectedCaseParamRows()" in qml_source
    assert "TestPageBridge.globalParamRows()" in qml_source
    assert "return case_param_expander.caseFields" in qml_source
    assert "TestPageBridge.caseParamValue(" not in qml_source
    assert "TestPageBridge.caseParamListContains(" not in qml_source
    assert "TestPageBridge.globalContext(" not in qml_source
    assert "TestPageBridge.globalSchema(" not in qml_source

    assert "def caseParamFields(" not in bridge_source
    assert "def caseParamValue(" not in bridge_source
    assert "def caseParamListContains(" not in bridge_source
    assert "def globalContext(" not in bridge_source
    assert "def globalSchema(" not in bridge_source
    assert "def caseTypeConfig(" not in bridge_source
    assert "def setCaseTypeValue(" not in bridge_source


def test_text_parameter_edits_save_without_refreshing_view_model():
    qml_source = (ROOT / "ui/example/imports/example/qml/page/T_TestConfig.qml").read_text(encoding="utf-8")
    bridge_source = (ROOT / "ui/example/bridge/TestPageBridge.py").read_text(encoding="utf-8")

    assert "onTextChanged: persistValue()" in qml_source
    assert "TestPageBridge.saveCaseParamValue(caseNodeId, fieldData.key" in qml_source
    assert "onTextChanged: TestPageBridge.saveGlobalValue(fieldData.key, text)" in qml_source

    save_case_body = bridge_source.split("def saveCaseParamValue", 1)[1].split("@Slot", 1)[0]
    save_global_body = bridge_source.split("def saveGlobalValue", 1)[1].split("@Slot", 1)[0]

    assert "save_state(self._state_path, self._state)" in save_case_body
    assert "save_state(self._state_path, self._state)" in save_global_body
    assert "stateChanged.emit()" not in save_case_body
    assert "stateChanged.emit()" not in save_global_body


def test_start_button_does_not_force_parameter_save():
    qml_source = (ROOT / "ui/example/imports/example/qml/page/T_TestConfig.qml").read_text(encoding="utf-8")

    start_button_body = qml_source.split("if(RunBridge.startRun())", 1)[0].rsplit("onClicked:", 1)[1]

    assert "forceActiveFocus" not in start_button_body
    assert "TestPageBridge.save" not in start_button_body
    assert "TestPageBridge.set" not in start_button_body
