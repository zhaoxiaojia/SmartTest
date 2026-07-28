from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from support.ai import (
    AIConfigurationError,
    AIKeyResolver,
    available_models,
    model_by_id,
    select_model,
    selected_model_id,
)


_MODEL_DISPLAY_NAMES = {
    "company-kimi": "Company Intranet Kimi",
    "public-deepseek": "Public DeepSeek",
}


class AISettingsBridge(QObject):
    stateChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(
        self,
        *,
        available_models_function: Callable[[], Any] = available_models,
        model_by_id_function: Callable[[str], Any] = model_by_id,
        selected_model_id_function: Callable[[], str] = selected_model_id,
        select_model_function: Callable[[str], None] = select_model,
        key_resolver: AIKeyResolver | None = None,
    ):
        super().__init__()
        self._available_models = available_models_function
        self._model_by_id = model_by_id_function
        self._selected_model_id = selected_model_id_function
        self._select_model = select_model_function
        self._key_resolver = key_resolver or AIKeyResolver()

    @Slot(result="QVariantMap")
    def state(self) -> dict[str, Any]:
        models = []
        for template in self._available_models():
            try:
                configured = self._key_resolver.is_configured(template.credential_id)
            except (AIConfigurationError, OSError, ValueError, TypeError):
                configured = False
            models.append(
                {
                    "id": template.id,
                    "display_name": self.tr(_MODEL_DISPLAY_NAMES[template.id]),
                    "configured": bool(configured),
                }
            )
        return {
            "selected_model_id": self._selected_model_id(),
            "models": models,
        }

    @Slot(str, result=bool)
    def selectModel(self, model_id: str) -> bool:
        try:
            self._model_by_id(str(model_id or "").strip())
            self._select_model(str(model_id or "").strip())
        except (AIConfigurationError, OSError, ValueError, TypeError):
            self.stateChanged.emit()
            self._emit_error("Unable to select the AI model. Try again.")
            return False
        self.stateChanged.emit()
        return True

    @Slot(str, str, result=bool)
    def saveApiKey(self, model_id: str, key: str) -> bool:
        clean_key = str(key or "").strip()
        if not clean_key:
            self._emit_error("Enter an API key.")
            return False
        try:
            template = self._model_by_id(str(model_id or "").strip())
            self._key_resolver.store(template.credential_id, clean_key)
        except (AIConfigurationError, OSError, ValueError, TypeError):
            self._emit_error("Unable to save the API key. Check the key and try again.")
            return False
        self.stateChanged.emit()
        return True

    @Slot(str, result=bool)
    def clearApiKey(self, model_id: str) -> bool:
        try:
            template = self._model_by_id(str(model_id or "").strip())
            self._key_resolver.clear(template.credential_id)
        except (AIConfigurationError, OSError, ValueError, TypeError):
            self._emit_error("Unable to clear the API key. Try again.")
            return False
        self.stateChanged.emit()
        return True

    def _emit_error(self, message: str) -> None:
        self.errorOccurred.emit(self.tr(message))
