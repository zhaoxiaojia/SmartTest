from __future__ import annotations

import os
from typing import Callable

from AI.config.defaults import SMARTTEST_AI_API_KEY_ENV
from AI.core.errors import AIConfigurationError
from AI.config.secret_store import AISecretStore


class AIApiKeyResolver:
    def __init__(
        self,
        secret_store: AISecretStore,
        *,
        env_var_name: str = SMARTTEST_AI_API_KEY_ENV,
        default_api_key_factory: Callable[[], str] | None = None,
    ):
        self._secret_store = secret_store
        self._env_var_name = env_var_name
        self._default_api_key_factory = default_api_key_factory

    def resolve(self) -> str:
        env_value = os.getenv(self._env_var_name, "").strip()
        if env_value:
            return env_value

        stored_value = self._secret_store.read_api_key()
        if stored_value:
            return stored_value

        if self._default_api_key_factory is None:
            raise AIConfigurationError("AI API key is not configured")
        default_value = self._default_api_key_factory().strip()
        if not default_value:
            raise AIConfigurationError("AI API key is not configured")
        self._secret_store.write_api_key(default_value)
        return default_value
