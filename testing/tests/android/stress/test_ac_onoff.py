from __future__ import annotations

import time
from typing import Any

import pytest

from testing.params.runtime import runtime_params
from testing.runtime.config import current_dut_serial
from testing.runtime.equipment import test_equipment as runtime_test_equipment
from testing.runtime.steps import step, step_log
from testing.steps.definitions import ActionContext, get_action


pytestmark = [
    pytest.mark.case_type("stress"),
    pytest.mark.requires_equipment("relay"),
]

CASE_ID = "ac_onoff"

SMARTTEST_CASE_PLAN = {
    "case_id": CASE_ID,
    "steps": [
        {
            "id": "ac_onoff.prepare_relay",
            "title": "Prepare relay",
            "kind": "setup",
            "definition_id": "relay.prepare",
            "expected": "Configured environment relay is available.",
        },
        {
            "id": "ac_onoff.cycle.power_off",
            "title": "Cycle: power off relay",
            "kind": "step",
            "definition_id": "relay.power_off",
            "expected": "Relay powers off the DUT.",
        },
        {
            "id": "ac_onoff.cycle.power_on",
            "title": "Cycle: power on relay",
            "kind": "step",
            "definition_id": "relay.power_on",
            "expected": "Relay powers on the DUT.",
        },
        {
            "id": "ac_onoff.cycle.wait_resume",
            "title": "Cycle: wait for DUT resume {ac_onoff:power_on_wait_sec}s",
            "kind": "step",
            "definition_id": "power.wait_resume",
            "expected": "DUT has enough time to boot before checkpoints.",
        },
        {
            "id": "ac_onoff.cycle.ping",
            "title": "Cycle: ping {ac_onoff:ping_target}",
            "kind": "check",
            "definition_id": "network.ping",
            "expected": "DUT can reach the configured ping target after AC power on.",
        },
        {
            "id": "ac_onoff.cycle.bluetooth",
            "title": "Cycle: verify Bluetooth target",
            "kind": "check",
            "definition_id": "bluetooth.verify_target",
            "expected": "DUT reports the configured Bluetooth target connected after AC power on.",
        },
    ],
}


@pytest.mark.requires_params(
    "ac_onoff:cycle_count",
    "ac_onoff:power_off_sec",
    "ac_onoff:power_off_step_sec",
    "ac_onoff:power_on_wait_sec",
    "ac_onoff:power_on_wait_step_sec",
    "ac_onoff:ping_target",
    "ac_onoff:bt_target",
)
def test_ac_onoff_via_relay(request):
    params = _case_params(request)
    relay = None
    with step(
        "Prepare relay",
        phase="setup",
        kind="setup",
        definition_id="relay.prepare",
        expected="Configured environment relay is available.",
        step_id="ac_onoff.prepare_relay",
    ):
        relay = runtime_test_equipment().relay
        step_log(f"relay={relay.__class__.__name__}")

    dut = _checkpoint_dut(params)
    total = int(params["ac_onoff:cycle_count"])
    for index in range(1, total + 1):
        power_off_sec = _cycle_seconds(
            params["ac_onoff:power_off_sec"],
            params["ac_onoff:power_off_step_sec"],
            index,
        )
        power_on_wait_sec = _cycle_seconds(
            params["ac_onoff:power_on_wait_sec"],
            params["ac_onoff:power_on_wait_step_sec"],
            index,
        )
        with step(
            f"Cycle {index}/{total}: power off relay",
            kind="step",
            definition_id="relay.power_off",
            expected="Relay powers off the DUT.",
            step_id=f"ac_onoff.cycle.{index}.power_off",
        ):
            _relay_power(relay, "power_off")
            time.sleep(power_off_sec)

        with step(
            f"Cycle {index}/{total}: power on relay",
            kind="step",
            definition_id="relay.power_on",
            expected="Relay powers on the DUT.",
            step_id=f"ac_onoff.cycle.{index}.power_on",
        ):
            _relay_power(relay, "power_on")

        with step(
            f"Cycle {index}/{total}: wait for DUT resume",
            kind="step",
            definition_id="power.wait_resume",
            expected="DUT has enough time to boot before checkpoints.",
            step_id=f"ac_onoff.cycle.{index}.wait_resume",
        ):
            time.sleep(power_on_wait_sec)

        if str(params.get("ac_onoff:ping_target", "") or "").strip():
            _run_dut_check(
                "network.ping",
                params=params,
                dut=dut,
                request=request,
                index=index,
                total=total,
            )
        if str(params.get("ac_onoff:bt_target", "") or "").strip():
            _run_dut_check(
                "bluetooth.verify_target",
                params=params,
                dut=dut,
                request=request,
                index=index,
                total=total,
            )


def _case_params(request) -> dict[str, Any]:
    params = runtime_params()
    nodeid = request.node.nodeid
    return {
        "ac_onoff:cycle_count": max(params.get_int(nodeid, "ac_onoff:cycle_count", 20), 1),
        "ac_onoff:power_off_sec": max(params.get_int(nodeid, "ac_onoff:power_off_sec", 5), 0),
        "ac_onoff:power_off_step_sec": params.get_float(nodeid, "ac_onoff:power_off_step_sec", 0.0),
        "ac_onoff:power_on_wait_sec": max(params.get_int(nodeid, "ac_onoff:power_on_wait_sec", 60), 0),
        "ac_onoff:power_on_wait_step_sec": params.get_float(nodeid, "ac_onoff:power_on_wait_step_sec", 0.0),
        "ac_onoff:ping_target": params.get_str(nodeid, "ac_onoff:ping_target", ""),
        "ac_onoff:bt_target": params.get_str(nodeid, "ac_onoff:bt_target", ""),
    }


def _cycle_seconds(base: Any, step_seconds: Any, index: int) -> float:
    return max(float(base) + (max(int(index), 1) - 1) * float(step_seconds), 0.0)


def _checkpoint_dut(params: dict[str, Any]):
    if not str(params.get("ac_onoff:ping_target", "") or "").strip() and not str(
        params.get("ac_onoff:bt_target", "") or ""
    ).strip():
        return None
    serial = current_dut_serial()
    if not serial:
        pytest.fail("Select a DUT before running AC on/off checkpoints.")
    from testing.tool.dut_tool.duts.android import android

    return android(serialnumber=serial)


def _relay_power(relay: Any, direction: str) -> None:
    action = str(direction or "").strip().lower()
    if hasattr(relay, "switch") and getattr(relay, "port", None):
        ip, port = relay.port
        status = 2 if action == "power_off" else 1
        step_log(f"snmp_pdu switch ip={ip} port={port} status={status} direction={action}")
        relay.switch(ip, port, status)
        return
    relay.pulse(action)


def _run_dut_check(
    definition_id: str,
    *,
    params: dict[str, Any],
    dut: Any,
    request: Any,
    index: int,
    total: int,
) -> None:
    action = get_action(definition_id)
    title = "ping target" if definition_id == "network.ping" else "verify Bluetooth target"
    with step(
        f"Cycle {index}/{total}: {title}",
        kind="check",
        definition_id=definition_id,
        expected=action.expected,
        step_id=f"ac_onoff.cycle.{index}.{definition_id.replace('.', '_')}",
    ):
        if action.executor is None:
            raise RuntimeError(f"SmartTest action has no executor: {definition_id}")
        context = ActionContext(
            case_id=CASE_ID,
            params=params,
            trigger=request.node.nodeid,
            dut=dut,
            request=request,
        )
        result = action.executor(context)
        if action.kind == "check" and result is False:
            raise AssertionError(f"Check failed: {action.title}")
