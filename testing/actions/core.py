from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from testing.runtime import step as runtime_step


ActionExecutor = Callable[["ActionContext"], Any]
ActionPlanner = Callable[["ActionPlanContext"], "ActionPlanDecision | bool"]


@dataclass(frozen=True)
class ActionContext:
    case_id: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)
    trigger: str = ""
    dut: Any = None
    request: Any = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionPlanContext:
    case_id: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)
    step: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionPlanDecision:
    include: bool
    reason: str = ""


@dataclass(frozen=True)
class ActionDefinition:
    definition_id: str
    title: str
    kind: str
    executor: ActionExecutor | None = None
    planner: ActionPlanner | None = None
    expected: Any = ""
    phase: str = "call"
    when_param: str = ""
    plan_id: str = ""

    def plan_step(self, *, step_id: str | None = None) -> dict[str, Any]:
        return {
            "id": step_id or self.plan_id or self.definition_id,
            "title": self.title,
            "kind": self.kind,
            "definition_id": self.definition_id,
            "expected": self.expected,
            **({"when_param": self.when_param} if self.when_param else {}),
        }

    def plan_decision(self, context: ActionPlanContext) -> ActionPlanDecision:
        if self.planner is None:
            return ActionPlanDecision(True, "no planner")
        decision = self.planner(context)
        if isinstance(decision, ActionPlanDecision):
            return decision
        return ActionPlanDecision(bool(decision), "planner returned bool")


_ACTION_REGISTRY: dict[str, ActionDefinition] = {}


def register_action(definition: ActionDefinition) -> ActionDefinition:
    key = str(definition.definition_id).strip()
    if not key:
        raise ValueError("Action definition_id cannot be empty.")
    existing = _ACTION_REGISTRY.get(key)
    if existing is not None and existing != definition:
        raise ValueError(f"Action definition_id already registered: {key}")
    _ACTION_REGISTRY[key] = definition
    return definition


def get_action(definition_id: str) -> ActionDefinition:
    key = str(definition_id).strip()
    try:
        return _ACTION_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"Unknown SmartTest action: {key}") from exc


def action_plan(definition_ids: Iterable[str], *, context: ActionPlanContext | None = None) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    plan_context = context or ActionPlanContext()
    for definition_id in definition_ids:
        definition = get_action(definition_id)
        decision = definition.plan_decision(plan_context)
        print(
            "[actions.plan.decision] "
            f"definition_id={definition.definition_id} include={decision.include} reason={decision.reason}"
        )
        if decision.include:
            steps.append(definition.plan_step())
    return steps


def action_step_enabled(step: Mapping[str, Any], *, case_id: str, params: Mapping[str, Any]) -> bool | None:
    definition_id = str(step.get("definition_id", "") or "").strip()
    if not definition_id:
        return None
    definition = _ACTION_REGISTRY.get(definition_id)
    if definition is None:
        return None
    decision = definition.plan_decision(
        ActionPlanContext(case_id=case_id, params=dict(params), step=dict(step))
    )
    print(
        "[actions.plan.decision] "
        f"definition_id={definition.definition_id} include={decision.include} reason={decision.reason}"
    )
    return decision.include


def run_action(definition_id: str, context: ActionContext, *, executor: ActionExecutor | None = None) -> Any:
    definition = get_action(definition_id)
    selected_executor = executor or definition.executor
    if selected_executor is None:
        raise RuntimeError(f"SmartTest action has no executor: {definition_id}")
    with runtime_step(
        definition.title,
        phase=definition.phase,
        kind=definition.kind,
        definition_id=definition.definition_id,
        params=dict(context.params),
        expected=definition.expected,
    ):
        result = selected_executor(context)
        if definition.kind == "check" and result is False:
            raise AssertionError(f"Check failed: {definition.title}")
        return result
