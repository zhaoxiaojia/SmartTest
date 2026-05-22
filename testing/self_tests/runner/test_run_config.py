from __future__ import annotations

from pathlib import Path

from testing.runner.config import build_run_config_from_state, resolve_dut_serial
from testing.state.models import SelectedCase, TestPageState as SmartTestPageState


def test_resolve_dut_serial_keeps_selected_connected_device() -> None:
    assert resolve_dut_serial("XYZ789", devices=["ABC123", "XYZ789"]) == "XYZ789"


def test_resolve_dut_serial_uses_only_device_when_saved_value_is_stale() -> None:
    assert resolve_dut_serial("OLD", devices=["ABC123"]) == "ABC123"


def test_resolve_dut_serial_omits_single_unsafe_device_serial() -> None:
    assert resolve_dut_serial("OLD", devices=["0099360090052090260214801F41D0F脗"]) is None


def test_build_run_config_from_state_carries_equipment_config() -> None:
    state = SmartTestPageState(
        selected=[SelectedCase("testing/tests/example.py::test_case")],
        case_configs={"testing/tests/example.py::test_case": {"duration": 3}},
        global_context={
            "dut": "ABC123",
            "equipment": {
                "relay": {"type": "usb_relay", "port": "COM4"},
                "router": {"type": "ASUS-AX86U", "address": "192.168.50.1"},
            },
        },
    )

    run_config, diagnostics = build_run_config_from_state(
        root_dir=Path.cwd(),
        state=state,
        device_lister=lambda: ["ABC123"],
    )

    assert diagnostics == []
    assert run_config.nodeids == ["testing/tests/example.py::test_case"]
    assert run_config.case_configs == {"testing/tests/example.py::test_case": {"duration": 3}}
    assert run_config.dut_serial == "ABC123"
    assert run_config.equipment["relay"]["port"] == "COM4"
