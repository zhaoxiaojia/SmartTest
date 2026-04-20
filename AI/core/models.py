from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AIChatMessage:
    role: str
    content: Any
    name: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "role": self.role,
            "content": self.content,
        }
        if self.name:
            payload["name"] = self.name
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AIChatMessage":
        return cls(
            role=str(payload.get("role", "")),
            content=payload.get("content"),
            name=payload.get("name"),
        )


@dataclass(frozen=True)
class AIChatResponse:
    response_id: str | None
    model: str | None
    created: int | None
    message: AIChatMessage | None = None
    finish_reason: str | None = None

    @property
    def text(self) -> str | None:
        if self.message is None:
            return None
        return self.message.content if isinstance(self.message.content, str) else None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AIChatResponse":
        created = payload.get("created")
        first_choice = next(iter(payload.get("choices") or ()), None)
        message = None
        finish_reason = None
        if isinstance(first_choice, dict):
            message = AIChatMessage.from_payload(first_choice.get("message") or {})
            finish_reason = first_choice.get("finish_reason")
        return cls(
            response_id=payload.get("id"),
            model=payload.get("model"),
            created=int(created) if created is not None else None,
            message=message,
            finish_reason=finish_reason,
        )
