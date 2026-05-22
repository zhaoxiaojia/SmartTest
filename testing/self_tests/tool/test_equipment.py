from __future__ import annotations

from testing.tool.equipment import TestEquipment


class _Device:
    def __init__(self, label: str) -> None:
        self.label = label
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_test_equipment_instantiates_configured_devices() -> None:
    created: list[tuple[str, str, str]] = []

    def factory(kind: str):
        def _build(name, config):  # noqa: ANN001
            created.append((kind, name, str(config.get("type", ""))))
            return _Device(f"{kind}:{name}")

        return _build

    equipment = TestEquipment(
        {
            "relay": {"type": "usb_relay", "port": "COM4"},
            "routers": {
                "main": {"type": "ASUS-AX86U", "address": "192.168.50.1"},
            },
            "attenuators": [
                {"name": "rf", "type": "Vaunix-LDA-908V-8", "ip": "192.168.50.20"},
            ],
        },
        relay_factory=factory("relay"),
        router_factory=factory("router"),
        attenuator_factory=factory("attenuator"),
    )

    assert equipment.relay.label == "relay:default"
    assert equipment.get("router", "main").label == "router:main"
    assert equipment.get("attenuator", "rf").label == "attenuator:rf"
    assert created == [
        ("relay", "default", "usb_relay"),
        ("router", "main", "ASUS-AX86U"),
        ("attenuator", "rf", "Vaunix-LDA-908V-8"),
    ]

    devices = [equipment.relay, equipment.get("router", "main"), equipment.get("attenuator", "rf")]
    equipment.close()

    assert all(device.closed for device in devices)


def test_test_equipment_passes_direct_snmp_pdu_relay_config_to_factory(monkeypatch) -> None:
    created: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def build_relay(relay_type, relay_params=None, **kwargs):  # noqa: ANN001
        created.append((relay_type, tuple(relay_params or ()), dict(kwargs)))
        return _Device("relay")

    monkeypatch.setattr("testing.tool.relay_tool.get_relay_controller", build_relay)

    equipment = TestEquipment(
        {
            "relay": {
                "type": "snmp_pdu",
                "ip": "192.0.2.10",
                "port": "4",
            }
        }
    )

    assert equipment.relay.label == "relay"
    assert created == [("snmp_pdu", ("192.0.2.10", 4), {})]


def test_snmp_pdu_relay_uses_default_port_without_compatibility_config(monkeypatch) -> None:
    from testing.tool.relay_tool.pdusnmp import power_ctrl

    monkeypatch.setattr("testing.tool.relay_tool.pdusnmp.load_config", lambda refresh=False: {})

    relay = power_ctrl(("192.0.2.10", 4))

    assert relay.port == ("192.0.2.10", 4)
    assert relay.power_ctrl == {"192.0.2.10": [4]}
