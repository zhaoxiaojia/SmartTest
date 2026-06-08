from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - depends on packaged dependencies
    yaml = None


REQUIRED_PARAMS_PATH = Path(__file__).with_name("required_params.yaml")


@lru_cache(maxsize=1)
def load_required_case_params() -> dict[str, list[str]]:
    if not REQUIRED_PARAMS_PATH.exists():
        return {}
    text = REQUIRED_PARAMS_PATH.read_text(encoding="utf-8")
    payload = yaml.safe_load(text) if yaml is not None else _parse_required_params_yaml(text)
    payload = payload or {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"Required parameter config must be a mapping: {REQUIRED_PARAMS_PATH}")

    cases = payload.get("cases", {})
    if not isinstance(cases, Mapping):
        raise ValueError(f"'cases' must be a mapping in {REQUIRED_PARAMS_PATH}")

    required_by_case: dict[str, list[str]] = {}
    for case_id, case_config in cases.items():
        normalized_case_id = str(case_id).strip()
        if not normalized_case_id:
            continue
        if not isinstance(case_config, Mapping):
            raise ValueError(f"Case '{normalized_case_id}' must be a mapping in {REQUIRED_PARAMS_PATH}")
        required_by_case[normalized_case_id] = _normalize_required_values(case_config.get("required", []))
    return required_by_case


def required_params_for_case(case: Mapping[str, Any]) -> list[str]:
    case_keys = _case_lookup_keys(case)
    required_by_case = load_required_case_params()
    for case_key in case_keys:
        required = required_by_case.get(case_key)
        if required is not None:
            return list(required)
    return []


def _case_lookup_keys(case: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    android_case_id = str(case.get("android_case_id", "") or "").strip()
    if android_case_id:
        keys.append(android_case_id)
    nodeid = str(case.get("nodeid", "") or "").strip()
    if nodeid:
        if "::" in nodeid:
            keys.append(nodeid.rsplit("::", 1)[-1])
        keys.append(nodeid)
    for param_key in list(case.get("required_params", [])):
        prefix = str(param_key).split(":", 1)[0].strip()
        if prefix and prefix not in keys:
            keys.append(prefix)
    return keys


def _normalize_required_values(raw_values: Any) -> list[str]:
    if raw_values is None:
        return []
    if not isinstance(raw_values, list):
        raise ValueError(f"Required parameter entries must be lists in {REQUIRED_PARAMS_PATH}")
    values: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        value = str(raw_value).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _parse_required_params_yaml(text: str) -> dict[str, dict[str, dict[str, list[str]]]]:
    payload: dict[str, dict[str, dict[str, list[str]]]] = {"cases": {}}
    section = ""
    current_case = ""
    current_key = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            section = stripped[:-1].strip()
            continue
        if section != "cases":
            continue
        if indent == 2 and stripped.endswith(":"):
            current_case = stripped[:-1].strip()
            payload["cases"][current_case] = {}
            current_key = ""
            continue
        if indent == 4 and stripped.endswith(":"):
            current_key = stripped[:-1].strip()
            payload["cases"].setdefault(current_case, {})[current_key] = []
            continue
        if indent >= 6 and stripped.startswith("- ") and current_case and current_key:
            value = stripped[2:].strip().strip('"')
            payload["cases"][current_case][current_key].append(value)
    return payload
