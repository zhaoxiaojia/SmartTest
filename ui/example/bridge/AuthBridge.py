from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
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


class AuthBridge(QObject):
    authChanged = Signal()

    def __init__(self):
        super().__init__(QGuiApplication.instance())
        self._username = ""
        self._authenticated = False
        self._load_auth_state()

    def _auth_state_path(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / AUTH_STATE_FILENAME

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
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to read auth state file %s: %s", path, exc)
            self._username = ""
            self._authenticated = False
            return

        username = str(data.get("username", "") or "").strip()
        authenticated = bool(data.get("authenticated", False))
        self._username = username if authenticated else ""
        self._authenticated = authenticated and bool(username)

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

    def _set_auth_state(self, *, username: str, authenticated: bool) -> None:
        next_username = (username or "").strip() if authenticated else ""
        changed = self._username != next_username or self._authenticated != authenticated
        self._username = next_username
        self._authenticated = authenticated and bool(next_username)
        if self._authenticated:
            self._save_auth_state()
        else:
            self._clear_auth_state()
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
                "message": "Account or password cannot be empty.",
                "username": "",
                "detail": "account_or_password_empty",
            }
        if Connection is None:
            return {
                "success": False,
                "message": "ldap3 is not installed in the current Python environment.",
                "username": "",
                "detail": "ldap3_not_installed",
            }

        auth_result = self._ldap_authenticate(clean_username, clean_password)
        if not auth_result["success"]:
            detail = str(auth_result.get("detail", "") or "").strip()
            return {
                "success": False,
                "message": f"LDAP sign-in failed. {detail}" if detail else "LDAP sign-in failed. Please check your account or password.",
                "username": "",
                "detail": detail,
            }

        validated_username = str(auth_result.get("username", "") or "").strip()
        self._set_auth_state(username=validated_username, authenticated=True)
        return {
            "success": True,
            "message": f"Sign-in successful. Welcome, {validated_username}",
            "username": validated_username,
            "detail": "",
        }

    @Slot()
    def logout(self) -> None:
        self._set_auth_state(username="", authenticated=False)

    authenticated = Property(bool, _get_authenticated, notify=authChanged)
    username = Property(str, _get_username, notify=authChanged)
