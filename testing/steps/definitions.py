from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import re
from typing import Any

from testing.runtime.steps import step_log


ActionExecutor = Callable[["ActionContext"], Any]
ActionPlanner = Callable[["ActionPlanContext"], "ActionPlanDecision"]


@dataclass(frozen=True)
class ActionContext:
    case_id: str
    params: Mapping[str, Any]
    trigger: str = ""
    dut: Any = None
    request: Any = None
    extra: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ActionPlanContext:
    case_id: str = ""
    params: Mapping[str, Any] | None = None
    step: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ActionPlanDecision:
    include: bool
    reason: str = ""


@dataclass(frozen=True)
class ActionDefinition:
    definition_id: str
    title: str
    kind: str = "step"
    expected: str = ""
    executor: ActionExecutor | None = None
    planner: ActionPlanner | None = None
    plan_id: str = ""

    def plan_decision(self, context: ActionPlanContext | None = None) -> ActionPlanDecision:
        if self.planner is None:
            return ActionPlanDecision(True, "no planner")
        return self.planner(context or ActionPlanContext())

    def to_step(self, context: ActionPlanContext | None = None) -> dict[str, Any] | None:
        plan_context = context or ActionPlanContext()
        decision = self.plan_decision(plan_context)
        step_log(
            "[steps.plan.decision] "
            f"definition_id={self.definition_id} include={decision.include} reason={decision.reason}"
        )
        if not decision.include:
            return None
        return {
            "id": self.plan_id or self.definition_id,
            "title": self.title,
            "kind": self.kind,
            "definition_id": self.definition_id,
            "expected": self.expected,
        }


_DEFINITION_REGISTRY: dict[str, ActionDefinition] = {}


def register_action(definition: ActionDefinition) -> ActionDefinition:
    key = _normalize_definition_id(definition.definition_id)
    if not key:
        raise ValueError("definition_id is required.")
    existing = _DEFINITION_REGISTRY.get(key)
    if existing is not None and existing != definition:
        raise ValueError(f"Duplicate action definition: {definition.definition_id}")
    _DEFINITION_REGISTRY[key] = definition
    return definition


def get_action(definition_id: str) -> ActionDefinition:
    key = _normalize_definition_id(definition_id)
    try:
        return _DEFINITION_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"Unknown SmartTest action definition: {definition_id}") from exc


def action_plan(definition_ids: Iterable[str], *, context: ActionPlanContext | None = None) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for definition_id in definition_ids:
        definition = get_action(definition_id)
        step = definition.to_step(context)
        if step is not None:
            steps.append(step)
    return steps


def action_step_enabled(step: Mapping[str, Any], *, case_id: str, params: Mapping[str, Any]) -> bool | None:
    definition_id = str(step.get("definition_id", "") or "").strip()
    if not definition_id:
        return None
    definition = _DEFINITION_REGISTRY.get(_normalize_definition_id(definition_id))
    if definition is None:
        return None
    decision = definition.plan_decision(
        ActionPlanContext(case_id=case_id, params=params, step=step)
    )
    step_log(
        "[steps.plan.decision] "
        f"case_id={case_id} definition_id={definition_id} include={decision.include} reason={decision.reason}"
    )
    return decision.include


def run_action(definition_id: str, context: ActionContext, *, executor: ActionExecutor | None = None) -> Any:
    definition = get_action(definition_id)
    selected_executor = executor or definition.executor
    if selected_executor is None:
        raise RuntimeError(f"SmartTest action has no executor: {definition_id}")
    return selected_executor(context)


def _normalize_definition_id(value: str) -> str:
    return str(value or "").strip()


_DISABLED_CHOICE_VALUES = {"", "none", "null", "no", "disabled", "off", "鏃?"}


def _param(context: ActionContext, name: str, default: Any = "") -> Any:
    if context.extra and name in context.extra:
        return context.extra[name]
    if name in context.params:
        return context.params[name]
    if context.case_id:
        return context.params.get(f"{context.case_id}:{name}", default)
    return default


def _plan_param(context: ActionPlanContext, name: str, default: Any = "") -> Any:
    params = context.params or {}
    if name in params:
        return params[name]
    if context.case_id:
        return params.get(f"{context.case_id}:{name}", default)
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
        for item in context.dut.stability.get_connected_bluetooth_mac_addresses()
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
register_action(
    ActionDefinition(
        definition_id="android_client.prepare_request",
        title="Prepare android_client request",
        kind="setup",
    )
)
register_action(
    ActionDefinition(
        definition_id="android_client.trigger_case",
        title="Trigger android_client case",
        kind="step",
    )
)
for _definition in (
    ActionDefinition("power.auto_reboot.prepare", "Prepare auto reboot request", "setup", plan_id="auto_reboot.prepare"),
    ActionDefinition("power.reboot", "Cycle: reboot DUT", "step", plan_id="auto_reboot.cycle.reboot"),
    ActionDefinition("power.wait_resume", "Cycle: wait for DUT resume", "step", plan_id="auto_reboot.cycle.wait_resume"),
    ActionDefinition(
        "power.wait_interval",
        "Cycle: wait interval {auto_reboot:interval_sec}s",
        "step",
        plan_id="auto_reboot.cycle.wait_interval",
    ),
    ActionDefinition(
        "power.capture_radio_state",
        "Cycle: capture radio state",
        "check",
        plan_id="auto_reboot.cycle.capture_radio_state",
    ),
    ActionDefinition("storage.emmc.prepare_request", "Prepare eMMC read/write request", "step"),
    ActionDefinition("storage.emmc.trigger_execution", "Trigger eMMC read/write execution", "step"),
    ActionDefinition("storage.emmc.copy_file", "Cycle: copy file", "step", plan_id="emmc_rw.cycle.copy_file"),
    ActionDefinition("storage.emmc.read_file", "Cycle: read back file", "step", plan_id="emmc_rw.cycle.read_file"),
    ActionDefinition("storage.emmc.cmp_file", "Cycle: compare file", "check", plan_id="emmc_rw.cycle.cmp_file"),
):
    register_action(_definition)
