from __future__ import annotations

import re
import shutil
import subprocess
import sys

from testing.params.adb_devices import resolve_adb_serial_for_command
from testing.runtime.config import current_dut_serial


NO_BLUETOOTH_TARGET = "None"
_ADDRESS_PATTERN = re.compile(r"(?:[0-9A-Fa-fXx]{2}:){5}[0-9A-Fa-fXx]{2}")
_BONDED_DEVICE_PATTERN = re.compile(
    r"^\s*((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s+\[[^\]]+\]\s+(.+?)\s*$",
    re.IGNORECASE,
)
_LEGACY_NAME_PATTERN = re.compile(
    r"record\s+\d+\s+((?:[0-9A-Fa-fXx]{2}:){5}[0-9A-Fa-fXx]{2}).*?\bname:\"([^\"]*)\"",
    re.IGNORECASE,
)


def list_connected_bluetooth_targets(selected_serial: str | None = None) -> list[str]:
    return [NO_BLUETOOTH_TARGET, *read_connected_bluetooth_targets(adb_serial=selected_serial)]


def read_connected_bluetooth_targets(*, adb_serial: str | None = None) -> list[str]:
    raw = read_bluetooth_manager_dump(adb_serial=adb_serial)
    return connected_bluetooth_targets_from_dumpsys(raw)


def read_bluetooth_manager_dump(*, adb_serial: str | None = None) -> str:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        raise RuntimeError("adb is not available in PATH.")

    selected_serial = str(adb_serial or current_dut_serial()).strip()
    command_serial = resolve_adb_serial_for_command(selected_serial)
    cmd = [adb_executable]
    if command_serial:
        cmd.extend(["-s", command_serial])
    cmd.extend(["shell", "dumpsys", "bluetooth_manager"])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Failed to read bluetooth_manager dumpsys: {message}")
    return result.stdout or ""


def connected_bluetooth_targets_from_dumpsys(raw: str) -> list[str]:
    name_by_address = _bluetooth_names_by_address(raw)
    addresses = _connected_bluetooth_addresses(raw)
    targets: list[str] = []
    for address in addresses:
        display_address, name = _display_address_and_name(address, name_by_address)
        targets.append(f"{name} [{display_address}]" if name else display_address)
    return targets


def _bluetooth_names_by_address(raw: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for line in (raw or "").splitlines():
        match = _BONDED_DEVICE_PATTERN.match(line)
        if not match:
            continue
        address = _normalize_address(match.group(1))
        name = match.group(2).strip()
        if address and name:
            names[address] = name
    for match in _LEGACY_NAME_PATTERN.finditer(raw or ""):
        address = _normalize_address(match.group(1))
        name = match.group(2).strip()
        if address and name:
            names[address] = name
    return names


def _display_address_and_name(address: str, name_by_address: dict[str, str]) -> tuple[str, str]:
    normalized = _normalize_address(address)
    tail = _address_tail(normalized)
    if _is_masked_address(normalized) and tail:
        for known_address, known_name in name_by_address.items():
            if not _is_masked_address(known_address) and _address_tail(known_address) == tail and known_name.strip():
                return known_address, known_name.strip()

    exact_name = name_by_address.get(normalized, "").strip()
    if exact_name:
        return normalized, exact_name

    if tail:
        for known_address, known_name in name_by_address.items():
            if _address_tail(known_address) == tail and known_name.strip():
                return known_address, known_name.strip()
    return normalized, ""


def _connected_bluetooth_addresses(raw: str) -> list[str]:
    addresses: list[str] = []
    seen: set[str] = set()
    pending_peer = ""
    pending_state_machine = ""

    for line in (raw or "").splitlines():
        text = line.strip()
        lower = text.lower()

        if "statemachine" in lower and " for " in lower:
            pending_state_machine = _first_address(text)
            if "state=connected" in lower:
                _append_address(addresses, seen, pending_state_machine)
                pending_state_machine = ""
            continue

        if pending_state_machine and "state=connected" in lower:
            _append_address(addresses, seen, pending_state_machine)
            pending_state_machine = ""
            continue

        if "state=disconnected" in lower:
            pending_state_machine = ""

        if lower.startswith("peer:") or " active peer:" in lower:
            pending_peer = _first_address(text)
            continue

        if pending_peer and lower.startswith("connected:"):
            if "true" in lower:
                _append_address(addresses, seen, pending_peer)
            pending_peer = ""

        if "mcurrentdevice:" in lower:
            _append_address(addresses, seen, _first_address(text))

    return addresses


def _append_address(addresses: list[str], seen: set[str], address: str) -> None:
    normalized = _normalize_address(address)
    if normalized and normalized not in seen and normalized != "00:00:00:00:00:00":
        addresses.append(normalized)
        seen.add(normalized)


def _first_address(text: str) -> str:
    match = _ADDRESS_PATTERN.search(text or "")
    return match.group(0) if match else ""


def _normalize_address(address: str) -> str:
    return str(address or "").strip().upper()


def _address_tail(address: str) -> str:
    parts = _normalize_address(address).split(":")
    if len(parts) != 6:
        return ""
    return ":".join(parts[-2:])


def _is_masked_address(address: str) -> bool:
    return "XX" in _normalize_address(address).split(":")


def _subprocess_creationflags() -> int:
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return subprocess.CREATE_NO_WINDOW
    return 0
