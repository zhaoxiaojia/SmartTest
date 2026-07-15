from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from jira_tool.fields.specs import FieldSpec


@dataclass(frozen=True)
class PathToken:
    key: str
    iterate: bool = False


@lru_cache(maxsize=512)
def parse_path(path: str) -> tuple[PathToken, ...]:
    normalized = (path or "").strip()
    if normalized == "":
        raise ValueError("field path cannot be empty")
    tokens: list[PathToken] = []
    for segment in normalized.split("."):
        clean = segment.strip()
        if clean == "":
            raise ValueError(f"invalid field path segment in '{path}'")
        iterate = clean.endswith("[]")
        key = clean[:-2] if iterate else clean
        if key == "":
            raise ValueError(f"invalid iterable field path segment in '{path}'")
        tokens.append(PathToken(key=key, iterate=iterate))
    return tuple(tokens)


def extract_path(data: Any, path: str, default: Any = None) -> Any:
    values = _extract_values(data, parse_path(path))
    if not values:
        return default
    if len(values) == 1:
        return values[0]
    return values


def extract_spec(data: dict[str, Any], spec: FieldSpec) -> Any:
    return spec.convert(extract_path(data, spec.path, spec.default))


def project_fields(data: dict[str, Any], specs: list[FieldSpec]) -> dict[str, Any]:
    return {spec.name: extract_spec(data, spec) for spec in specs}


def _extract_values(current: Any, tokens: tuple[PathToken, ...]) -> list[Any]:
    if not tokens:
        return [current]
    if current is None:
        return []

    token = tokens[0]
    remaining = tokens[1:]
    next_value = _lookup(current, token.key)
    if next_value is None:
        return []

    if token.iterate:
        if not isinstance(next_value, list):
            return []
        values: list[Any] = []
        for item in next_value:
            values.extend(_extract_values(item, remaining))
        return values

    return _extract_values(next_value, remaining)


def _lookup(current: Any, key: str) -> Any:
    if isinstance(current, dict):
        return current.get(key)
    return getattr(current, key, None)
