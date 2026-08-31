from __future__ import annotations

import base64
from dataclasses import dataclass


@dataclass(frozen=True)
class JiraBasicAuth:
    username: str
    password: str

    def authorization_header(self) -> str:
        token = f"{self.username}:{self.password}".encode("utf-8")
        return "Basic " + base64.b64encode(token).decode("ascii")
