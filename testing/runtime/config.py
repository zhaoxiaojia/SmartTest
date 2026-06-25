from __future__ import annotations

from typing import Any

from testing.test_context import RuntimeConfig, smarttest_context


def runtime_config() -> RuntimeConfig:
    return smarttest_context().runtime_config()


def current_dut_serial() -> str:
    return runtime_config().dut_serial


def equipment_config() -> dict[str, Any]:
    return dict(runtime_config().equipment)
