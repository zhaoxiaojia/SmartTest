from __future__ import annotations

from pathlib import Path
from typing import Any

from ui import jsonTool


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    fallback = default or {}
    try:
        raw = jsonTool.read_json(path, dict(fallback))
    except (FileNotFoundError, OSError, ValueError):
        return dict(fallback)
    if not isinstance(raw, dict):
        return dict(fallback)
    return raw


def save_json(path: Path, data: dict[str, Any]) -> None:
    jsonTool.write_json(path, data)


def load_pref(path: Path, key: str, default: Any = None) -> Any:
    data = load_json(path, {})
    return data.get(key, default)


def save_pref(path: Path, key: str, value: Any) -> None:
    data = load_json(path, {})
    data[key] = value
    save_json(path, data)
