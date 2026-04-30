from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import requests


@dataclass(frozen=True)
class JiraBasicAuth:
    username: str
    password: str

    def authorization_header(self) -> str:
        token = f"{self.username}:{self.password}".encode("utf-8")
        return "Basic " + base64.b64encode(token).decode("ascii")

    def apply(self, session: "requests.Session") -> None:
        session.auth = (self.username, self.password)

    def redact(self) -> dict[str, Any]:
        return {"username": self.username, "password": "***"}
