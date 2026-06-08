from __future__ import annotations

import json

from testing.runner.config import RUN_CONFIG_ENV
from testing.runtime.config import current_dut_serial, equipment_config, runtime_config


def test_runtime_config_reads_unified_run_config(monkeypatch) -> None:
    monkeypatch.setenv(
        RUN_CONFIG_ENV,
        json.dumps(
            {
                "nodeids": ["testing/tests/example.py::test_case"],
                "dut_serial": "ABC123",
                "equipment": {"relay": {"type": "usb_relay", "port": "COM4"}},
            }
        ),
    )
    monkeypatch.setenv("SMARTTEST_ADB_SERIAL", "LEGACY")

    config = runtime_config()

    assert config.dut_serial == "ABC123"
    assert current_dut_serial() == "ABC123"
    assert equipment_config()["relay"]["port"] == "COM4"
