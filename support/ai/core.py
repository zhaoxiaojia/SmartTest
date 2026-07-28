from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
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
    request_options: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_options", _freeze_request_options(self.request_options)
        )


@dataclass(frozen=True)
class AIModelTemplate:
    id: str
    credential_id: str
    base_url: str
    model_id: str
    timeout: float = 120.0
    max_tokens: int = 2048
    request_options: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_options", _freeze_request_options(self.request_options)
        )


def _freeze_request_options(
    options: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if options is None:
        return None
    if not isinstance(options, Mapping):
        raise AIConfigurationError("AI request options are invalid")
    return MappingProxyType(
        {str(key): _freeze_request_value(value) for key, value in options.items()}
    )


def _freeze_request_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_request_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_request_value(item) for item in value)
    return value


@dataclass(frozen=True)
class AIChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AIChatResponse:
    content: str
    model: str = ""
    usage: dict[str, Any] | None = None
