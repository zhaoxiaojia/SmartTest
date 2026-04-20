from __future__ import annotations

from typing import Any, Iterable

from AI.config.api_key_resolver import AIApiKeyResolver
from AI.config.secret_store import AISecretStore
from AI.core.models import AIChatMessage, AIChatResponse
from AI.providers.amlogic_defaults import (
    DEFAULT_AMLOGIC_BASE_URL,
    DEFAULT_AMLOGIC_MODEL,
    decode_default_amlogic_api_key,
)
from AI.transport.client import AIChatClient, AIClientConfig


class AmlogicAIProvider:
    def __init__(
        self,
        client: AIChatClient,
        *,
        default_model: str = DEFAULT_AMLOGIC_MODEL,
    ):
        self._default_model = default_model
        self._client = client

    def chat(
        self,
        messages: Iterable[AIChatMessage],
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


def create_default_amlogic_provider(
    *,
    secret_store: AISecretStore | None = None,
    base_url: str = DEFAULT_AMLOGIC_BASE_URL,
    default_model: str = DEFAULT_AMLOGIC_MODEL,
) -> AmlogicAIProvider:
    resolved_secret_store = secret_store or AISecretStore()
    resolver = AIApiKeyResolver(
        resolved_secret_store,
        default_api_key_factory=decode_default_amlogic_api_key,
    )
    client = AIChatClient(
        AIClientConfig(base_url=base_url),
        api_key_provider=resolver.resolve,
    )
    return AmlogicAIProvider(client, default_model=default_model)
