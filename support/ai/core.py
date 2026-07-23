from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class AIError(RuntimeError):
    pass


class AIConfigurationError(AIError):
    pass


class AITransportError(AIError):
    def __init__(
        self,
        message: str,
        *,
        category: str = "transport",
        status_code: int | None = None,
        timeout: float | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.timeout = timeout


class AIResponseError(AIError):
    pass


@dataclass(frozen=True)
class AIClientConfig:
    base_url: str
    model: str
    api_key: str
    timeout: float = 120.0
    max_tokens: int = 2048


@dataclass(frozen=True)
class AIChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AIChatResponse:
    content: str
    model: str = ""
    usage: dict[str, Any] | None = None
