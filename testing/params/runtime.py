from __future__ import annotations

from typing import Any

from tools.param_conversion import normalize_value, to_bool, to_float, to_int, to_string, to_string_list, wire_string
from ui import jsonTool

from testing.params.registry import SchemaRegistry, default_registry


class RuntimeParamResolver:
    def __init__(self, registry: SchemaRegistry | None = None) -> None:
        self._registry = registry or default_registry()

    def raw_case_values(self, nodeid: str) -> dict[str, Any]:
        raw_parameters = jsonTool.get_json_value("test_page_state.json", ["case_parameters"], {})
        if not isinstance(raw_parameters, dict):
            return {}
        requested_nodeid = str(nodeid)
        values = raw_parameters.get(requested_nodeid)
        if isinstance(values, dict):
            return dict(values)
        return {}

    def case_values(self, nodeid: str) -> dict[str, Any]:
        return {
            str(key): self.normalize_for_key(str(key), value)
            for key, value in self.raw_case_values(nodeid).items()
            if str(key).strip()
        }

    def get_value(self, nodeid: str, key: str, default: Any = None) -> Any:
        field = self._registry.get_param(str(key or "").strip())
        fallback = field.default if field is not None and default is None else default
        values = self.raw_case_values(nodeid)
        return self.normalize_for_key(key, values.get(str(key), fallback), default=fallback)

    def get_int(self, nodeid: str, key: str, default: int = 0) -> int:
        return to_int(self.get_value(nodeid, key, default), default=default)

    def get_float(self, nodeid: str, key: str, default: float = 0.0) -> float:
        return to_float(self.get_value(nodeid, key, default), default=default)

    def get_bool(self, nodeid: str, key: str, default: bool = False) -> bool:
        return to_bool(self.get_value(nodeid, key, default), default=default)

    def get_list(self, nodeid: str, key: str, default: list[str] | None = None) -> list[str]:
        value = self.get_value(nodeid, key, default or [])
        return to_string_list(value)

    def get_str(self, nodeid: str, key: str, default: str = "") -> str:
        return to_string(self.get_value(nodeid, key, default), default=default)

    def normalize_for_key(self, key: str, value: Any, default: Any = None) -> Any:
        field = self._registry.get_param(str(key or "").strip())
        if field is None:
            return value if value is not None else default
        fallback = field.default if default is None else default
        return normalize_value(value, field.type, default=fallback)

    def apk_params(self, case_id: str, nodeid: str) -> dict[str, str]:
        normalized_case_id = str(case_id or "").strip()
        prefix = f"{normalized_case_id}:"
        resolved: dict[str, str] = {}
        for field in self._registry.fields_by_key.values():
            key = str(field.key or "").strip()
            if key.startswith(prefix) and field.default not in (None, ""):
                resolved[key] = wire_string(field.default, value_type=field.type)
        for key, value in self.raw_case_values(nodeid).items():
            normalized_key = str(key or "").strip()
            if not normalized_key.startswith(prefix):
                continue
            field = self._registry.get_param(normalized_key)
            resolved[normalized_key] = wire_string(
                self.normalize_for_key(normalized_key, value),
                value_type=field.type if field is not None else None,
            )
        return resolved


_RUNTIME_PARAMS = RuntimeParamResolver()


def runtime_params() -> RuntimeParamResolver:
    return _RUNTIME_PARAMS
