from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable


APP_DATA_ENV = "SMARTTEST_APP_DATA_DIR"
APP_DATA_ORG = "Amlogic"
APP_DATA_NAME = "SmartTest"


def app_data_dir() -> Path:
    override = str(os.environ.get(APP_DATA_ENV, "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
    if local_app_data:
        return Path(local_app_data) / APP_DATA_ORG / APP_DATA_NAME
    return Path.home() / ".local" / "share" / APP_DATA_ORG / APP_DATA_NAME


def resolve_json_path(path: str | Path) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return app_data_dir() / resolved


def read_json(path: str | Path, default: Any | None = None) -> Any:
    resolved = resolve_json_path(path)
    if not resolved.exists():
        return {} if default is None else default
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {resolved}") from exc


def write_json(path: str | Path, data: Any) -> None:
    resolved = resolve_json_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = resolved.with_name(f"{resolved.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    tmp_path.replace(resolved)


def get_json_value(path: str | Path, keys: Iterable[str], default: Any | None = None) -> Any:
    current: Any = read_json(path, {})
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def set_json_value(path: str | Path, keys: Iterable[str], value: Any) -> None:
    key_list = [str(key) for key in keys]
    if not key_list:
        write_json(path, value)
        return
    data = read_json(path, {})
    if not isinstance(data, dict):
        data = {}
    current = data
    for key in key_list[:-1]:
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value
    current[key_list[-1]] = value
    write_json(path, data)
