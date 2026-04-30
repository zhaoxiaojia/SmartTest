from __future__ import annotations

import ast
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]


def _android_case_ids_by_function() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in (ROOT / "testing" / "tests").rglob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            case_id = _find_case_id(node)
            if case_id:
                rel = path.relative_to(ROOT).as_posix()
                result[f"{rel}::{node.name}"] = case_id
    return result


def _find_case_id(node: ast.FunctionDef) -> str:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        for keyword in child.keywords:
            if keyword.arg == "case_id" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value)
        if (
            isinstance(child.func, ast.Name)
            and child.func.id == "build_case_params"
            and child.args
            and isinstance(child.args[0], ast.Constant)
        ):
            return str(child.args[0].value)
    name = node.name
    if name.startswith("test_") and name.endswith("_via_android_client"):
        return name[len("test_") : -len("_via_android_client")]
    return ""


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from testing.cases.discovery import discover_pytest_cases

    case_ids = _android_case_ids_by_function()
    cases = discover_pytest_cases(root_dir=ROOT, python_executable=sys.executable)
    payload = []
    for case in cases:
        payload.append(
            {
                "nodeid": case.nodeid,
                "file": case.file,
                "name": case.name,
                "markers": case.markers,
                "case_type": case.case_type,
                "required_params": case.required_params,
                "required_param_groups": case.required_param_groups,
                "android_case_id": case_ids.get(case.nodeid, ""),
            }
        )
    out_path = ROOT / "build" / "generated" / "testing" / "cases" / "test_catalog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = [row["nodeid"] for row in payload if not row.get("android_case_id")]
    if missing:
        raise SystemExit("Missing android_case_id for packaged tests:\n" + "\n".join(missing))


if __name__ == "__main__":
    main()

