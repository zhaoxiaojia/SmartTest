from __future__ import annotations

import os
import re
import subprocess


_ADB_SERIAL_ARG_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


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


def _hidden_process_kwargs() -> dict:
    if os.name != "nt":
        return {}
    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = 0
    return {
        "startupinfo": startup_info,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def list_adb_devices() -> list[str]:
    try:
        result = subprocess.run(
            ["adb", "devices"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=False,
            check=False,
            **_hidden_process_kwargs(),
        )
    except FileNotFoundError:
        return []

    if result.returncode != 0:
        return []
    return parse_adb_devices_output(_decode_adb_output(result.stdout))


def resolve_adb_serial_for_command(selected_serial: str | None) -> str | None:
    serial = str(selected_serial or "").strip()
    if not serial:
        return None
    if not _ADB_SERIAL_ARG_RE.fullmatch(serial):
        return None
    return serial
