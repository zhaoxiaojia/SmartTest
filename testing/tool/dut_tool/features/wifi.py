from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WifiConnectParams:
    ssid: str
    password: str = ""
    security: str = ""
    hidden: bool = False
    lan: bool = True
    timeout_s: int = 90
