from __future__ import annotations

from collections.abc import Callable

from .bt_devices import known_bluetooth_targets


OptionProvider = Callable[[], list[str]]


_STATIC_OPTION_PROVIDERS: dict[str, OptionProvider] = {
    "auto_reboot:bt_target": known_bluetooth_targets,
    "auto_suspend:bt_target": known_bluetooth_targets,
}


def static_param_options(param_key: str) -> list[str]:
    provider = _STATIC_OPTION_PROVIDERS.get(str(param_key).strip())
    return provider() if provider is not None else []
