from __future__ import annotations

import json
from typing import Any

from AI.core.models import AIChatMessage, AIChatResponse
from AI.providers.amlogic import AmlogicAIProvider

_DEFAULT_SYSTEM_PROMPT = (
    "You are SmartTest's Jira analysis assistant. "
    "Answer based on the provided Jira context, summarize clearly, "
    "call out risks, and state when the available data is insufficient."
)


class JiraAIAnalysisService:
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
        prompt: str,
        *,
        jira_context: Any = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AIChatResponse:
        messages = [
            AIChatMessage(role="system", content=self._system_prompt),
            AIChatMessage(role="user", content=_compose_user_prompt(prompt, jira_context)),
        ]
        return self._provider.chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )


def _compose_user_prompt(prompt: str, jira_context: Any) -> str:
    if jira_context is None:
        return prompt
    context_text = jira_context if isinstance(jira_context, str) else json.dumps(jira_context, ensure_ascii=False, indent=2)
    return f"{prompt}\n\nJira context:\n{context_text}"
