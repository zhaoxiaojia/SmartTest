from __future__ import annotations

import os
import subprocess

from testing.params.adb_devices import resolve_adb_serial_for_command


def subprocess_creationflags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def adb_base_cmd(*, adb_executable: str, adb_serial: str | None = None) -> list[str]:
    command = [adb_executable]
    serial = resolve_adb_serial_for_command(adb_serial)
    if serial:
        command.extend(["-s", serial])
    return command
