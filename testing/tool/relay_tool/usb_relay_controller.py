from __future__ import annotations

import time
from typing import Any

from testing.tool.pc_tool import SerialTool, list_serial_port_entries, normalize_serial_port
from testing.tool.relay_tool import Relay
from tools.logging import smart_log

_DEFAULT_BAUDRATE = 9600
_DEFAULT_HOLD_SECONDS = 0.1


def list_usb_relay_port_entries(selected_serial: str | None = None) -> list[dict[str, str]]:
    del selected_serial
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in list_serial_port_entries():
        value = _normalize_port_name(str(item.get("value", "") or ""))
        if value and value not in seen:
            seen.add(value)
            entries.append({"label": str(item.get("label", "") or value), "value": value})
    return entries


def _normalize_port_name(port: str) -> str:
    return normalize_serial_port(port)


def _command_for_power_action(action: str, terminal: int = 1) -> bytes:
    relay_action = 1 if str(action or "").strip().lower() == "off" else 0
    port = max(1, int(terminal))
    return bytes([0xA0, port, relay_action, (0xA0 + port + relay_action) & 0xFF])


class UsbRelayController(Relay):
    def __init__(self, port: str | None = None, *, terminals: Any = None, mode: str | None = None, press_seconds: float | None = None) -> None:
        super().__init__(_normalize_port_name(str(port or "")))
        self.terminals = _normalize_terminals(terminals, mode=mode, press_seconds=press_seconds)

    def pulse(self, direction: str = "power_off", *, port: str | None = None, mode: str | None = None, press_seconds: float | None = None) -> None:
        del mode
        relay_port = _normalize_port_name(str(port or self.port or ""))
        if not relay_port:
            raise ValueError("USB relay port is not configured")
        action = _direction_to_power_action(direction)
        with SerialTool(relay_port, _DEFAULT_BAUDRATE) as connection:
            for terminal in self.terminals:
                terminal_no = int(terminal.get("terminal", 1))
                hold = press_seconds if press_seconds is not None else terminal.get("press_seconds", 1)
                wiring_mode = str(terminal.get("mode", "NO") or "NO").strip().upper()
                command_action = _action_for_wiring(action, wiring_mode)
                command = _command_for_power_action(command_action, terminal_no)
                smart_log(
                    f"device={relay_port} terminal={terminal_no} direction={direction} "
                    f"action={action} wiring={wiring_mode} hold={hold} "
                    f"cmd={command.hex(' ')}",
                    domain="equipment",
                    source="UsbRelayController",
                )
                smart_log(
                    "USB relay device=%s terminal=%s action=%s wiring=%s hold=%s cmd=%s",
                    relay_port,
                    terminal_no,
                    action,
                    wiring_mode,
                    hold,
                    command.hex(" "),
                    level="info",
                )
                connection.write(command)
                connection.flush()
                time.sleep(max(_DEFAULT_HOLD_SECONDS, float(hold)))


def _direction_to_power_action(direction: str) -> str:
    value = str(direction or "").strip().lower()
    if value in {"power_off", "off"}:
        return "off"
    if value in {"power_on", "on"}:
        return "on"
    raise ValueError(f"Unsupported USB relay direction: {direction}")


def _action_for_wiring(action: str, mode: str) -> str:
    if str(mode or "").strip().upper() == "NC":
        return "on" if action == "off" else "off"
    return action


def _normalize_terminals(terminals: Any, *, mode: str | None, press_seconds: float | None) -> list[dict[str, Any]]:
    if isinstance(terminals, list):
        rows = [_normalize_terminal(item) for item in terminals if isinstance(item, dict)]
        if rows:
            return rows
    return [_normalize_terminal({"terminal": 1, "mode": mode or "NO", "press_seconds": press_seconds or 1})]


def _normalize_terminal(item: dict[str, Any]) -> dict[str, Any]:
    terminal = item.get("terminal", item.get("relay_port", item.get("channel", 1)))
    mode = str(item.get("mode", "NO") or "NO").strip().upper()
    press_seconds = item.get("press_seconds", 1)
    return {
        "terminal": max(1, int(str(terminal).strip() or "1")),
        "mode": mode if mode in {"NO", "NC"} else "NO",
        "press_seconds": float(press_seconds) if press_seconds not in (None, "") else _DEFAULT_HOLD_SECONDS,
    }
