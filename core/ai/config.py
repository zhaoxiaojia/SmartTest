from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .client import AIChatClient
from .core import AIClientConfig, AIConfigurationError, AIModelTemplate

LEGACY_DPAPI_ENTROPY = b"SmartTest.AI.SecretStore.v1"
_KIMI_CREDENTIAL_ID = "company-kimi"
_MODELS = (
    AIModelTemplate(
        id="company-kimi",
        display_name="Company Intranet Kimi",
        credential_id="company-kimi",
        base_url="https://llm.amlogic.com/8d1b5b4c",
        model_id="Amlogic_Local/Kimi-K2.7-Code",
        request_options={"chat_template_kwargs": {"enable_thinking": False}},
    ),
    AIModelTemplate(
        id="public-deepseek",
        display_name="Public DeepSeek",
        credential_id="public-deepseek",
        base_url="https://api.deepseek.com",
        model_id="deepseek-v4-flash",
        request_options={"thinking": {"type": "disabled"}},
    ),
)
_MODELS_BY_ID = {model.id: model for model in _MODELS}
_ENVIRONMENT_CREDENTIALS = {
    "company-kimi": ("SMARTTEST_AI_API_KEY", "SMARTTEST_KIMI_API_KEY"),
    "public-deepseek": ("DEEPSEEK_API_KEY", "SMARTTEST_DEEPSEEK_API_KEY"),
}


def available_models() -> tuple[AIModelTemplate, ...]:
    return _MODELS


def model_by_id(model_id: str) -> AIModelTemplate:
    try:
        return _MODELS_BY_ID[str(model_id)]
    except KeyError:
        raise AIConfigurationError("AI model is unavailable") from None


def selected_model_id() -> str:
    try:
        payload = _read_json(_default_settings_path())
        model_id = str(payload.get("selected_model_id") or _MODELS[0].id)
        model_by_id(model_id)
        return model_id
    except (OSError, ValueError, TypeError, AIConfigurationError):
        return _MODELS[0].id


def select_model(model_id: str) -> None:
    model_by_id(model_id)
    _atomic_write_json(_default_settings_path(), {"selected_model_id": str(model_id)})


class AIKeyResolver:
    def resolve(self, credential_id: str) -> str:
        credential_id = _credential_id(credential_id)
        payload = self._read_payload()
        credentials = payload.get("credentials")
        if isinstance(credentials, dict) and credential_id in credentials:
            return _decrypt_key(credentials[credential_id])
        if credential_id == _KIMI_CREDENTIAL_ID:
            legacy_key = _legacy_key(payload)
            if legacy_key:
                self.store(credential_id, legacy_key)
                return legacy_key
        key = _environment_key(credential_id)
        if key:
            return key
        raise AIConfigurationError("AI API key is unavailable")

    def store(self, credential_id: str, key: str) -> Path:
        credential_id = _credential_id(credential_id)
        key = str(key or "").strip()
        if os.name != "nt" or not key:
            raise AIConfigurationError("AI API key cannot be stored")
        payload = self._read_payload()
        credentials = payload.get("credentials")
        if not isinstance(credentials, dict):
            credentials = {}
        credentials[credential_id] = base64.b64encode(_dpapi_protect(key.encode("utf-8"))).decode("ascii")
        payload["credentials"] = credentials
        if credential_id == _KIMI_CREDENTIAL_ID:
            payload.pop("api_key_dpapi", None)
            payload.pop("encrypted_api_key", None)
        path = self._path()
        _atomic_write_json(path, payload)
        return path

    def clear(self, credential_id: str) -> None:
        credential_id = _credential_id(credential_id)
        payload = self._read_payload()
        credentials = payload.get("credentials")
        if isinstance(credentials, dict):
            credentials.pop(credential_id, None)
            if credentials:
                payload["credentials"] = credentials
            else:
                payload.pop("credentials", None)
        if credential_id == _KIMI_CREDENTIAL_ID:
            payload.pop("api_key_dpapi", None)
            payload.pop("encrypted_api_key", None)
        _atomic_write_json(self._path(), payload)

    def is_configured(self, credential_id: str) -> bool:
        credential_id = _credential_id(credential_id)
        try:
            payload = self._read_payload()
        except AIConfigurationError:
            return False
        credentials = payload.get("credentials")
        if isinstance(credentials, dict) and credentials.get(credential_id):
            return True
        if credential_id == _KIMI_CREDENTIAL_ID and (
            payload.get("api_key_dpapi") or payload.get("encrypted_api_key")
        ):
            return True
        return bool(_environment_key(credential_id))

    def _path(self) -> Path:
        return _default_store_path()

    def _read_payload(self) -> dict[str, Any]:
        path = self._path()
        if not path.exists():
            return {}
        try:
            payload = _read_json(path)
        except (OSError, ValueError, TypeError) as exc:
            raise AIConfigurationError("AI API key is unavailable") from exc
        if not isinstance(payload, dict):
            raise AIConfigurationError("AI API key is unavailable")
        return payload


def create_chat_client(model_id: str | None = None) -> AIChatClient:
    template = model_by_id(selected_model_id() if model_id is None else model_id)
    key = AIKeyResolver().resolve(template.credential_id)
    return AIChatClient(
        AIClientConfig(
            base_url=template.base_url,
            model=template.model_id,
            api_key=key,
            timeout=template.timeout,
            max_tokens=template.max_tokens,
            request_options=template.request_options,
        )
    )


def _credential_id(credential_id: str) -> str:
    credential_id = str(credential_id or "").strip()
    if not credential_id:
        raise AIConfigurationError("AI credential is unavailable")
    return credential_id


def _environment_key(credential_id: str) -> str:
    for name in _ENVIRONMENT_CREDENTIALS.get(credential_id, ()):
        key = str(os.getenv(name) or "").strip()
        if key:
            return key
    return ""


def _legacy_key(payload: dict[str, Any]) -> str:
    try:
        if payload.get("api_key_dpapi"):
            encrypted = base64.b64decode(str(payload["api_key_dpapi"]), validate=True)
            return _dpapi_unprotect(encrypted).decode("utf-8").strip()
        if payload.get("encrypted_api_key"):
            encrypted = base64.b64decode(str(payload["encrypted_api_key"]), validate=True)
            return _dpapi_unprotect(encrypted, entropy=LEGACY_DPAPI_ENTROPY).decode("utf-8").strip()
    except Exception as exc:
        raise AIConfigurationError("AI API key is unavailable") from exc
    return ""


def _decrypt_key(value: Any) -> str:
    try:
        encrypted = base64.b64decode(str(value), validate=True)
        key = _dpapi_unprotect(encrypted).decode("utf-8").strip()
    except Exception as exc:
        raise AIConfigurationError("AI API key is unavailable") from exc
    if not key:
        raise AIConfigurationError("AI API key is unavailable")
    return key


def _default_store_path() -> Path:
    return _application_data_directory() / "secret_store.json"


def _default_settings_path() -> Path:
    return _application_data_directory() / "settings.json"


def _application_data_directory() -> Path:
    base = os.getenv("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Local"
    return root / "Amlogic" / "SmartTest" / "AI"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _dpapi_unprotect(ciphertext: bytes, *, entropy: bytes | None = None) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    source_buffer = ctypes.create_string_buffer(ciphertext)
    source = Blob(len(ciphertext), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    entropy_buffer = ctypes.create_string_buffer(entropy) if entropy is not None else None
    entropy_blob = Blob(len(entropy), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_byte))) if entropy_buffer else None
    target = Blob()
    entropy_pointer = ctypes.byref(entropy_blob) if entropy_blob is not None else None
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, entropy_pointer, None, None, 0, ctypes.byref(target)):
        raise AIConfigurationError("AI API key cannot be decrypted")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def _dpapi_protect(plaintext: bytes, *, entropy: bytes | None = None) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    source_buffer = ctypes.create_string_buffer(plaintext)
    source = Blob(len(plaintext), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    entropy_buffer = ctypes.create_string_buffer(entropy) if entropy is not None else None
    entropy_blob = Blob(len(entropy), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_byte))) if entropy_buffer else None
    target = Blob()
    entropy_pointer = ctypes.byref(entropy_blob) if entropy_blob is not None else None
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), None, entropy_pointer, None, None, 0, ctypes.byref(target)):
        raise AIConfigurationError("AI API key cannot be encrypted")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)
