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
