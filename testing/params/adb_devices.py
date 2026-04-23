from __future__ import annotations

import subprocess


def _decode_adb_output(output: bytes | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    for encoding in ("utf-8", "mbcs", "gbk", "latin-1"):
        try:
            return output.decode(encoding)
        except UnicodeDecodeError:
            continue
    return output.decode("utf-8", errors="ignore")


def parse_adb_devices_output(output: str) -> list[str]:
    devices: list[str] = []
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        if len(parts) < 2 or parts[1] != "device":
            continue
        serial = str(parts[0] or "").strip()
        if serial and serial not in devices:
            devices.append(serial)
    return devices


def list_adb_devices() -> list[str]:
    try:
        result = subprocess.run(
            ["adb", "devices"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=False,
            check=False,
        )
    except FileNotFoundError:
        return []

    if result.returncode != 0:
        return []
    return parse_adb_devices_output(_decode_adb_output(result.stdout))


def resolve_adb_serial_for_command(selected_serial: str | None) -> str | None:
    devices = list_adb_devices()
    if len(devices) <= 1:
        return None
    serial = str(selected_serial or "").strip()
    if serial and serial in devices:
        return serial
    return serial or None
