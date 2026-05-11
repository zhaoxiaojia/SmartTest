from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path
from typing import Any

from testing.actions import ActionPlanContext, get_action
from testing.cases.catalog import load_runtime_test_catalog
from testing.tests import build_declared_case_plan, declared_step_enabled


_CYCLE_ID_RE = re.compile(r"\.(cycle|loop)\.\d+\.")
_CYCLE_TITLE_RE = re.compile(r"\b(cycle|loop)\s+\d+\s*/\s*\d+\s*:\s*", re.IGNORECASE)


def build_step_plan(
    *,
    root_dir: Path,
    nodeid: str,
    case_config: dict[str, Any],
    prefer_catalog: bool = True,
    include_config_disabled: bool = False,
) -> list[dict[str, Any]]:
    use_catalog_plan = prefer_catalog
    if use_catalog_plan:
        catalog_plan = _catalog_step_plan(root_dir=root_dir, nodeid=nodeid, case_config=case_config)
        if catalog_plan:
            return _remove_case_execute_summary_steps(catalog_plan)
    declared_plan = _load_declared_plan(
        root_dir=root_dir,
        nodeid=nodeid,
        case_config=case_config,
        include_config_disabled=include_config_disabled,
    )
    if not declared_plan:
        declared_steps = _declared_runtime_steps(root_dir=root_dir, nodeid=nodeid, case_config=case_config)
        mirrored_plan = _android_mirrored_plan(root_dir=root_dir, nodeid=nodeid, case_config=case_config)
        if declared_steps or mirrored_plan:
            return _remove_case_execute_summary_steps(_merge_plans([*declared_steps, *mirrored_plan]))
        return _fallback_plan(nodeid=nodeid, case_config=case_config)
    normalized = [_normalize_step(item, index=index) for index, item in enumerate(declared_plan)]
    return _remove_case_execute_summary_steps(_compact_repeated_cycle_steps(normalized))


def _catalog_step_plan(*, root_dir: Path, nodeid: str, case_config: dict[str, Any]) -> list[dict[str, Any]]:
    for row in load_runtime_test_catalog(root_dir=root_dir):
        if str(row.get("nodeid", "") or "").strip() != nodeid:
            continue
        raw_steps = row.get("initial_step_plan")
        if not isinstance(raw_steps, list):
            return []
        resolved = [_normalize_step(dict(item), index=index) for index, item in enumerate(raw_steps) if isinstance(item, dict)]
        if not resolved:
            return []
        # Rebind params from current case config so runtime overrides are reflected.
        for item in resolved:
            params = item.get("params", {})
            current = dict(params) if isinstance(params, dict) else {}
            for key, value in case_config.items():
                current[str(key)] = value
            item["params"] = current
            item["title"] = _resolve_title_placeholders(str(item.get("title", "") or ""), current)
        case_id = str(row.get("android_case_id", "") or "").strip()
        resolved = [item for item in resolved if _step_enabled(item, case_id=case_id)]
        return _remove_case_execute_summary_steps(_compact_repeated_cycle_steps(resolved))
    return []


def _step_enabled(item: dict[str, Any], *, case_id: str) -> bool:
    params = dict(item.get("params", {}) if isinstance(item.get("params", {}), dict) else {})
    definition_id = str(item.get("definition_id", "") or "").strip()
    if definition_id:
        try:
            action = get_action(definition_id)
        except KeyError:
            pass
        else:
            decision = action.plan_decision(
                ActionPlanContext(case_id=case_id, params=params, step=dict(item))
            )
            return decision.include
    return declared_step_enabled(item, params)


def _load_declared_plan(
    *,
    root_dir: Path,
    nodeid: str,
    case_config: dict[str, Any],
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
            case_config=dict(case_config),
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
        "params": dict(item.get("params", {}) if isinstance(item.get("params", {}), dict) else {}),
        "expected": item.get("expected", ""),
        "when_param": str(item.get("when_param", "") or ""),
        "when": dict(item.get("when", {}) if isinstance(item.get("when", {}), dict) else {}),
    }


def _merge_plans(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        normalized = _normalize_step(item, index=index)
        key = str(normalized.get("id") or normalized.get("definition_id") or "")
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def _looks_like_cycle_step(item: dict[str, Any]) -> bool:
    raw_id = str(item.get("id", "") or "")
    title = str(item.get("title", "") or "")
    return bool(_CYCLE_ID_RE.search(raw_id) or _CYCLE_TITLE_RE.search(title))


def _compact_step_id(raw_id: str) -> str:
    compact = _CYCLE_ID_RE.sub(lambda m: f".{m.group(1)}.", raw_id)
    return compact


def _compact_step_title(title: str) -> str:
    return _CYCLE_TITLE_RE.sub(lambda m: f"{m.group(1).capitalize()}: ", title).strip()


def _compact_repeated_cycle_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in steps:
        if not _looks_like_cycle_step(item):
            compacted.append(item)
            continue
        kind = str(item.get("kind", "") or "")
        definition_id = str(item.get("definition_id", "") or "")
        key = ("cycle", kind, definition_id)
        if key in seen:
            continue
        seen.add(key)
        compact = dict(item)
        compact["id"] = _compact_step_id(str(item.get("id", "") or ""))
        compact["title"] = _compact_step_title(str(item.get("title", "") or ""))
        compacted.append(compact)
    return compacted


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


def _declared_runtime_steps(*, root_dir: Path, nodeid: str, case_config: dict[str, Any]) -> list[dict[str, Any]]:
    tree = _parse_node_module(root_dir=root_dir, nodeid=nodeid)
    if tree is None:
        return []
    steps: list[dict[str, Any]] = [
        {
            "id": "prepare_runner",
            "title": "Prepare runner and parameters",
            "kind": "setup",
            "definition_id": "smarttest.runner.prepare",
            "params": dict(case_config),
            "expected": "Runner receives selected case and user parameters.",
        }
    ]
    declared_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _call_name(node.func) in {"case_step", "setup_step", "teardown_step", "action_step", "loop_step"}
    ]
    for node in sorted(declared_calls, key=lambda item: getattr(item, "lineno", 0)):
        function_name = _call_name(node.func)
        title = _literal_arg(node, 0)
        definition_id = _literal_keyword(node, "definition_id")
        if not title or not definition_id or definition_id.startswith("android_client."):
            continue
        steps.append(
            {
                "id": definition_id,
                "title": title,
                "kind": _step_kind(function_name),
                "definition_id": definition_id,
                "params": dict(case_config),
                "expected": "",
            }
        )
    return steps


def _step_kind(function_name: str) -> str:
    if function_name == "setup_step":
        return "setup"
    if function_name == "teardown_step":
        return "teardown"
    if function_name == "loop_step":
        return "loop"
    return "step"


def _android_mirrored_plan(*, root_dir: Path, nodeid: str, case_config: dict[str, Any]) -> list[dict[str, Any]]:
    case_id = _android_case_id_from_node(root_dir=root_dir, nodeid=nodeid)
    if not case_id:
        return []
    params = {
        key: value
        for key, value in case_config.items()
        if str(key).startswith(f"{case_id}:")
    }
    case_title = nodeid.rsplit("::", 1)[-1] if "::" in nodeid else nodeid
    return [
        {
            "id": "prepare_runner",
            "title": "Prepare runner and parameters",
            "kind": "setup",
            "definition_id": "smarttest.runner.prepare",
            "params": params,
            "expected": "Runner receives selected case and user parameters.",
        }
    ]


def _android_case_id_from_node(*, root_dir: Path, nodeid: str) -> str:
    tree = _parse_node_module(root_dir=root_dir, nodeid=nodeid)
    if tree is None:
        return ""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = _call_name(node.func)
        if function_name == "trigger_android_client_case":
            case_id = _literal_keyword(node, "case_id") or _literal_arg(node, 0)
            if case_id:
                return case_id
        if function_name == "build_case_params":
            case_id = _literal_arg(node, 0)
            if case_id:
                return case_id
    return ""


def _parse_node_module(*, root_dir: Path, nodeid: str) -> ast.AST | None:
    path_text = nodeid.split("::", 1)[0].strip()
    if not path_text:
        return None
    module_path = (root_dir / path_text).resolve()
    if not module_path.exists() or module_path.suffix != ".py":
        return None
    try:
        return ast.parse(module_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None


def _literal_arg(node: ast.Call, index: int) -> str:
    if len(node.args) <= index:
        return ""
    value = node.args[index]
    if isinstance(value, ast.Constant):
        return str(value.value or "").strip()
    return ""


def _literal_keyword(node: ast.Call, name: str) -> str:
    for keyword in node.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value or "").strip()
    return ""


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _fallback_plan(*, nodeid: str, case_config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "prepare_runner",
            "title": "Prepare runner and parameters",
            "kind": "setup",
            "definition_id": "smarttest.runner.prepare",
            "params": dict(case_config),
            "expected": "Runner receives selected case and user parameters.",
        },
    ]
