from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ui"))

import example.imports.resource_rc  # noqa: F401
from example.bridge.TestPageBridge import TestPageBridge
from example.helper.TranslateHelper import TranslateHelper
from example.helper.TsTextCatalog import TsTextCatalog
from testing.state.models import SelectedCase


def _translator() -> TranslateHelper:
    helper = TranslateHelper()
    helper.init(None)
    return helper


def test_ts_text_catalog_reads_test_page_parameter_text_from_ts() -> None:
    catalog = TsTextCatalog(Path.cwd())

    assert catalog.text(
        locale="en_US",
        context="TestPageBridge",
        source="test.param.ac_onoff.cycle_count.label",
    ) == "Cycle count"
    assert catalog.text(
        locale="zh_CN",
        context="TestPageBridge",
        source="test.param.ac_onoff.cycle_count.label",
    ) == "\u5faa\u73af\u6b21\u6570"


def test_test_page_bridge_env_rows_follow_selected_required_equipment(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    helper = _translator()
    previous_language = helper.current
    helper.current = "en_US"
    nodeid = "testing/tests/android/stress/test_ac_onoff.py::test_ac_onoff_via_relay"
    bridge = TestPageBridge(Path.cwd())
    bridge._state_path = tmp_path / "test_page_state.json"
    bridge._cases = [
        {
            "nodeid": nodeid,
            "file": "testing/tests/android/stress/test_ac_onoff.py",
            "name": "test_ac_onoff_via_relay",
            "markers": ["requires_equipment"],
            "case_type": "stress",
            "required_params": [],
            "required_param_groups": [],
            "required_equipment": ["relay"],
            "android_case_id": "",
        }
    ]
    bridge._rebuild_case_indexes()
    bridge._state.selected = [SelectedCase(nodeid=nodeid, case_type="stress")]
    bridge._state.global_context = {}

    try:
        rows = bridge.envEquipmentRows()

        assert [row["kind"] for row in rows] == ["relay"]
        assert rows[0]["label"] == "Relay"
        assert rows[0]["label_source"] == "fixed"
        assert rows[0]["type"] == "snmp_pdu"
        assert rows[0]["type_source"] == "user"
        assert [field["key"] for field in rows[0]["fields"]] == ["ip", "port"]
        assert [field["label_source"] for field in rows[0]["fields"]] == ["fixed", "fixed"]
        assert [field["value_source"] for field in rows[0]["fields"]] == ["user", "user"]
    finally:
        helper.current = previous_language


def test_test_page_bridge_env_config_is_saved_under_global_equipment(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = TestPageBridge(Path.cwd())
    bridge._state_path = tmp_path / "test_page_state.json"
    bridge._state.global_context = {}

    bridge.setEnvEquipmentType("relay", "snmp_pdu")
    bridge.setEnvEquipmentValue("relay", "ip", "192.0.2.10")
    bridge.setEnvEquipmentValue("relay", "port", 4)

    assert bridge.globalContext()["equipment"] == {
        "relay": {
            "type": "snmp_pdu",
            "ip": "192.0.2.10",
            "port": 4,
        }
    }
    assert bridge.envEquipmentValue("relay", "ip") == "192.0.2.10"
    assert bridge.envEquipmentValue("relay", "port") == 4


def test_test_page_bridge_keeps_equipment_when_pruning_global_context(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    bridge = TestPageBridge(Path.cwd())
    bridge._state_path = tmp_path / "test_page_state.json"
    bridge._adb_devices = ["ABC123"]
    bridge._state.global_context = {
        "dut": "ABC123",
        "equipment": {"relay": {"type": "snmp_pdu", "ip": "192.0.2.10", "port": 4}},
        "unknown": "remove me",
    }

    bridge._ensure_state_defaults()

    assert bridge.globalContext() == {
        "dut": "ABC123",
        "equipment": {"relay": {"type": "snmp_pdu", "ip": "192.0.2.10", "port": 4}},
    }


def test_test_page_bridge_parameter_text_follows_current_language(tmp_path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None

    helper = _translator()
    previous_language = helper.current
    bridge = TestPageBridge(Path.cwd())
    bridge._state_path = tmp_path / "test_page_state.json"
    bridge._cases = [
        {
            "nodeid": "testing/tests/android/stress/test_ac_onoff.py::test_ac_onoff_via_relay",
            "file": "testing/tests/android/stress/test_ac_onoff.py",
            "name": "test_ac_onoff_via_relay",
            "markers": [],
            "case_type": "stress",
            "required_params": ["ac_onoff:cycle_count", "ac_onoff:power_off_sec"],
            "required_param_groups": [],
            "required_equipment": ["relay"],
            "android_case_id": "",
        },
        {
            "nodeid": "testing/tests/android/common/system/test_cpu_frequency.py::test_cpu_frequency_switching",
            "file": "testing/tests/android/common/system/test_cpu_frequency.py",
            "name": "test_cpu_frequency_switching",
            "markers": [],
            "case_type": "default",
            "required_params": ["cpu_frequency:frequencies"],
            "required_param_groups": [],
            "required_equipment": [],
            "android_case_id": "",
        },
        {
            "nodeid": "testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client",
            "file": "testing/tests/android/common/system/test_emmc_rw.py",
            "name": "test_emmc_rw_via_android_client",
            "markers": [],
            "case_type": "default",
            "required_params": ["emmc_rw:loop_count", "emmc_rw:work_dir"],
            "required_param_groups": [],
            "required_equipment": [],
            "android_case_id": "",
        },
    ]
    bridge._rebuild_case_indexes()

    try:
        helper.current = "zh_CN"
        ac_fields = bridge.caseParamFields("testing/tests/android/stress/test_ac_onoff.py::test_ac_onoff_via_relay")
        cpu_fields = bridge.caseParamFields("testing/tests/android/common/system/test_cpu_frequency.py::test_cpu_frequency_switching")
        emmc_fields = bridge.caseParamFields("testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client")

        assert [field["label"] for field in ac_fields] == ["\u5faa\u73af\u6b21\u6570", "\u4e0b\u7535\u65f6\u957f\uff08\u79d2\uff09"]
        assert [field["label_source"] for field in ac_fields] == ["fixed", "fixed"]
        assert [field["description_source"] for field in ac_fields] == ["fixed", "fixed"]
        assert cpu_fields[0]["label"] == "CPU \u9891\u70b9"
        assert cpu_fields[0]["enum_values_source"] == "dynamic"
        assert emmc_fields[0]["label"] == "\u5faa\u73af\u6b21\u6570"
        assert emmc_fields[1]["label"] == "\u5de5\u4f5c\u76ee\u5f55"
        assert ac_fields[0]["scope_label"] == "\u6bcf\u4e2a\u7528\u4f8b\u72ec\u7acb"
        assert ac_fields[0]["scope_label_source"] == "fixed"

        helper.current = "en_US"
        ac_fields = bridge.caseParamFields("testing/tests/android/stress/test_ac_onoff.py::test_ac_onoff_via_relay")
        cpu_fields = bridge.caseParamFields("testing/tests/android/common/system/test_cpu_frequency.py::test_cpu_frequency_switching")
        emmc_fields = bridge.caseParamFields("testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client")

        assert [field["label"] for field in ac_fields] == ["Cycle count", "Power off seconds"]
        assert cpu_fields[0]["label"] == "CPU frequencies"
        assert emmc_fields[0]["label"] == "Loop Count"
        assert emmc_fields[1]["label"] == "Working Directory"
        assert ac_fields[0]["scope_label"] == "Per Case"
        assert ac_fields[0]["label_source"] == "fixed"
    finally:
        helper.current = previous_language
