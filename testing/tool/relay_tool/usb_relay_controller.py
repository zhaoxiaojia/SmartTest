from __future__ import annotations

"""High-level helpers to control a USB relay device.

This module defines byte-level command constants, default serial settings,
and utility functions for normalizing port names and wiring modes.  The
:class:`UsbRelayDevice` encapsulates serial communication with the relay
hardware and exposes context manager semantics for automatic opening and
closing.  Top-level functions allow callers to apply, pulse and hold
relay states.  Global variables are annotated using :class:`~typing.Annotated`
to document their purpose.
"""

import logging
import re
import time
from typing import Iterable, Annotated

from testing.tool.relay_tool import Relay

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    serial = None  # type: ignore

_RELAY_RELEASE: Annotated[bytes, "Byte sequence to release the relay coil"] = bytes([0xA0, 0x01, 0x00, 0xA1])
_RELAY_ENGAGE: Annotated[bytes, "Byte sequence to engage the relay coil"] = bytes([0xA0, 0x01, 0x01, 0xA2])
_DEFAULT_BAUDRATE: Annotated[int, "Default serial baud rate for the relay controller"] = 9600
_DEFAULT_TIMEOUT: Annotated[float, "Default timeout in seconds for serial communication"] = 1.0
_SEND_INTERVAL: Annotated[float, "Default interval between successive USB relay commands"] = 0.1
_WINDOWS_COM_PORT_PATTERN: Annotated[re.Pattern[str], "Regex to capture Windows COM port designations"] = re.compile(r"^(COM\d+)", flags=re.IGNORECASE)
_SUPPORTED_WIRING: Annotated[set[str], "Supported wiring modes for the relay contacts"] = {"NO", "NC"}


def _normalize_port_name(port: str) -> str:
    """Trim human-friendly suffixes (e.g. 'COM4 (USB-SERIAL ...)') from port names.

    Parameters:
        port (str): A raw port name which may include descriptive suffixes
            such as USB identifiers or parentheses.

    Returns:
        str: A normalized port name stripped of any suffixes and converted
        to uppercase on Windows platforms.
    """
    candidate = (port or "").strip()
    if not candidate:
        return candidate

    match = _WINDOWS_COM_PORT_PATTERN.match(candidate)
    if match:
        return match.group(1).upper()

    if "(" in candidate:
        candidate = candidate.split("(", 1)[0].strip()
    if " " in candidate:
        candidate = candidate.split(" ", 1)[0]
    return candidate


class UsbRelayDevice:
    """Represent a connection to a USB relay controlled via a serial port.

    This class manages the opening and closing of a serial connection to the
    relay and provides methods to send raw command bytes or sequences of
    commands.  It supports use as a context manager such that the serial
    port is automatically opened on entry and closed on exit.

    Parameters:
        port (str): The system-specific identifier for the serial port.  The
            value will be normalized by :func:`_normalize_port_name`.
        baudrate (int, optional): The baud rate for the serial port.  Defaults
            to :data:`_DEFAULT_BAUDRATE`.
        timeout (float, optional): Read timeout for the serial port in
            seconds.  Defaults to :data:`_DEFAULT_TIMEOUT`.
    """

    def __init__(self, port: str, *, baudrate: int = _DEFAULT_BAUDRATE, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self.raw_port = (port or "").strip()
        self.port = _normalize_port_name(self.raw_port)
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None
        if self.raw_port and self.port and self.raw_port != self.port:
            logging.debug("Normalized USB relay port from %s to %s", self.raw_port, self.port)

    def open(self) -> None:
        """Open the serial connection to the USB relay if not already open.

        Raises:
            Exception: Propagates any exceptions raised by :class:`serial.Serial`
                when attempting to open the port.  A descriptive error is
                logged prior to raising the exception.
        """
        if self._serial is not None or serial is None:
            return
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        except Exception as exc:  # pragma: no cover - depends on environment
            port_label = self.port
            if self.raw_port and self.raw_port != self.port:
                port_label = f"{self.port} (from {self.raw_port})"
            logging.error("Failed to open USB relay port %s: %s", port_label, exc)
            raise

    def close(self) -> None:
        """Close the serial connection to the USB relay.

        This method quietly does nothing if the connection is already closed.
        """
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None

    def __enter__(self) -> "UsbRelayDevice":
        """Enter the context manager, opening the serial port if necessary.

        Returns:
            UsbRelayDevice: The instance itself with an open serial connection.
        """
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Exit the context manager and close the serial connection.

        Parameters are ignored but included for compatibility with the context
        manager protocol.

        Returns:
            None
        """
        self.close()

    def send(self, command: bytes) -> None:
        """Write a single command to the relay and flush the serial buffer.

        Parameters:
            command (bytes): The raw command bytes to send to the relay.

        Raises:
            RuntimeError: If the optional ``serial`` dependency is not
                available.

        Returns:
            None
        """
        if serial is None:
            raise RuntimeError("pyserial is required for USB relay control")
        if self._serial is None:
            self.open()
        assert self._serial is not None
        self._serial.write(command)
        self._serial.flush()

    def send_sequence(self, commands: Iterable[bytes], *, interval: float = _SEND_INTERVAL) -> None:
        """Send a sequence of commands to the relay with optional delays.

        Parameters:
            commands (Iterable[bytes]): An iterable of command byte strings to
                send sequentially to the relay.
            interval (float, optional): Time in seconds to wait between
                commands.  Defaults to the module-level :data:`_SEND_INTERVAL`.

        Returns:
            None
        """
        for command in commands:
            self.send(command)
            time.sleep(max(0.0, interval))


class UsbRelayController(Relay):
    """Expose Relay ABC behavior for USB relays."""

    def __init__(self, port: str | None = None, *, mode: str = "NO", press_seconds: float | None = None) -> None:
        """Store default USB relay parameters."""
        super().__init__(port)
        self.mode = mode
        self.press_seconds = press_seconds

    def pulse(
        self,
        direction: str = "power_off",
        *,
        port: str | None = None,
        mode: str | None = None,
        press_seconds: float | None = None,
    ) -> None:
        """Dispatch the standard USB relay pulse."""
        relay_port = port or self.port
        if not relay_port:
            raise ValueError("USB relay port is not configured")
        device_mode = mode or self.mode
        duration = press_seconds if press_seconds is not None else self.press_seconds
        logging.debug(
            "USB relay pulse direction=%s port=%s mode=%s hold=%s",
            direction,
            relay_port,
            device_mode,
            duration,
        )
        with UsbRelayDevice(relay_port) as device:
            pulse(device, device_mode, duration)


def _normalize_wiring(mode: str) -> str:
    """Normalize a wiring mode string to a supported value.

    Parameters:
        mode (str): A user-provided wiring mode value such as ``"NO"`` or
            ``"NC"``.

    Returns:
        str: A normalized uppercase wiring mode.  Unrecognized values
        default to ``"NO"`` and cause a warning to be logged.
    """
    wiring = (mode or "NO").strip().upper()
    if wiring not in _SUPPORTED_WIRING:
        logging.warning("Unknown wiring mode %s, defaulting to NO", mode)
        return "NO"
    return wiring


def _command_for_coil_state(desired_state: str) -> bytes:
    """Return the command bytes corresponding to a desired coil state.

    Parameters:
        desired_state (str): The desired relay state, either ``"on"`` or
            ``"off"`` (case-insensitive).

    Returns:
        bytes: The command bytes that will engage or release the relay coil.

    Raises:
        ValueError: If ``desired_state`` is not ``"on"`` or ``"off"``.
    """
    desired = desired_state.lower()
    if desired == "on":
        return _RELAY_ENGAGE
    if desired == "off":
        return _RELAY_RELEASE
    raise ValueError(f"Unsupported relay state: {desired_state}")


def _describe_contact_state(wiring: str, coil_engaged: bool) -> str:
    """Describe the contact state based on wiring type and coil state.

    Parameters:
        wiring (str): The wiring mode, either ``"NO"`` (normally open) or
            ``"NC"`` (normally closed).
        coil_engaged (bool): Whether the relay coil is currently energized.

    Returns:
        str: ``"closed"`` or ``"open"`` reflecting the physical contact state.
    """
    if wiring == "NO":
        return "closed" if coil_engaged else "open"
    # wiring == "NC"
    return "open" if coil_engaged else "closed"


def apply_state(device: UsbRelayDevice, mode: str, desired_state: str) -> None:
    """Set the relay coil explicitly to on (engaged) or off (released).

    For ``mode="NO"`` a coil engagement closes the contact; for
    ``mode="NC"`` it opens it.  The command bytes match the USB protocol
    directly (``01`` -> engage, ``00`` -> release).

    Parameters:
        device (UsbRelayDevice): The relay device through which to send commands.
        mode (str): Wiring mode, either ``"NO"`` or ``"NC"``.
        desired_state (str): Desired state, either ``"on"`` or ``"off"``.

    Returns:
        None
    """
    wiring = _normalize_wiring(mode)
    command = _command_for_coil_state(desired_state)
    coil_engaged = command == _RELAY_ENGAGE
    logging.debug(
        "Relay wiring=%s -> coil %s (contact %s)",
        wiring,
        "engaged" if coil_engaged else "released",
        _describe_contact_state(wiring, coil_engaged),
    )
    device.send_sequence((command,), interval=0.0)


def pulse(device: UsbRelayDevice, mode: str, press_seconds: float | None = None) -> None:
    """Simulate a short button tap by energising the coil then releasing it.

    Parameters:
        device (UsbRelayDevice): The relay device to operate.
        mode (str): Wiring mode, either ``"NO"`` or ``"NC"``.
        press_seconds (float | None, optional): Duration in seconds to hold
            the coil engaged; ``None`` uses the default send interval.

    Returns:
        None
    """
    wiring = _normalize_wiring(mode)
    hold = _SEND_INTERVAL if press_seconds is None else max(0.1, press_seconds)
    logging.debug(
        "Relay pulse wiring=%s hold=%ss (contact presses %s)",
        wiring,
        hold,
        _describe_contact_state(wiring, True),
    )
    device.send_sequence((_RELAY_ENGAGE,), interval=0.0)
    if hold > 0.0:
        time.sleep(hold)
    device.send_sequence((_RELAY_RELEASE,), interval=0.0)


def long_press(device: UsbRelayDevice, mode: str, hold_seconds: float) -> None:
    """Hold the button for the requested duration before releasing the relay.

    Parameters:
        device (UsbRelayDevice): The relay device to operate.
        mode (str): Wiring mode, either ``"NO"`` or ``"NC"``.
        hold_seconds (float): Duration in seconds to hold the coil engaged.

    Returns:
        None
    """
    wiring = _normalize_wiring(mode)
    hold = max(0.0, hold_seconds)
    logging.debug(
        "Relay long-press wiring=%s hold=%ss (contact presses %s)",
        wiring,
        hold,
        _describe_contact_state(wiring, True),
    )
    device.send_sequence((_RELAY_ENGAGE,), interval=0.0)
    time.sleep(hold)
    device.send_sequence((_RELAY_RELEASE,), interval=0.0)
