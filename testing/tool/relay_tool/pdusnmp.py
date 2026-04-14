"""High-level control interfaces for SNMP-based power distribution units.

This module provides a simple wrapper around SNMP commands to control power
relays. It exposes a :class:`power_ctrl` class that reads configuration
information, constructs SNMP command strings and executes them using
``subprocess``. All function and method arguments are documented in a
``Parameters`` section.
"""
import logging
from testing.tool.connect_tool import command_batch as subprocess
import time
from typing import Any, Sequence

from src.util.constants import load_config
from testing.tool.relay_tool import Relay


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

        compat = self.config["compatibility"]
        power_cfg = compat["power_ctrl"]
        relays_cfg = power_cfg["relays"]

        power_relay: dict[str, list[int]] = {}
        for entry in relays_cfg:
            ip = str(entry["ip"]).strip()
            ports = [int(p) for p in entry["ports"]]
            if ip in power_relay:
                for port in ports:
                    if port not in power_relay[ip]:
                        power_relay[ip].append(port)
            else:
                power_relay[ip] = ports

        self.power_ctrl = power_relay
        self.ip_list = list(self.power_ctrl.keys())
        self.ctrl = self._handle_env_data()

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
            logging.info("SNMP cmd[%s]: %s", attempt, cmd)
            if result.stdout:
                logging.info("SNMP stdout[%s]: %s", attempt, result.stdout)
            if result.stderr:
                logging.info("SNMP stderr[%s]: %s", attempt, result.stderr)
            if result.returncode == 0:
                return result.stdout
            logging.error("SNMP exit code[%s]: %s", attempt, result.returncode)
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
        logging.info(
            f'Setting power relay: {ip} port {port} {"on" if status == 1 else "off"}'
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
        logging.info('Shutting down all relays')
        self.set_all(False)

    def pulse(self, direction: str = "power_off", *, port: tuple[str, int] | None = None) -> None:
        """Send a simple SNMP switch for one relay port."""
        target = port or self.port
        if not target:
            logging.warning("No relay port specified for SNMP pulse")
            return
        ip, relay_port = target
        action = (direction or "power_off").strip().lower()
        off_alias = {"power_off", "off", "断通"}
        on_alias = {"power_on", "on", "通断"}
        if action not in off_alias | on_alias:
            logging.warning("Unknown direction %s; defaulting to power_off", direction)
            action = "power_off"
        status = 0 if action in off_alias else 1
        self.switch(ip, relay_port, status)

# s = PowerCtrl("192.168.50.230")
# s.switch(2, True)
# s.dark()
# s.survival(1)
# print(s.get_status(1))
# time.sleep(1)
# print("start on")
# s.switch(1, True)
# print(s.get_status(2))

# s = power_ctrl()
# s.switch('192.168.200.4',4,1)
