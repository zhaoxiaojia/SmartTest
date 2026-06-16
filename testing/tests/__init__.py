from __future__ import annotations

from typing import Any

from tools.param_conversion import to_int
from tools.param_conversion import wire_string
from testing.steps.definitions import action_step_enabled


_REPEAT_MARKERS = ("cycle", "loop")


def build_declared_case_plan(
    declaration: dict[str, Any],
    *,
    case_parameters: dict[str, Any],
    include_config_disabled: bool = False,
) -> list[dict[str, Any]]:
    case_id = str(declaration.get("case_id", "") or "").strip()
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
        step["title"] = resolve_title_placeholders(str(step.get("title", "") or ""), params)
        steps.append(step)
    return expand_repeated_steps(steps, case_id=case_id, params=params)


def expand_repeated_steps(steps: list[dict[str, Any]], *, case_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    index = 0
    while index < len(steps):
        marker = _repeat_marker(steps[index])
        if marker is None:
            expanded.append(steps[index])
            index += 1
            continue
        block_start = index
        while index < len(steps) and _repeat_marker(steps[index]) == marker:
            index += 1
        block = steps[block_start:index]
        total = _repeat_count(marker=marker, case_id=case_id, step=block[0], params=params)
        if total is None:
            expanded.extend(block)
            continue
        for repeat_index in range(1, total + 1):
            expanded.extend(_expand_repeated_step(step, marker=marker, index=repeat_index, total=total) for step in block)
    return _expand_default_cycle_steps(expanded, case_id=case_id, params=params)


def _expand_default_cycle_steps(steps: list[dict[str, Any]], *, case_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    if not steps:
        return steps
    if any(_repeat_marker(step) == "cycle" for step in steps):
        return steps
    total = _default_cycle_count(case_id=case_id, params=params)
    if total <= 0:
        return steps

    expanded: list[dict[str, Any]] = []
    cycle_steps = [step for step in steps if _should_default_cycle_expand(step)]
    if not cycle_steps:
        return steps
    cycle_ids = {id(step) for step in cycle_steps}
    for step in steps:
        if id(step) not in cycle_ids:
            expanded.append(step)
            continue
        for cycle_index in range(1, total + 1):
            expanded.append(_wrap_default_cycle_step(step, index=cycle_index, total=total))
    return expanded


def _repeat_marker(step: dict[str, Any]) -> str | None:
    step_id = str(step.get("id", "") or "")
    parts = step_id.split(".")
    if len(parts) < 3:
        return None
    for marker in _REPEAT_MARKERS:
        if marker not in parts:
            continue
        marker_index = parts.index(marker)
        if marker_index >= len(parts) - 1:
            return None
        return marker
    return None


def _expand_repeated_step(step: dict[str, Any], *, marker: str, index: int, total: int) -> dict[str, Any]:
    parts = str(step.get("id", "") or "").split(".")
    marker_index = parts.index(marker)
    item = dict(step)
    item["id"] = ".".join([*parts[: marker_index + 1], str(index), *parts[marker_index + 1 :]])
    item["title"] = _repeat_title(str(step.get("title", "") or ""), marker=marker, index=index, total=total)
    return item


def _wrap_default_cycle_step(step: dict[str, Any], *, index: int, total: int) -> dict[str, Any]:
    item = dict(step)
    raw_id = str(step.get("id", "") or "step")
    item["id"] = f"{raw_id}.cycle.{index}"
    item["title"] = _repeat_title(str(step.get("title", "") or raw_id), marker="cycle", index=index, total=total)
    return item


def _repeat_count(*, marker: str, case_id: str, step: dict[str, Any], params: dict[str, Any]) -> int | None:
    count_names = [f"{marker}_count"]
    if marker == "cycle":
        count_names.append("loop_count")
    keys = []
    step_prefix = _repeat_prefix(step, marker=marker)
    for count_name in count_names:
        if case_id:
            keys.append(f"{case_id}:{count_name}")
        if step_prefix:
            keys.append(f"{step_prefix}:{count_name}")
    key = next((candidate for candidate in keys if candidate in params), "")
    if not key:
        return None
    return max(to_int(params.get(key, 1), default=1), 1)


def _default_cycle_count(*, case_id: str, params: dict[str, Any]) -> int:
    keys: list[str] = []
    if case_id:
        keys.extend([f"{case_id}:cycle_count", f"{case_id}:loop_count"])
    key = next((candidate for candidate in keys if candidate in params), "")
    if not key:
        return 1
    return max(to_int(params.get(key, 1), default=1), 1)


def _repeat_prefix(step: dict[str, Any], *, marker: str) -> str:
    parts = str(step.get("id", "") or "").split(".")
    return ".".join(parts[: parts.index(marker)]) if marker in parts else ""


def _should_default_cycle_expand(step: dict[str, Any]) -> bool:
    kind = str(step.get("kind", "") or "").strip().lower()
    if kind in {"setup", "teardown", "case"}:
        return False
    step_id = str(step.get("id", "") or "")
    return _repeat_marker({"id": step_id}) is None


def _repeat_title(title: str, *, marker: str, index: int, total: int) -> str:
    label = marker.capitalize()
    prefix = f"{label}:"
    if title.startswith(prefix):
        return f"{label} {index}/{total}:{title[len(prefix):]}"
    return f"{label} {index}/{total}: {title}"


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


def resolve_title_placeholders(title: str, params: dict[str, Any]) -> str:
    resolved = str(title or "")
    for key, value in params.items():
        formatted = wire_string(value)
        resolved = resolved.replace("{" + str(key) + "}", formatted)
        short = str(key).split(":", 1)[-1]
        resolved = resolved.replace("{" + short + "}", formatted)
    return resolved
