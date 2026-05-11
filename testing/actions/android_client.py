from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from testing.runner.android_client import trigger_android_client_case
from testing.runtime import step_log

from .core import ActionContext, ActionDefinition, action_plan, register_action, run_action


def _prepare_android_client_request(context: ActionContext) -> str:
    summary = ", ".join(f"{key.split(':', 1)[-1]}={value}" for key, value in context.params.items())
    step_log(summary)
    return summary


def _trigger_android_client_case(context: ActionContext):
    result = trigger_android_client_case(
        case_id=context.case_id,
        params=context.params,
        trigger=context.trigger,
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if stdout:
        step_log(stdout)
    if stderr:
        step_log(stderr, level="warning")
    return result


register_action(
    ActionDefinition(
        definition_id="android_client.prepare_request",
        title="Prepare android_client request",
        kind="setup",
        executor=_prepare_android_client_request,
    )
)
register_action(
    ActionDefinition(
        definition_id="android_client.trigger_case",
        title="Trigger android_client case",
        kind="step",
        executor=_trigger_android_client_case,
    )
)


def android_client_case_plan(
    case_id: str,
    runtime_definition_ids: list[str] | None = None,
    *,
    prepare_definition_id: str = "android_client.prepare_request",
    trigger_definition_id: str = "android_client.trigger_case",
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "steps": [
            *action_plan([prepare_definition_id, trigger_definition_id]),
            *action_plan(runtime_definition_ids or []),
        ],
    }


def run_android_client_case(
    *,
    case_id: str,
    params: Mapping[str, Any],
    trigger: str,
    prepare_definition_id: str = "android_client.prepare_request",
    trigger_definition_id: str = "android_client.trigger_case",
) -> Any:
    context = ActionContext(case_id=case_id, params=params, trigger=trigger)
    run_action(prepare_definition_id, context, executor=_prepare_android_client_request)
    return run_action(trigger_definition_id, context, executor=_trigger_android_client_case)
