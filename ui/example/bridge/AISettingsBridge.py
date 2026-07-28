from __future__ import annotations

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


class AISettingsBridge(QObject):
    stateChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(self):
        super().__init__()
        self._key_resolver = AIKeyResolver()

    @Slot(result="QVariantMap")
    def state(self) -> dict[str, Any]:
        selected = selected_model_id()
        selected_index = -1
        selected_configured = False
        models = []
        for index, template in enumerate(available_models()):
            try:
                configured = self._key_resolver.is_configured(template.credential_id)
            except (AIConfigurationError, OSError, ValueError, TypeError):
                configured = False
            if template.id == selected:
                selected_index = index
                selected_configured = bool(configured)
            models.append(
                {
                    "id": template.id,
                    "display_name": (
                        self.tr("Company Intranet Kimi")
                        if template.id == "company-kimi"
                        else self.tr("Public DeepSeek")
                    ),
                    "configured": bool(configured),
                }
            )
        return {
            "selected_model_id": selected,
            "selected_model_index": selected_index,
            "selected_model_configured": selected_configured,
            "models": models,
        }

    @Slot(str, result=bool)
    def selectModel(self, model_id: str) -> bool:
        try:
            select_model(str(model_id or "").strip())
        except (AIConfigurationError, OSError, ValueError, TypeError):
            self.stateChanged.emit()
            self.errorOccurred.emit(self.tr("Unable to select the AI model. Try again."))
            return False
        self.stateChanged.emit()
        return True

    @Slot(str, str, result=bool)
    def saveApiKey(self, model_id: str, key: str) -> bool:
        clean_key = str(key or "").strip()
        if not clean_key:
            self.errorOccurred.emit(self.tr("Enter an API key."))
            return False
        try:
            template = model_by_id(str(model_id or "").strip())
            self._key_resolver.store(template.credential_id, clean_key)
        except (AIConfigurationError, OSError, ValueError, TypeError):
            self.errorOccurred.emit(self.tr("Unable to save the API key. Check the key and try again."))
            return False
        self.stateChanged.emit()
        return True

    @Slot(str, result=bool)
    def clearApiKey(self, model_id: str) -> bool:
        try:
            template = model_by_id(str(model_id or "").strip())
            self._key_resolver.clear(template.credential_id)
        except (AIConfigurationError, OSError, ValueError, TypeError):
            self.errorOccurred.emit(self.tr("Unable to clear the API key. Try again."))
            return False
        self.stateChanged.emit()
        return True
