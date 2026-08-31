from __future__ import annotations

import platform
import re
import os
import subprocess
from typing import Any

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    serial = None  # type: ignore

_SERIAL_COMMANDS: dict[str, list[str]] = {
    "windows": [
        "powershell",
        "-NoProfile",
        "-Command",
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$ports = @(); "
        "$ports += Get-CimInstance Win32_SerialPort | ForEach-Object { "
        "if ($_.DeviceID -and $_.Name) { $_.Name } elseif ($_.DeviceID) { $_.DeviceID } }; "
        "$ports += Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match '\\(COM\\d+\\)' } "
        "| Select-Object -ExpandProperty Name; "
        "$ports | Where-Object { $_ } | Select-Object -Unique",
    ],
    "linux": ["bash", "-lc", "ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null"],
    "darwin": ["bash", "-lc", "ls /dev/cu.* /dev/tty.* 2>/dev/null"],
}
_SERIAL_VALUE_PATTERNS = (
    re.compile(r"\((COM\d+)\)", re.IGNORECASE),
    re.compile(r"^(COM\d+)$", re.IGNORECASE),
    re.compile(r"(/dev/\S+)", re.IGNORECASE),
)


class SerialTool:
    def __init__(self, port: str, baudrate: int | str = 115200, *, timeout: float = 1.0, **kwargs: Any) -> None:
        if serial is None:
            raise RuntimeError("pyserial is required for serial control")
        self.port = normalize_serial_port(port)
        self.baudrate = int(baudrate)
        self._serial = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=timeout, **kwargs)

    @property
    def is_open(self) -> bool:
        return bool(getattr(self._serial, "is_open", False))

    def write(self, data: bytes | str) -> int:
        payload = data.encode() if isinstance(data, str) else data
        return int(self._serial.write(payload))

    def query(self, data: bytes | str, *, read_size: int = 4096, timeout: float | None = None) -> bytes:
        old_timeout = getattr(self._serial, "timeout", None)
        if timeout is not None:
            self._serial.timeout = timeout
        try:
            self.write(data)
            return self.read(read_size)
        finally:
            if timeout is not None:
                self._serial.timeout = old_timeout

    def read(self, size: int = 1) -> bytes:
        return bytes(self._serial.read(size))

    def readline(self) -> bytes:
        return bytes(self._serial.readline())

    def readlines(self) -> list[bytes]:
        return list(self._serial.readlines())

    def flush(self) -> None:
        self._serial.flush()

    def close(self) -> None:
        self._serial.close()

    def __enter__(self) -> "SerialTool":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def list_serial_port_entries(selected_serial: str | None = None) -> list[dict[str, str]]:
    del selected_serial
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in [*_pyserial_port_lines(), *_run_lines(_SERIAL_COMMANDS.get(platform.system().strip().lower(), []))]:
        value = normalize_serial_port(_extract_serial_value(line))
        if value and value not in seen:
            seen.add(value)
            entries.append({"label": _compose_serial_label(line, value), "value": value})
    return entries


def list_serial_ports(selected_serial: str | None = None) -> list[str]:
    return [item["value"] for item in list_serial_port_entries(selected_serial)]


def normalize_serial_port(port: str) -> str:
    value = str(port or "").strip()
    match = re.match(r"^(COM\d+)", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    for separator in ("(", " "):
        if separator in value:
            value = value.split(separator, 1)[0].strip()
    return value


def _run_lines(command: list[str]) -> list[str]:
    if not command:
        return []
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
        **_hidden_process_kwargs(),
    )
    if completed.returncode != 0:
        return []
    return [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]


def _pyserial_port_lines() -> list[str]:
    if serial is None:
        return []
    try:
        from serial.tools import list_ports  # type: ignore
    except ImportError:
        return []
    lines: list[str] = []
    for port in list_ports.comports():
        device = str(getattr(port, "device", "") or "").strip()
        description = str(getattr(port, "description", "") or "").strip()
        if not device:
            continue
        label = description if description and device.lower() in description.lower() else f"{description} ({device})"
        if not description:
            label = device
        lines.append(label)
    return lines


def _hidden_process_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = 0
    return {
        "startupinfo": startup_info,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def _compose_serial_label(label: str, value: str) -> str:
    text = str(label or "").strip()
    return text if value.lower() in text.lower() else f"{text} ({value})"


def _extract_serial_value(text: str) -> str:
    raw = str(text or "").strip()
    for pattern in _SERIAL_VALUE_PATTERNS:
        match = pattern.search(raw)
        if match:
            value = str(match.group(1) or "").strip()
            return value.upper() if value.upper().startswith("COM") else value
    return ""
