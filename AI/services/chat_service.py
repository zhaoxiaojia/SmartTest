from __future__ import annotations

from typing import Iterable

from AI.core.models import AIChatMessage, AIChatResponse
from AI.providers.amlogic import AmlogicAIProvider, create_default_amlogic_provider

_DEFAULT_SYSTEM_PROMPT = (
    "You are SmartTest's AI assistant. Help with test planning, failure analysis, "
    "Jira triage, logs, pytest, adb, network tools, and SmartTest usage. "
    "Use Markdown for readable answers. State clearly when provided context is insufficient."
)


class AIChatService:
    def __init__(
        self,
        provider: AmlogicAIProvider,
        *,
        system_prompt: str = _DEFAULT_SYSTEM_PROMPT,
    ):
        self._provider = provider
        self._system_prompt = system_prompt

    def ask(
        self,
        messages: Iterable[AIChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIChatResponse:
        request_messages = [AIChatMessage(role="system", content=self._system_prompt)]
        request_messages.extend(messages)
        return self._provider.chat(
            request_messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )


def create_default_ai_chat_service() -> AIChatService:
    return AIChatService(create_default_amlogic_provider())
