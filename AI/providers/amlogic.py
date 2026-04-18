from __future__ import annotations

from typing import Any, Iterable

from AI.config import AISecretStore, DEFAULT_AI_BASE_URL, DEFAULT_AI_MODEL
from AI.core.models import AIChatMessage, AIChatResponse
from AI.transport import AIChatClient, AIClientConfig


class AmlogicAIProvider:
    def __init__(
        self,
        *,
        client: AIChatClient | None = None,
        secret_store: AISecretStore | None = None,
        base_url: str = DEFAULT_AI_BASE_URL,
        default_model: str = DEFAULT_AI_MODEL,
    ):
        self._default_model = default_model
        self._client = client or AIChatClient(
            AIClientConfig(base_url=base_url),
            secret_store=secret_store or AISecretStore(),
        )

    def chat(
        self,
        messages: Iterable[AIChatMessage | dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AIChatResponse:
        return self._client.chat_completion(
            messages,
            model=model or self._default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
