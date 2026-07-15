"""High-level control interfaces for SNMP-based power distribution units.

This module provides a simple wrapper around SNMP commands to control power
relays. It exposes a :class:`power_ctrl` class that reads configuration
information, constructs SNMP command strings and executes them using
``subprocess``. All function and method arguments are documented in a
``Parameters`` section.
"""
from testing.tool.dut_tool import command_batch as subprocess
import time
from collections.abc import Mapping
from typing import Any, Sequence

from testing.tool.relay_tool import Relay
from support.logging import smart_log


def load_config(refresh: bool = False) -> dict[str, Any]:
    return {}


class power_ctrl(Relay):
    """Encapsulate control of power relays using SNMP via shell commands."""

    SWITCH_CMD = 'snmpset -v1 -c private {} .1.3.6.1.4.1.23280.9.1.2.{} i {}'
    SET_CMD = 'snmpset -v1 -c private {} 1.3.6.1.4.1.23273.4.4{}.0 i 255'
    Relay_IP = ['192.168.200.3', '192.168.200.4', '192.168.200.5', '192.168.200.6', '192.168.200.7', '192.168.200.8']

    def __init__(self, default_port: tuple[str, int] | Sequence[Any] | None = None) -> None:
        """Load SNMP relay config and optional default port.

        The relay configuration is defined under ``compatibility.power_ctrl``
        in ``config_compatibility.yaml``.
        """
        super().__init__(self._coerce_default_port(default_port))
        self.config = load_config(refresh=True)

        relays_cfg = self._configured_relays(self.config)

        power_relay: dict[str, list[int]] = {}
        for entry in relays_cfg:
            if not isinstance(entry, Mapping):
                continue
            ip = str(entry.get("ip", "")).strip()
            if not ip:
                continue
            ports = [int(p) for p in list(entry.get("ports") or [])]
            if ip in power_relay:
                for port in ports:
                    if port not in power_relay[ip]:
                        power_relay[ip].append(port)
            else:
                power_relay[ip] = ports

        if self.port:
            ip, port = self.port
            ports = power_relay.setdefault(ip, [])
            if port not in ports:
                ports.append(port)

        self.power_ctrl = power_relay
        self.ip_list = list(self.power_ctrl.keys())
        self.ctrl = self._handle_env_data()

    @staticmethod
    def _configured_relays(config: Mapping[str, Any] | None) -> list[Any]:
        if not isinstance(config, Mapping):
            return []
        compat = config.get("compatibility")
        if not isinstance(compat, Mapping):
            return []
        power_cfg = compat.get("power_ctrl")
        if not isinstance(power_cfg, Mapping):
            return []
        relays = power_cfg.get("relays")
        return list(relays) if isinstance(relays, list) else []

    @staticmethod
    def _coerce_default_port(value: tuple[str, int] | Sequence[Any] | None) -> tuple[str, int] | None:
        """Normalize list-like relay params into an (ip, port) tuple."""

        if value is None:
            return None
        if isinstance(value, tuple) and len(value) == 2:
            ip, port = value
        elif isinstance(value, Sequence):
            items = list(value)
            if not items:
                return None
            ip = str(items[0]).strip()
            port = items[1] if len(items) > 1 else None
        else:
            return None
        ip = str(ip).strip()
        try:
            port_int = int(str(port).strip()) if port is not None else None
        except (TypeError, ValueError):
            port_int = None
        if ip and port_int is not None:
            return ip, port_int
        return None

    def _handle_env_data(self) -> list[tuple[str, int]]:
        """Flatten the configuration into a list of (IP, port) tuples.

        Returns:
            list[tuple[str, int]]: A list of tuples where each tuple contains
            an IP address and an integer port number defined in the configuration.
        """
        temp: list[tuple[str, int]] = []
        for k, v in self.power_ctrl.items():
            if v:
                for i in v:
                    temp.append((k, i))
        return temp

    @staticmethod
    def check_output(cmd: str) -> bytes | None:
        for attempt in range(1, 4):
            result = subprocess.run(cmd, shell=True, capture_output=True)
            smart_log("SNMP cmd[%s]: %s", attempt, cmd, level="info")
            if result.stdout:
                smart_log("SNMP stdout[%s]: %s", attempt, result.stdout, level="info")
            if result.stderr:
                smart_log("SNMP stderr[%s]: %s", attempt, result.stderr, level="info")
            if result.returncode == 0:
                return result.stdout
            smart_log("SNMP exit code[%s]: %s", attempt, result.returncode, level="error")
            time.sleep(1)
        return None


    def switch(self, ip: str, port: int, status: int) -> None:
        """Toggle an individual relay on or off.

        Parameters:
            ip (str): The IP address of the relay device.
            port (int): The port number on the relay device to control.
            status (int): ``1`` to turn the port on, ``0`` or ``2`` to turn
                it off depending on the underlying SNMP semantics.

        Returns:
            None
        """
        smart_log(
            f'Setting power relay: {ip} port {port} {"on" if status == 1 else "off"}',
            level="info",
        )
        cmd = self.SWITCH_CMD.format(ip, port, status)
        self.check_output(cmd)

    def set_all(self, status: bool) -> None:
        """Set all configured relays to the given state.

        Parameters:
            status (bool): ``True`` to power on all relays or ``False`` to shut
                them down.  The SNMP command is constructed accordingly.

        Returns:
            None
        """
        for k in self.Relay_IP:
            cmd = self.SET_CMD.format(k, 0 if status else 1)
            self.check_output(cmd)

    def shutdown(self) -> None:
        """Shut down all relays via SNMP.

        Returns:
            None
        """
        smart_log('Shutting down all relays', level="info")
        self.set_all(False)

    def pulse(self, direction: str = "power_off", *, port: tuple[str, int] | None = None) -> None:
        """Send a simple SNMP switch for one relay port."""
        target = port or self.port
        if not target:
            smart_log("No relay port specified for SNMP pulse", level="warning")
            return
        ip, relay_port = target
        action = (direction or "power_off").strip().lower()
        off_alias = {"power_off", "off"}
        on_alias = {"power_on", "on"}
        if action not in off_alias | on_alias:
            smart_log("Unknown direction %s; defaulting to power_off", direction, level="warning")
            action = "power_off"
        status = 0 if action in off_alias else 1
        self.switch(ip, relay_port, status)

