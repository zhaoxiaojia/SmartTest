from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from testing.cases.catalog import load_runtime_test_catalog
from testing.test_context import smarttest_context
from testing.steps.definitions import ActionPlanContext, get_action
from testing.tests import build_declared_case_plan, declared_step_enabled, expand_repeated_steps, resolve_title_placeholders


def build_step_plan(
    *,
    root_dir: Path,
    nodeid: str,
    prefer_catalog: bool = True,
    include_config_disabled: bool = False,
) -> list[dict[str, Any]]:
    case_parameters = smarttest_context().params.case_values(nodeid)
    use_catalog_plan = prefer_catalog
    if use_catalog_plan:
        catalog_plan = _catalog_step_plan(root_dir=root_dir, nodeid=nodeid, case_parameters=case_parameters)
        if catalog_plan:
            _trace_plan("catalog", nodeid=nodeid, steps=catalog_plan, case_parameters=case_parameters)
            return _remove_case_execute_summary_steps(catalog_plan)
    declared_plan = _load_declared_plan(
        root_dir=root_dir,
        nodeid=nodeid,
        case_parameters=case_parameters,
        include_config_disabled=include_config_disabled,
    )
    if not declared_plan:
        result = _fallback_plan()
        _trace_plan("fallback", nodeid=nodeid, steps=result, case_parameters=case_parameters)
        return result
    normalized = [_normalize_step(item, index=index) for index, item in enumerate(declared_plan)]
    result = _remove_case_execute_summary_steps(normalized)
    _trace_plan("declared", nodeid=nodeid, steps=result, case_parameters=case_parameters)
    return result


def _catalog_step_plan(*, root_dir: Path, nodeid: str, case_parameters: dict[str, Any]) -> list[dict[str, Any]]:
    for row in load_runtime_test_catalog(root_dir=root_dir):
        if str(row.get("nodeid", "") or "").strip() != nodeid:
            continue
        raw_steps = row.get("initial_step_plan")
        if not isinstance(raw_steps, list):
            return []
        resolved = [_normalize_step(dict(item), index=index) for index, item in enumerate(raw_steps) if isinstance(item, dict)]
        if not resolved:
            return []
        for item in resolved:
            item["title"] = resolve_title_placeholders(str(item.get("title", "") or ""), case_parameters)
        case_id = str(row.get("android_case_id", "") or "").strip()
        resolved = [item for item in resolved if _step_enabled(item, case_id=case_id, case_parameters=case_parameters)]
        resolved = expand_repeated_steps(resolved, case_id=case_id, params=case_parameters)
        return _remove_case_execute_summary_steps(resolved)
    return []


def _step_enabled(item: dict[str, Any], *, case_id: str, case_parameters: dict[str, Any]) -> bool:
    definition_id = str(item.get("definition_id", "") or "").strip()
    if definition_id:
        try:
            action = get_action(definition_id)
        except KeyError:
            pass
        else:
            decision = action.plan_decision(
                ActionPlanContext(case_id=case_id, params=case_parameters, step=dict(item))
            )
            return decision.include
    return declared_step_enabled(item, case_parameters)


def _load_declared_plan(
    *,
    root_dir: Path,
    nodeid: str,
    case_parameters: dict[str, Any],
    include_config_disabled: bool,
) -> list[dict[str, Any]]:
    path_text = nodeid.split("::", 1)[0].strip()
    if not path_text:
        return []
    module_path = (root_dir / path_text).resolve()
    if not module_path.exists() or module_path.suffix != ".py":
        return []
    module_name = "smarttest_step_plan_" + str(abs(hash(str(module_path))))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    declaration = getattr(module, "SMARTTEST_CASE_PLAN", None)
    if isinstance(declaration, dict):
        return build_declared_case_plan(
            declaration,
            case_parameters=case_parameters,
            include_config_disabled=include_config_disabled,
        )
    return []


def _normalize_step(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    step_id = str(item.get("id", "") or f"step_{index + 1}")
    title = str(item.get("title", "") or step_id)
    return {
        "id": step_id,
        "title": title,
        "kind": str(item.get("kind", "action") or "action"),
        "definition_id": str(item.get("definition_id", "") or step_id),
        "expected": item.get("expected", ""),
        "when_param": str(item.get("when_param", "") or ""),
        "when": dict(item.get("when", {}) if isinstance(item.get("when", {}), dict) else {}),
    }


def _is_case_execute_summary_step(item: dict[str, Any]) -> bool:
    raw_id = str(item.get("id", "") or "").strip()
    definition_id = str(item.get("definition_id", "") or "").strip()
    title = str(item.get("title", "") or "").strip().lower()
    return (
        title.startswith("execute ")
        and (raw_id.endswith(".execute") or definition_id.endswith(".execute") or raw_id == "execute_case")
    )


def _remove_case_execute_summary_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in steps if not _is_case_execute_summary_step(item)]


def _fallback_plan() -> list[dict[str, Any]]:
    return [
        {
            "id": "prepare_runner",
            "title": "Prepare runner and parameters",
            "kind": "setup",
            "definition_id": "smarttest.runner.prepare",
            "expected": "Runner receives selected case and user parameters.",
        },
    ]


def _trace_plan(source: str, *, nodeid: str, steps: list[dict[str, Any]], case_parameters: dict[str, Any]) -> None:
    from tools.logging import smart_log

    smart_log(
        "steps.plan source=%s nodeid=%s count=%s config_keys=%s",
        source,
        nodeid,
        len(steps),
        ",".join(sorted(str(key) for key in case_parameters)) or "<none>",
        level="debug",
        domain="test",
        source="testing.steps.planner",
        case_nodeid=nodeid,
    )
    for index, step in enumerate(steps, start=1):
        smart_log(
            "steps.plan.item index=%s id=%s kind=%s definition_id=%s title=%s",
            index,
            str(step.get("id", "") or "<empty>"),
            str(step.get("kind", "") or "<empty>"),
            str(step.get("definition_id", "") or "<empty>"),
            str(step.get("title", "") or "<empty>"),
            level="debug",
            domain="test",
            source="testing.steps.planner",
            case_nodeid=nodeid,
            step_id=str(step.get("id", "") or ""),
        )
