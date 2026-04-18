from __future__ import annotations

import json
import logging
import os
import base64
import ctypes
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from sys import platform
from typing import Any

from PySide6.QtCore import QObject, Property, QStandardPaths, Signal, Slot
from PySide6.QtGui import QGuiApplication

try:
    from ldap3 import ALL, NTLM, Connection, Server
    from ldap3.core.exceptions import LDAPException
except ImportError:  # pragma: no cover - runtime dependency
    ALL = None
    NTLM = None
    Connection = None
    Server = None

    class LDAPException(Exception):
        pass


LDAP_HOST = os.getenv("AMLOGIC_LDAP_HOST", "ldap.amlogic.com")
LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "AMLOGIC")
AUTH_STATE_FILENAME = "auth_state.json"
AUTH_SECRET_FILENAME = "auth_secret.json"
_AUTH_SECRET_ENTROPY = b"SmartTest.Auth.SecretStore.v1"


class AuthBridge(QObject):
    authChanged = Signal()

    def __init__(self):
        super().__init__(QGuiApplication.instance())
        self._username = ""
        self._authenticated = False
        self._password = ""
        self._load_auth_state()

    def _auth_state_path(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / AUTH_STATE_FILENAME

    def _auth_secret_path(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / AUTH_SECRET_FILENAME

    def _normalize_username(self, username: str) -> str:
        clean_username = (username or "").strip()
        if "\\" in clean_username or "@" in clean_username:
            return clean_username
        return f"{LDAP_DOMAIN}\\{clean_username}"

    def _load_auth_state(self) -> None:
        path = self._auth_state_path()
        if not path.exists():
            self._username = ""
            self._authenticated = False
            self._password = ""
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to read auth state file %s: %s", path, exc)
            self._username = ""
            self._authenticated = False
            self._password = ""
            return

        username = str(data.get("username", "") or "").strip()
        authenticated = bool(data.get("authenticated", False))
        stored_password = self._load_password_secret() if authenticated else ""
        self._username = username if authenticated and stored_password else ""
        self._authenticated = authenticated and bool(username) and bool(stored_password)
        self._password = stored_password if self._authenticated else ""

    def _save_auth_state(self) -> None:
        path = self._auth_state_path()
        data = {
            "username": self._username,
            "authenticated": self._authenticated,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to write auth state file %s: %s", path, exc)

    def _clear_auth_state(self) -> None:
        path = self._auth_state_path()
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to clear auth state file %s: %s", path, exc)

    def _load_password_secret(self) -> str:
        path = self._auth_secret_path()
        if not path.exists():
            return ""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            encrypted_value = str(payload.get("encrypted_password", "") or "").strip()
            if not encrypted_value:
                return ""
            protected_bytes = base64.b64decode(encrypted_value.encode("ascii"))
            return _dpapi_unprotect(protected_bytes).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to load auth secret file %s: %s", path, exc)
            return ""

    def _save_password_secret(self, password: str) -> None:
        path = self._auth_secret_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            protected_bytes = _dpapi_protect(password.encode("utf-8"))
            payload = {
                "encrypted_password": base64.b64encode(protected_bytes).decode("ascii"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to save auth secret file %s: %s", path, exc)

    def _clear_password_secret(self) -> None:
        path = self._auth_secret_path()
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to clear auth secret file %s: %s", path, exc)

    def _set_auth_state(self, *, username: str, authenticated: bool, password: str = "") -> None:
        next_username = (username or "").strip() if authenticated else ""
        next_password = password if authenticated else ""
        changed = self._username != next_username or self._authenticated != authenticated
        self._username = next_username
        self._password = next_password if authenticated else ""
        self._authenticated = authenticated and bool(next_username)
        if self._authenticated:
            self._save_auth_state()
            if next_password:
                self._save_password_secret(next_password)
        else:
            self._clear_auth_state()
            self._clear_password_secret()
        if changed:
            self.authChanged.emit()

    def _ldap_authenticate(self, username: str, password: str) -> dict[str, Any]:
        clean_username = (username or "").strip()
        clean_password = password or ""
        if not clean_username or not clean_password:
            logging.info("ldap_authenticate: username or password empty (username=%s)", clean_username)
            return {"success": False, "username": "", "detail": "username_or_password_empty"}
        if Connection is None or Server is None or NTLM is None or ALL is None:
            logging.error("ldap_authenticate: ldap3 dependency is not installed")
            return {"success": False, "username": "", "detail": "ldap3_not_installed"}

        server_host = LDAP_HOST.strip()
        connection: Connection | None = None
        domain_user = self._normalize_username(clean_username)
        try:
            server = Server(server_host, get_info=ALL)
            connection = Connection(
                server,
                user=domain_user,
                password=clean_password,
                authentication=NTLM,
            )
            if not connection.bind():
                result = connection.result or {}
                description = str(result.get("description", "") or "").strip()
                message = str(result.get("message", "") or "").strip()
                detail = " | ".join(part for part in [description, message] if part)
                logging.warning(
                    "ldap_authenticate: LDAP bind failed (username=%s, server=%s, result=%s)",
                    domain_user,
                    server_host,
                    connection.result,
                )
                return {"success": False, "username": "", "detail": detail or "ldap_bind_failed"}
            logging.info(
                "ldap_authenticate: LDAP bind success (username=%s, server=%s)",
                domain_user,
                server_host,
            )
            return {"success": True, "username": clean_username, "detail": ""}
        except LDAPException as exc:
            logging.exception(
                "ldap_authenticate: LDAP exception (username=%s, server=%s): %s",
                clean_username,
                server_host,
                exc,
            )
            return {"success": False, "username": "", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logging.exception(
                "ldap_authenticate: unexpected exception (username=%s, server=%s): %s",
                clean_username,
                server_host,
                exc,
            )
            return {"success": False, "username": "", "detail": str(exc)}
        finally:
            if connection is not None:
                try:
                    connection.unbind()
                except Exception:  # noqa: BLE001
                    logging.debug("ldap_authenticate: ignored unbind exception", exc_info=True)

    @Slot(result=bool)
    def isAuthenticated(self) -> bool:
        return self._authenticated

    def _get_authenticated(self) -> bool:
        return self._authenticated

    @Slot(result=str)
    def currentUsername(self) -> str:
        return self._username

    def _get_username(self) -> str:
        return self._username

    def currentPassword(self) -> str:
        return self._password

    @Slot(result=bool)
    def hasCredential(self) -> bool:
        return bool(self._password)

    @Slot(result=str)
    def ldapServer(self) -> str:
        return LDAP_HOST

    @Slot(str, str, result="QVariantMap")
    def login(self, username: str, password: str) -> dict[str, Any]:
        clean_username = (username or "").strip()
        clean_password = password or ""
        if not clean_username or not clean_password:
            return {
                "success": False,
                "message": self.tr("Account or password cannot be empty."),
                "username": "",
                "detail": "account_or_password_empty",
            }
        if Connection is None:
            return {
                "success": False,
                "message": self.tr("ldap3 is not installed in the current Python environment."),
                "username": "",
                "detail": "ldap3_not_installed",
            }

        auth_result = self._ldap_authenticate(clean_username, clean_password)
        if not auth_result["success"]:
            detail = str(auth_result.get("detail", "") or "").strip()
            return {
                "success": False,
                "message": (
                    self.tr("LDAP sign-in failed. {detail}").format(detail=detail)
                    if detail
                    else self.tr("LDAP sign-in failed. Please check your account or password.")
                ),
                "username": "",
                "detail": detail,
            }

        validated_username = str(auth_result.get("username", "") or "").strip()
        self._set_auth_state(username=validated_username, authenticated=True, password=clean_password)
        return {
            "success": True,
            "message": self.tr("Sign-in successful. Welcome, {username}").format(username=validated_username),
            "username": validated_username,
            "detail": "",
        }

    @Slot()
    def logout(self) -> None:
        self._set_auth_state(username="", authenticated=False)

    authenticated = Property(bool, _get_authenticated, notify=authChanged)
    username = Property(str, _get_username, notify=authChanged)


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_protect(data: bytes) -> bytes:
    if platform != "win32":
        raise RuntimeError("Auth secret store requires Windows DPAPI")

    in_blob = _blob_from_bytes(data)
    entropy_blob = _blob_from_bytes(_AUTH_SECRET_ENTROPY)
    out_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "SmartTest Auth Password",
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
        raise RuntimeError("Auth secret store requires Windows DPAPI")

    in_blob = _blob_from_bytes(data)
    entropy_blob = _blob_from_bytes(_AUTH_SECRET_ENTROPY)
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
