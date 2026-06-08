from __future__ import annotations

from collections.abc import Callable
import importlib
import re
from typing import Any

from .bt_devices import known_bluetooth_targets


OptionProvider = Callable[[], list[str]]
DynamicOptionProvider = Callable[[str | None], list[str]]


_STATIC_OPTION_PROVIDERS: dict[str, OptionProvider] = {
    "ac_onoff:bt_target": known_bluetooth_targets,
    "auto_reboot:bt_target": known_bluetooth_targets,
    "auto_suspend:bt_target": known_bluetooth_targets,
    "bt_onoff_scan:bt_target": known_bluetooth_targets,
    "local_playback_stress:actions": lambda: [
        "pause",
        "seek_forward",
        "seek_backward",
        "back_to_start",
        "seek_to_end",
    ],
}


def static_param_options(param_key: str) -> list[str]:
    provider = _STATIC_OPTION_PROVIDERS.get(str(param_key).strip())
    return provider() if provider is not None else []


def dynamic_param_options(source: str, selected_serial: str | None = None) -> list[str]:
    provider = _load_dynamic_option_provider(source)
    return normalize_option_values(provider(selected_serial))


def normalize_option_values(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        values = re.split(r"[\s,;]+", raw_value.strip())
    elif isinstance(raw_value, (list, tuple, set)):
        values = list(raw_value)
    else:
        values = [raw_value]

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def option_cache_key(source: str, selected_serial: str | None = None) -> str:
    serial = str(selected_serial or "").strip() or "<default>"
    return f"{str(source or '').strip()}@{serial}"


def _load_dynamic_option_provider(source: str) -> DynamicOptionProvider:
    module_name, separator, function_name = str(source or "").strip().partition(":")
    if not module_name or separator != ":" or not function_name:
        raise ValueError(f"Invalid dynamic option source: {source}")
    provider = getattr(importlib.import_module(module_name), function_name)
    if not callable(provider):
        raise TypeError(f"Dynamic option source is not callable: {source}")
    return provider
