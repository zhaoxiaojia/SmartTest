from __future__ import annotations

from typing import Any

from ui import jsonTool

from testing.steps.definitions import action_step_enabled


def build_declared_case_plan(
    declaration: dict[str, Any],
    *,
    nodeid: str,
    include_config_disabled: bool = False,
) -> list[dict[str, Any]]:
    case_id = str(declaration.get("case_id", "") or "").strip()
    case_parameters = _case_parameters_from_json(nodeid)
    params = {
        str(key): value
        for key, value in case_parameters.items()
        if not case_id or str(key).startswith(f"{case_id}:")
    }
    steps: list[dict[str, Any]] = []
    raw_steps = declaration.get("steps", [])
    if not isinstance(raw_steps, list):
        return steps
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            continue
        if not include_config_disabled:
            action_enabled = action_step_enabled(raw_step, case_id=case_id, params=params)
            if action_enabled is False:
                continue
            if action_enabled is None and not declared_step_enabled(raw_step, params):
                continue
        step = dict(raw_step)
        step["params"] = dict(params)
        step["title"] = _resolve_title_placeholders(str(step.get("title", "") or ""), params)
        steps.append(step)
    return steps


def _case_parameters_from_json(nodeid: str) -> dict[str, Any]:
    values = jsonTool.get_json_value("test_page_state.json", ["case_parameters", str(nodeid)], {})
    return dict(values) if isinstance(values, dict) else {}


def declared_step_enabled(step: dict[str, Any], params: dict[str, Any]) -> bool:
    when_param = str(step.get("when_param", "") or "").strip()
    if when_param:
        return str(params.get(when_param, "") or "").strip() != ""
    condition = step.get("when")
    if not isinstance(condition, dict):
        return True
    param = str(condition.get("param", "") or "").strip()
    if not param:
        return True
    value = str(params.get(param, "") or "").strip()
    if bool(condition.get("not_empty", False)):
        return value != ""
    if "equals" in condition:
        return value == str(condition.get("equals", ""))
    return True


def _resolve_title_placeholders(title: str, params: dict[str, Any]) -> str:
    resolved = str(title or "")
    for key, value in params.items():
        formatted = _format_placeholder_value(value)
        resolved = resolved.replace("{" + str(key) + "}", formatted)
        short = str(key).split(":", 1)[-1]
        resolved = resolved.replace("{" + short + "}", formatted)
    return resolved


def _format_placeholder_value(value: Any) -> str:
    text = str(value)
    try:
        numeric = float(text)
    except ValueError:
        return text
    if numeric.is_integer():
        return str(int(numeric))
    return text
