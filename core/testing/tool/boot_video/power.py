from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class PowerResult:
    success: bool
    perf_time: float
    wall_time: str
    message: str = ""


class PowerController(Protocol):
    def connect(self) -> None: ...
    def power_on(self) -> PowerResult: ...
    def power_off(self) -> PowerResult: ...
    def disconnect(self) -> None: ...
    def get_status(self) -> str: ...


class MockPowerController:
    def __init__(self) -> None:
        self._connected = False
        self._status = "off"

    def connect(self) -> None:
        self._connected = True

    def power_on(self) -> PowerResult:
        if not self._connected:
            self.connect()
        result = PowerResult(
            success=True,
            perf_time=time.perf_counter(),
            wall_time=datetime.now().astimezone().isoformat(timespec="milliseconds"),
            message="Mock power on succeeded.",
        )
        self._status = "on"
        return result

    def power_off(self) -> PowerResult:
        result = PowerResult(
            success=True,
            perf_time=time.perf_counter(),
            wall_time=datetime.now().astimezone().isoformat(timespec="milliseconds"),
            message="Mock power off succeeded.",
        )
        self._status = "off"
        return result

    def disconnect(self) -> None:
        self._connected = False

    def get_status(self) -> str:
        return self._status
