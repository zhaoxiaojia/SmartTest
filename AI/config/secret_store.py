from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from sys import platform

from AI.core.errors import AIConfigurationError

_DPAPI_ENTROPY = b"SmartTest.AI.SecretStore.v1"


class AISecretStore:
    def __init__(self, store_path: str | Path | None = None):
        self._store_path = Path(store_path) if store_path is not None else default_secret_store_path()
        self._store_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def store_path(self) -> Path:
        return self._store_path

    def read_api_key(self) -> str | None:
        payload = self._read_payload()
        encrypted_value = str(payload.get("encrypted_api_key", "")).strip()
        if not encrypted_value:
            return None
        protected_bytes = base64.b64decode(encrypted_value.encode("ascii"))
        decrypted = _dpapi_unprotect(protected_bytes)
        return decrypted.decode("utf-8")

    def write_api_key(self, api_key: str) -> None:
        normalized_key = api_key.strip()
        if not normalized_key:
            raise AIConfigurationError("AI API key cannot be empty")
        protected_bytes = _dpapi_protect(normalized_key.encode("utf-8"))
        payload = {
            "encrypted_api_key": base64.b64encode(protected_bytes).decode("ascii"),
        }
        self._store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_payload(self) -> dict[str, str]:
        if not self._store_path.exists():
            return {}
        text = self._store_path.read_text(encoding="utf-8").strip()
        if text == "":
            return {}
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise AIConfigurationError(f"Invalid AI secret store payload: {self._store_path}")
        return payload


def default_secret_store_path() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA", "").strip()
    if not local_appdata:
        local_appdata = str(Path.home() / "AppData" / "Local")
    return Path(local_appdata) / "SmartTest" / "AI" / "secret_store.json"


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_protect(data: bytes) -> bytes:
    if platform != "win32":
        raise AIConfigurationError("AI secret store currently requires Windows DPAPI")

    in_blob = _blob_from_bytes(data)
    entropy_blob = _blob_from_bytes(_DPAPI_ENTROPY)
    out_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "SmartTest AI Key",
        ctypes.byref(entropy_blob),
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        return _bytes_from_blob(out_blob)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    if platform != "win32":
        raise AIConfigurationError("AI secret store currently requires Windows DPAPI")

    in_blob = _blob_from_bytes(data)
    entropy_blob = _blob_from_bytes(_DPAPI_ENTROPY)
    out_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        return _bytes_from_blob(out_blob)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _blob_from_bytes(data: bytes) -> _DataBlob:
    if not data:
        return _DataBlob(0, None)
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))


def _bytes_from_blob(blob: _DataBlob) -> bytes:
    if not blob.pbData or blob.cbData == 0:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)
