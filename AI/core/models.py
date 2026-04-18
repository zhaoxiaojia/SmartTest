from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AIChatMessage:
    role: str
    content: Any
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[dict[str, Any], ...] = ()

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "role": self.role,
            "content": self.content,
        }
        if self.name:
            payload["name"] = self.name
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            payload["tool_calls"] = list(self.tool_calls)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AIChatMessage":
        return cls(
            role=str(payload.get("role", "")),
            content=payload.get("content"),
            name=payload.get("name"),
            tool_call_id=payload.get("tool_call_id"),
            tool_calls=tuple(payload.get("tool_calls") or ()),
        )


@dataclass(frozen=True)
class AIChatChoice:
    index: int
    message: AIChatMessage
    finish_reason: str | None = None


@dataclass(frozen=True)
class AIChatResponse:
    response_id: str | None
    model: str | None
    created: int | None
    choices: tuple[AIChatChoice, ...] = field(default_factory=tuple)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def first_message(self) -> AIChatMessage | None:
        return self.choices[0].message if self.choices else None

    @property
    def text(self) -> str | None:
        first_message = self.first_message
        if first_message is None:
            return None
        return first_message.content if isinstance(first_message.content, str) else None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AIChatResponse":
        choices = tuple(
            AIChatChoice(
                index=int(item.get("index", 0)),
                message=AIChatMessage.from_payload(item.get("message") or {}),
                finish_reason=item.get("finish_reason"),
            )
            for item in payload.get("choices") or ()
        )
        created = payload.get("created")
        return cls(
            response_id=payload.get("id"),
            model=payload.get("model"),
            created=int(created) if created is not None else None,
            choices=choices,
            raw=payload,
        )
