from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from typing import Any


_REMOVABLE_DRIVE_COMMANDS: dict[str, list[str]] = {
    "windows": [
        "powershell",
        "-NoProfile",
        "-Command",
        "(Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 } | Select-Object -ExpandProperty DeviceID)",
    ],
    "linux": ["bash", "-lc", "lsblk -nrpo NAME,RM | awk '$2==1 {print $1}'"],
    "darwin": ["bash", "-lc", "diskutil list external physical | awk '/\\/dev\\// {print $1}'"],
}

@dataclass(frozen=True)
class HostFieldSpec:
    key: str
    value_type: str
    default: Any = ""
    enum_values: list[Any] | None = None


class LocalHostTool:
    def __init__(self, *, system_name: str | None = None) -> None:
        self._system_name = str(system_name or platform.system()).strip().lower()

    def list_removable_drives(self) -> list[str]:
        return self._run_lines(_REMOVABLE_DRIVE_COMMANDS.get(self._system_name, []))

    def serial_env_field_specs(self, *, device_type: str, port_options: list[Any]) -> list[HostFieldSpec]:
        if str(device_type or "").strip() != "uart":
            return []
        return [
            HostFieldSpec(key="port", value_type="enum", default="", enum_values=list(port_options)),
            HostFieldSpec(key="baud", value_type="int", default=115200),
        ]

    def serial_env_fields(self, *, device_type: str, config: dict[str, Any], port_options: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                "key": spec.key,
                "type": spec.value_type,
                "default": spec.default,
                "enum_values": list(spec.enum_values or []),
                "value": config.get(spec.key, spec.default),
            }
            for spec in self.serial_env_field_specs(device_type=device_type, port_options=port_options)
        ]

    @staticmethod
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
        values: list[str] = []
        for line in str(completed.stdout or "").splitlines():
            text = str(line or "").strip()
            if text and text not in values:
                values.append(text)
        return values


_LOCAL_HOST_TOOL = LocalHostTool()


def local_host_tool() -> LocalHostTool:
    return _LOCAL_HOST_TOOL


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
