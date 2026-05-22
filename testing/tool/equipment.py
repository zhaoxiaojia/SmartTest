from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


EquipmentFactory = Callable[[str, Mapping[str, Any]], Any]


class TestEquipment:
    """Runtime-owned auxiliary equipment beside the DUT.

    The class is intentionally a thin composition root. It instantiates lab
    equipment from a structured config and keeps test cases away from concrete
    relay/router/attenuator factories.
    """

    __test__ = False

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        relay_factory: EquipmentFactory | None = None,
        router_factory: EquipmentFactory | None = None,
        attenuator_factory: EquipmentFactory | None = None,
    ) -> None:
        self.config = dict(config or {})
        self.relays = self._build_group(
            kind="relay",
            configs=self._named_configs("relay", "relays"),
            factory=relay_factory or _build_relay,
        )
        self.routers = self._build_group(
            kind="router",
            configs=self._named_configs("router", "routers"),
            factory=router_factory or _build_router,
        )
        self.attenuators = self._build_group(
            kind="attenuator",
            configs=self._named_configs("attenuator", "attenuators"),
            factory=attenuator_factory or _build_attenuator,
        )

    @classmethod
    def from_environment(cls) -> "TestEquipment":
        from testing.runtime.config import equipment_config

        return cls(equipment_config())

    @property
    def relay(self) -> Any:
        return self.get("relay")

    @property
    def router(self) -> Any:
        return self.get("router")

    @property
    def attenuator(self) -> Any:
        return self.get("attenuator")

    def get(self, kind: str, name: str = "default") -> Any:
        devices = self._group(kind)
        try:
            return devices[name]
        except KeyError as exc:
            raise KeyError(f"{kind} equipment is not configured: {name}") from exc

    def close(self) -> None:
        for device in self._all_devices():
            close = getattr(device, "close", None)
            if callable(close):
                close()

    def _group(self, kind: str) -> dict[str, Any]:
        normalized = str(kind or "").strip().lower()
        if normalized in {"relay", "relays"}:
            return self.relays
        if normalized in {"router", "routers"}:
            return self.routers
        if normalized in {"attenuator", "attenuators", "rf"}:
            return self.attenuators
        raise KeyError(f"Unknown equipment kind: {kind}")

    def _all_devices(self) -> list[Any]:
        return [*self.relays.values(), *self.routers.values(), *self.attenuators.values()]

    def _named_configs(self, singular: str, plural: str) -> dict[str, Mapping[str, Any]]:
        raw_plural = self.config.get(plural)
        if isinstance(raw_plural, Mapping):
            return {
                str(name): dict(value)
                for name, value in raw_plural.items()
                if isinstance(value, Mapping)
            }
        if isinstance(raw_plural, list):
            named: dict[str, Mapping[str, Any]] = {}
            for index, value in enumerate(raw_plural, start=1):
                if not isinstance(value, Mapping):
                    continue
                name = str(value.get("name") or f"{singular}_{index}").strip()
                named[name] = dict(value)
            return named
        raw_singular = self.config.get(singular)
        if isinstance(raw_singular, Mapping):
            return {"default": dict(raw_singular)}
        return {}

    @staticmethod
    def _build_group(
        *,
        kind: str,
        configs: Mapping[str, Mapping[str, Any]],
        factory: EquipmentFactory,
    ) -> dict[str, Any]:
        devices: dict[str, Any] = {}
        for name, config in configs.items():
            device = factory(name, config)
            if device is None:
                raise ValueError(f"{kind} equipment could not be created: {name}")
            devices[name] = device
        return devices


def _build_relay(name: str, config: Mapping[str, Any]) -> Any:
    from testing.tool.relay_tool import get_relay_controller

    relay_type = str(config.get("type") or config.get("relay_type") or "").strip()
    relay_params = config.get("params", config.get("relay_params", ()))
    if not relay_params:
        relay_params = _relay_params_from_direct_fields(config)
    kwargs = {
        key: value
        for key, value in dict(config).items()
        if key
        not in {
            "type",
            "relay_type",
            "params",
            "relay_params",
            "ip",
            "address",
            "host",
        }
    }
    if relay_params:
        kwargs.pop("port", None)
    return get_relay_controller(relay_type, relay_params, **kwargs)


def _relay_params_from_direct_fields(config: Mapping[str, Any]) -> tuple[Any, ...]:
    ip = str(config.get("ip") or config.get("address") or config.get("host") or "").strip()
    raw_port = config.get("port")
    try:
        port = int(str(raw_port).strip()) if raw_port not in (None, "") else None
    except (TypeError, ValueError):
        port = None
    if ip and port is not None:
        return (ip, port)
    return ()


def _build_router(name: str, config: Mapping[str, Any]) -> Any:
    from testing.tool.router_tool.router_factory import get_router

    router_name = str(config.get("type") or config.get("model") or config.get("router_name") or name).strip()
    address = config.get("address", config.get("ip"))
    return get_router(router_name, str(address).strip() if address is not None else None)


def _build_attenuator(name: str, config: Mapping[str, Any]) -> Any:
    from testing.tool.wifi_lab_tool.lab_device_controller import LabDeviceController

    ip = str(config.get("ip") or config.get("address") or "").strip()
    if not ip:
        raise ValueError(f"attenuator equipment requires ip/address: {name}")
    model = str(config.get("model") or config.get("type") or "").strip() or None
    channels = config.get("channels", config.get("ports"))
    return LabDeviceController(ip, model=model, channels=channels)
