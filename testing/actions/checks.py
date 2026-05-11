from __future__ import annotations

import re
from typing import Any

from .core import ActionContext, ActionDefinition, ActionPlanContext, ActionPlanDecision, register_action


_DISABLED_CHOICE_VALUES = {"", "none", "null", "no", "disabled", "off", "无"}


def _param(context: ActionContext, name: str, default: Any = "") -> Any:
    if name in context.extra:
        return context.extra[name]
    if name in context.params:
        return context.params[name]
    if context.case_id:
        return context.params.get(f"{context.case_id}:{name}", default)
    return default


def _plan_param(context: ActionPlanContext, name: str, default: Any = "") -> Any:
    if name in context.params:
        return context.params[name]
    if context.case_id:
        return context.params.get(f"{context.case_id}:{name}", default)
    return default


def _choice_enabled(value: Any) -> bool:
    return str(value or "").strip().lower() not in _DISABLED_CHOICE_VALUES


def _network_ping_plan(context: ActionPlanContext) -> ActionPlanDecision:
    target = _plan_param(context, "ping_target", "")
    enabled = _choice_enabled(target)
    return ActionPlanDecision(enabled, "ping_target configured" if enabled else "ping_target empty")


def _bluetooth_verify_target_plan(context: ActionPlanContext) -> ActionPlanDecision:
    target = _plan_param(context, "bt_target", "")
    enabled = _choice_enabled(target)
    return ActionPlanDecision(enabled, "bt_target configured" if enabled else "bt_target disabled by user config")


def _network_ping(context: ActionContext) -> bool:
    if context.dut is None:
        raise RuntimeError("network.ping requires a DUT in ActionContext.")
    target = str(_param(context, "target", _param(context, "ping_target", "")) or "").strip()
    if not target:
        raise ValueError("network.ping requires target or ping_target.")
    return bool(context.dut.ping(hostname=target))


def _bluetooth_verify_target(context: ActionContext) -> bool:
    if context.dut is None:
        raise RuntimeError("bluetooth.verify_target requires a DUT in ActionContext.")
    target = str(_param(context, "target", _param(context, "bt_target", "")) or "").strip()
    if not target:
        raise ValueError("bluetooth.verify_target requires target or bt_target.")
    match = re.search(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})", target)
    if not match:
        raise ValueError(f"Invalid Bluetooth target format: {target}")
    target_mac = match.group(1).upper()
    observed = [
        str(item).strip().upper()
        for item in context.dut.get_connected_bluetooth_mac_addresses()
        if str(item).strip()
    ]
    return any(_bluetooth_address_matches(target_mac, item) for item in observed)


def _bluetooth_address_matches(target_mac: str, observed_mac: str) -> bool:
    if observed_mac.upper() == target_mac.upper():
        return True
    target_parts = target_mac.upper().split(":")
    observed_parts = observed_mac.upper().split(":")
    if len(target_parts) != 6 or len(observed_parts) != 6:
        return False
    return observed_parts[:4] == ["XX", "XX", "XX", "XX"] and observed_parts[-2:] == target_parts[-2:]


register_action(
    ActionDefinition(
        definition_id="network.ping",
        title="Ping target",
        kind="check",
        executor=_network_ping,
        planner=_network_ping_plan,
    )
)
register_action(
    ActionDefinition(
        definition_id="bluetooth.verify_target",
        title="Verify Bluetooth target",
        kind="check",
        executor=_bluetooth_verify_target,
        planner=_bluetooth_verify_target_plan,
    )
)
