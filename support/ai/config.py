from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path

from .core import AIClientConfig, AIConfigurationError

DEFAULT_AI_BASE_URL = "https://llm.amlogic.com/8d1b5b4c"
DEFAULT_AI_MODEL = "Amlogic_Local/Kimi-K2.7-Code"
DEFAULT_AI_TIMEOUT = 120.0
DEFAULT_AI_MAX_TOKENS = 2048
LEGACY_DPAPI_ENTROPY = b"SmartTest.AI.SecretStore.v1"


class AIKeyResolver:
    def __init__(self, store_path: Path | None = None):
        self._store_path = store_path

    def resolve(self) -> str:
        key = str(os.getenv("SMARTTEST_AI_API_KEY") or "").strip()
        if key: return key
        if os.name != "nt": raise AIConfigurationError("AI API key is unavailable")
        path = self._store_path or _default_store_path()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("api_key_dpapi"):
                encrypted = base64.b64decode(str(payload["api_key_dpapi"]), validate=True)
                key = _dpapi_unprotect(encrypted).decode("utf-8").strip()
            elif payload.get("encrypted_api_key"):
                encrypted = base64.b64decode(str(payload["encrypted_api_key"]), validate=True)
                key = _dpapi_unprotect(encrypted, entropy=LEGACY_DPAPI_ENTROPY).decode("utf-8").strip()
                if key:
                    self.store(key)
            else:
                raise AIConfigurationError("AI API key is unavailable")
        except Exception as exc:
            raise AIConfigurationError("AI API key is unavailable") from exc
        if not key: raise AIConfigurationError("AI API key is unavailable")
        return key

    def store(self, key: str) -> Path:
        if os.name != "nt" or not str(key or "").strip():
            raise AIConfigurationError("AI API key cannot be stored")
        path = self._store_path or _default_store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"api_key_dpapi": base64.b64encode(_dpapi_protect(str(key).encode("utf-8"))).decode("ascii")}, indent=2)
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        return path


def _default_store_path() -> Path:
    base = os.getenv("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Local"
    return root / "Amlogic" / "SmartTest" / "AI" / "secret_store.json"


def load_ai_client_config(key_resolver: AIKeyResolver | None = None) -> AIClientConfig:
    resolver = key_resolver or AIKeyResolver()
    try:
        timeout = float(os.getenv("SMARTTEST_AI_TIMEOUT", str(DEFAULT_AI_TIMEOUT)))
        max_tokens = int(
            os.getenv("SMARTTEST_AI_MAX_TOKENS", str(DEFAULT_AI_MAX_TOKENS))
        )
    except ValueError as exc:
        raise AIConfigurationError("AI runtime limits are invalid") from exc
    base_url = str(os.getenv("SMARTTEST_AI_BASE_URL") or DEFAULT_AI_BASE_URL).strip().rstrip("/")
    model = str(os.getenv("SMARTTEST_AI_MODEL") or DEFAULT_AI_MODEL).strip()
    if not base_url or not model or timeout <= 0 or max_tokens <= 0:
        raise AIConfigurationError("AI runtime configuration is invalid")
    return AIClientConfig(
        base_url=base_url,
        model=model,
        api_key=resolver.resolve(),
        timeout=timeout,
        max_tokens=max_tokens,
    )


def _dpapi_unprotect(ciphertext: bytes, *, entropy: bytes | None = None) -> bytes:
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure): _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    source_buffer = ctypes.create_string_buffer(ciphertext)
    source = Blob(len(ciphertext), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    entropy_buffer = ctypes.create_string_buffer(entropy) if entropy is not None else None
    entropy_blob = Blob(len(entropy), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_byte))) if entropy is not None else None
    target = Blob()
    entropy_pointer = ctypes.byref(entropy_blob) if entropy_blob is not None else None
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, entropy_pointer, None, None, 0, ctypes.byref(target)):
        raise AIConfigurationError("AI API key cannot be decrypted")
    try: return ctypes.string_at(target.pbData, target.cbData)
    finally: ctypes.windll.kernel32.LocalFree(target.pbData)


def _dpapi_protect(plaintext: bytes, *, entropy: bytes | None = None) -> bytes:
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure): _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    source_buffer = ctypes.create_string_buffer(plaintext)
    source = Blob(len(plaintext), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    entropy_buffer = ctypes.create_string_buffer(entropy) if entropy is not None else None
    entropy_blob = Blob(len(entropy), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_byte))) if entropy is not None else None
    entropy_pointer = ctypes.byref(entropy_blob) if entropy_blob is not None else None
    target = Blob()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), None, entropy_pointer, None, None, 0, ctypes.byref(target)):
        raise AIConfigurationError("AI API key cannot be encrypted")
    try: return ctypes.string_at(target.pbData, target.cbData)
    finally: ctypes.windll.kernel32.LocalFree(target.pbData)
