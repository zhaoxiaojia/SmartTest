from __future__ import annotations

import math
import re
from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "y", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "n", "off", "disabled"}


def to_int(value: Any, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else default
    text = str(value or "").strip()
    if not text:
        return default
    try:
        numeric = float(text)
    except ValueError:
        return default
    return int(numeric) if numeric.is_integer() else default


def to_float(value: Any, *, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else default
    text = str(value or "").strip()
    if not text:
        return default
    try:
        numeric = float(text)
    except ValueError:
        return default
    return numeric if math.isfinite(numeric) else default


def to_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
        return default
    text = str(value or "").strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def to_string(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return str(value)


def to_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = re.split(r"[\s,;]+", value.strip())
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raw_values = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        text = to_string(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def normalize_value(value: Any, value_type: Any, *, default: Any = None) -> Any:
    normalized_type = _type_name(value_type)
    if normalized_type == "int":
        return to_int(value, default=to_int(default, default=0))
    if normalized_type == "float":
        return to_float(value, default=to_float(default, default=0.0))
    if normalized_type == "bool":
        return to_bool(value, default=to_bool(default, default=False))
    if normalized_type == "multi_enum":
        return to_string_list(value if value is not None else default)
    if normalized_type in {"string", "path", "multiline", "enum"}:
        return to_string(value, default=to_string(default))
    return value if value is not None else default


def wire_string(value: Any, *, value_type: Any = None) -> str:
    normalized = normalize_value(value, value_type, default=value) if value_type is not None else value
    if isinstance(normalized, (list, tuple, set)):
        return ",".join(to_string_list(normalized))
    return to_string(normalized)


def _type_name(value_type: Any) -> str:
    raw = getattr(value_type, "value", value_type)
    return str(raw or "").strip().lower()
