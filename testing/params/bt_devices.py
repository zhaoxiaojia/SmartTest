from __future__ import annotations

import re
import subprocess

from .adb_devices import _decode_adb_output, resolve_adb_serial_for_command


_MAC_PATTERN = r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})"


def parse_paired_bluetooth_devices_output(output: str) -> list[str]:
    text = str(output or "")
    devices: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        inline = re.search(rf"Name\s*=\s*(.*?)\s*\[{_MAC_PATTERN}\]", line)
        if inline:
            name = inline.group(1).strip()
            mac = inline.group(2).upper()
            label = f"{name} [{mac}]"
            if mac not in seen:
                seen.add(mac)
                devices.append(label)

    if devices:
        return devices

    pending_name: str | None = None
    in_bonded_section = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if in_bonded_section:
                pending_name = None
            continue

        if re.search(r"(Bonded|Paired)\s+devices\s*:", line, flags=re.IGNORECASE):
            in_bonded_section = True
            pending_name = None
            continue

        if not in_bonded_section:
            continue

        if re.match(r"^[A-Za-z][A-Za-z0-9 _/-]*:$", line) and not re.match(
            r"^(Name|Address|Peer)\s*:", line,
            flags=re.IGNORECASE,
        ):
            pending_name = None
            break

        name_match = re.search(r"Name\s*(?:=|:)\s*(.+)", line)
        if name_match:
            pending_name = name_match.group(1).strip()
            continue

        mac_match = re.search(rf"(?:Address|Peer)\s*(?:=|:)\s*{_MAC_PATTERN}", line)
        if mac_match and pending_name:
            mac = mac_match.group(1).upper()
            label = f"{pending_name} [{mac}]"
            if mac not in seen:
                seen.add(mac)
                devices.append(label)
            pending_name = None

    return devices


def list_paired_bluetooth_devices(selected_serial: str | None = None) -> list[str]:
    serial = resolve_adb_serial_for_command(selected_serial)
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["shell", "dumpsys", "bluetooth_manager"])
    try:
        result = subprocess.run(
            cmd,
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
    return parse_paired_bluetooth_devices_output(_decode_adb_output(result.stdout))
