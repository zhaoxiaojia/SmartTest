from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    fallback = default or {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return dict(fallback)
    if not isinstance(raw, dict):
        return dict(fallback)
    return raw


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_pref(path: Path, key: str, default: Any = None) -> Any:
    data = load_json(path, {})
    return data.get(key, default)


def save_pref(path: Path, key: str, value: Any) -> None:
    data = load_json(path, {})
    data[key] = value
    save_json(path, data)
