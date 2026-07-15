from __future__ import annotations

import os
import base64
import ctypes
import hashlib
import json
import math
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from sys import platform
from typing import Any

from PySide6.QtCore import QObject, Property, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImageReader

from ui import jsonTool
from support.logging import smart_log

try:
    from example.helper.AppPaths import app_data_dir
except ImportError:  # pragma: no cover - direct unit-test imports may use the ui.example package path
    from ui.example.helper.AppPaths import app_data_dir

try:
    from ldap3 import ALL, NTLM, SUBTREE, Connection, Server
    from ldap3.core.exceptions import LDAPException
except ImportError:  # pragma: no cover - runtime dependency
    ALL = None
    NTLM = None
    SUBTREE = None
    Connection = None
    Server = None

    class LDAPException(Exception):
        pass


LDAP_HOST = os.getenv("AMLOGIC_LDAP_HOST", "ldap.amlogic.com")
LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "AMLOGIC")
AUTH_STATE_FILENAME = "auth_state.json"
AUTH_SECRET_FILENAME = "auth_secret.json"
_AUTH_SECRET_ENTROPY = b"SmartTest.Auth.SecretStore.v1"


def load_personnel(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    return payload if isinstance(payload, dict) else {}


def initials_from_name(display_name: str) -> str:
    words = str(display_name or "").split()
    return "".join(word[0].upper() for word in words[:2] if word)


def match_employee_profile(
    personnel: dict[str, Any], ldap_display_name: str, *, username: str = ""
) -> dict[str, Any]:
    display_name = str(ldap_display_name or "").strip()
    employees = [item for item in personnel.get("employees", []) if isinstance(item, dict)]
    employee = next(
        (item for item in employees if str(item.get("display_name", "")).strip() == display_name),
        None,
    ) if display_name else None
    if employee is None and username:
        account_matches = [
            item
            for item in employees
            if str(item.get("account", "") or "") == username
        ]
        employee = account_matches[0] if len(account_matches) == 1 else None
    if employee is None:
        return {}
    employment = employee.get("employment", {}) or {}
    organization = employee.get("organization", {}) or {}
    grade = str(employment.get("grade", "") or "")
    career_level = next(
        (
            item
            for item in personnel.get("career_levels", [])
            if isinstance(item, dict) and str(item.get("grade", "") or "") == grade
        ),
        {},
    )
    product_names = {
        str(item.get("id", "") or ""): str(item.get("name", "") or "")
        for item in personnel.get("product_lines", [])
        if isinstance(item, dict)
    }
    assignments = employee.get("assignments", []) or []
    return {
        "display_name": str(employee.get("display_name", "") or ""),
        "grade": grade,
        "job_title": str(
            employment.get("job_title_override", "") or career_level.get("job_title", "") or ""
        ),
        "department": str(organization.get("department", "") or ""),
        "team": str(organization.get("team", "") or ""),
        "division": str(organization.get("division", "") or ""),
        "employee_type": str(employment.get("employee_type", "") or ""),
        "product_lines": [
            product_names.get(str(item.get("product_line_id", "") or ""), "")
            for item in assignments
            if isinstance(item, dict) and product_names.get(str(item.get("product_line_id", "") or ""), "")
        ],
        "roles": [str(role) for role in employee.get("system_roles", []) or []],
        "reports_to": str(employee.get("reports_to", "") or ""),
    }


def ldap_identity_from_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    display_name = str(attributes.get("displayName", "") or "").strip()
    avatar_bytes = b""
    for key in ("thumbnailPhoto", "jpegPhoto"):
        value = attributes.get(key)
        if isinstance(value, bytes):
            avatar_bytes = value
            break
        if isinstance(value, list) and value and isinstance(value[0], bytes):
            avatar_bytes = value[0]
            break
    return {"display_name": display_name, "avatar_bytes": avatar_bytes}


class AuthBridge(QObject):
    authChanged = Signal()

    def __init__(self, project_root: Path | None = None, state_root: Path | None = None):
        super().__init__(QGuiApplication.instance())
        self._project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[3]
        self._state_root = Path(state_root) if state_root else app_data_dir()
        self._personnel = load_personnel(self._project_root / "config" / "personnel.json")
        self._username = ""
        self._authenticated = False
        self._password = ""
        self._display_name = ""
        self._profile: dict[str, Any] = {}
        self._avatar_url = ""
        self._load_auth_state()
        self._resolve_profile()
        self._avatar_url = self._avatar_url_for_username(self._username)

    def _auth_state_path(self) -> Path:
        return self._state_root / AUTH_STATE_FILENAME

    def _auth_secret_path(self) -> Path:
        return self._state_root / AUTH_SECRET_FILENAME

    def _avatar_dir(self) -> Path:
        return self._state_root / "avatars"

    def _uploaded_avatar_dir(self) -> Path:
        return self._project_root / "config" / "avatars"

    def _avatar_identity(self) -> str:
        return self._username or self._display_name

    def _uploaded_avatar_path(self) -> Path | None:
        identity = self._avatar_identity()
        if not identity:
            return None
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        avatar_dir = self._uploaded_avatar_dir()
        for suffix in (".png", ".jpg", ".jpeg"):
            candidate = avatar_dir / f"{digest}{suffix}"
            if candidate.is_file():
                return candidate
        return None

    def _effective_avatar_url(self) -> str:
        uploaded = self._uploaded_avatar_path()
        if uploaded is not None:
            return uploaded.as_uri()
        return self._avatar_url_for_username(self._username)

    def _resolve_profile(self) -> None:
        self._profile = match_employee_profile(
            self._personnel,
            self._display_name,
            username=self._username,
        )
        if self._profile:
            self._display_name = self._profile["display_name"]

    def _apply_authenticated_identity(self, username: str, display_name: str) -> None:
        self._username = str(username or "").strip()
        self._display_name = str(display_name or "").strip() or self._username
        self._authenticated = bool(self._username)
        self._resolve_profile()
        if self._profile:
            self._display_name = self._profile["display_name"]
        self._avatar_url = self._effective_avatar_url()

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
            self._display_name = ""
            self._avatar_url = ""
            return

        try:
            data = jsonTool.read_json(path, {})
        except Exception as exc:  # noqa: BLE001
            smart_log("Failed to read auth state file %s: %s", path, exc, level="warning")
            self._username = ""
            self._authenticated = False
            self._password = ""
            self._display_name = ""
            self._avatar_url = ""
            return

        username = str(data.get("username", "") or "").strip()
        authenticated = bool(data.get("authenticated", False))
        display_name = str(data.get("display_name", "") or "").strip()
        stored_password = self._load_password_secret() if authenticated else ""
        self._username = username if authenticated and stored_password else ""
        self._authenticated = authenticated and bool(username) and bool(stored_password)
        self._password = stored_password if self._authenticated else ""
        self._display_name = display_name if self._authenticated else ""
        self._avatar_url = self._avatar_url_for_username(self._username)

    def _save_auth_state(self) -> None:
        path = self._auth_state_path()
        data = {
            "username": self._username,
            "authenticated": self._authenticated,
            "display_name": self._display_name,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            jsonTool.write_json(path, data)
        except Exception as exc:  # noqa: BLE001
            smart_log("Failed to write auth state file %s: %s", path, exc, level="warning")

    def _clear_auth_state(self) -> None:
        path = self._auth_state_path()
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:  # noqa: BLE001
            smart_log("Failed to clear auth state file %s: %s", path, exc, level="warning")

    def _load_password_secret(self) -> str:
        path = self._auth_secret_path()
        if not path.exists():
            return ""
        try:
            payload = jsonTool.read_json(path, {})
            encrypted_value = str(payload.get("encrypted_password", "") or "").strip()
            if not encrypted_value:
                return ""
            protected_bytes = base64.b64decode(encrypted_value.encode("ascii"))
            return _dpapi_unprotect(protected_bytes).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            smart_log("Failed to load auth secret file %s: %s", path, exc, level="warning")
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
            jsonTool.write_json(path, payload)
        except Exception as exc:  # noqa: BLE001
            smart_log("Failed to save auth secret file %s: %s", path, exc, level="warning")

    def _clear_password_secret(self) -> None:
        path = self._auth_secret_path()
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:  # noqa: BLE001
            smart_log("Failed to clear auth secret file %s: %s", path, exc, level="warning")

    def _avatar_path_for_username(self, username: str) -> Path:
        digest = hashlib.sha256(username.strip().lower().encode("utf-8")).hexdigest()[:24]
        return self._avatar_dir() / f"{digest}.jpg"

    def _avatar_url_for_username(self, username: str) -> str:
        clean_username = (username or "").strip()
        if not clean_username:
            return ""
        path = self._avatar_path_for_username(clean_username)
        return path.as_uri() if path.exists() else ""

    def _set_avatar_bytes(self, username: str, avatar_bytes: bytes) -> str:
        if not username or not avatar_bytes:
            return ""
        path = self._avatar_path_for_username(username)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(avatar_bytes)
            return path.as_uri()
        except Exception as exc:  # noqa: BLE001
            smart_log("Failed to cache LDAP avatar %s: %s", path, exc, level="warning")
            return ""

    def _fetch_ldap_identity(self, connection: Connection, username: str) -> dict[str, Any]:
        if SUBTREE is None:
            return {"display_name": "", "avatar_bytes": b""}
        try:
            naming_contexts = list((connection.server.info.other or {}).get("defaultNamingContext") or [])
            search_base = str(naming_contexts[0]) if naming_contexts else ""
            if not search_base:
                return {"display_name": "", "avatar_bytes": b""}
            account_name = username.split("\\")[-1].split("@")[0].strip()
            escaped_account = _escape_ldap_filter_value(account_name)
            escaped_username = _escape_ldap_filter_value(username)
            search_filter = (
                f"(|(sAMAccountName={escaped_account})(userPrincipalName={escaped_username})(mail={escaped_username}))"
            )
            if not connection.search(
                search_base=search_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=["displayName", "thumbnailPhoto", "jpegPhoto"],
                size_limit=1,
            ):
                return {"display_name": "", "avatar_bytes": b""}
            if not connection.entries:
                return {"display_name": "", "avatar_bytes": b""}
            entry = connection.entries[0]
            attributes = {
                name: entry[name].value if name in entry else None
                for name in ("displayName", "thumbnailPhoto", "jpegPhoto")
            }
            return ldap_identity_from_attributes(attributes)
        except Exception as exc:  # noqa: BLE001
            smart_log("LDAP avatar lookup failed for %s: %s", username, exc, level="info")
            return {"display_name": "", "avatar_bytes": b""}

    def _set_auth_state(
        self, *, username: str, authenticated: bool, password: str = "", display_name: str = ""
    ) -> None:
        next_username = (username or "").strip() if authenticated else ""
        next_password = password if authenticated else ""
        next_display_name = (display_name or "").strip() if authenticated else ""
        changed = (
            self._username != next_username
            or self._authenticated != authenticated
            or self._display_name != next_display_name
        )
        self._username = next_username
        self._password = next_password if authenticated else ""
        self._authenticated = authenticated and bool(next_username)
        self._display_name = next_display_name or next_username
        self._resolve_profile()
        if self._profile:
            self._display_name = self._profile["display_name"]
        self._avatar_url = self._avatar_url_for_username(next_username) if self._authenticated else ""
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
            smart_log("ldap_authenticate: username or password empty (username=%s)", clean_username, level="info")
            return {"success": False, "username": "", "detail": "username_or_password_empty"}
        if Connection is None or Server is None or NTLM is None or ALL is None:
            smart_log("ldap_authenticate: ldap3 dependency is not installed", level="error")
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
                smart_log(
                    "ldap_authenticate: LDAP bind failed (username=%s, server=%s, result=%s)",
                    domain_user,
                    server_host,
                    connection.result,
                    level="warning",
                )
                return {"success": False, "username": "", "detail": detail or "ldap_bind_failed"}
            smart_log(
                "ldap_authenticate: LDAP bind success (username=%s, server=%s)",
                domain_user,
                server_host,
                level="info",
            )
            identity = self._fetch_ldap_identity(connection, clean_username)
            return {"success": True, "username": clean_username, "detail": "", **identity}
        except LDAPException as exc:
            smart_log(
                "ldap_authenticate: LDAP exception (username=%s, server=%s): %s",
                clean_username,
                server_host,
                exc,
                level="error",
                exc_info=True,
            )
            return {"success": False, "username": "", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            smart_log(
                "ldap_authenticate: unexpected exception (username=%s, server=%s): %s",
                clean_username,
                server_host,
                exc,
            level="error", exc_info=True)
            return {"success": False, "username": "", "detail": str(exc)}
        finally:
            if connection is not None:
                try:
                    connection.unbind()
                except Exception:  # noqa: BLE001
                    smart_log("ldap_authenticate: ignored unbind exception", exc_info=True, level="debug")

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

    def _get_avatar_url(self) -> str:
        return self._effective_avatar_url()

    @Slot(str, float, float, float, result="QVariantMap")
    def saveCroppedAvatar(
        self, source: str, horizontal_position: float, vertical_position: float, crop_scale: float
    ) -> dict[str, Any]:
        if not self._avatar_identity():
            return {"success": False, "error": "missing_identity", "path": ""}
        values = (horizontal_position, vertical_position, crop_scale)
        if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
            return {"success": False, "error": "invalid_crop", "path": ""}
        if float(crop_scale) <= 0:
            return {"success": False, "error": "invalid_crop", "path": ""}
        source_url = QUrl(str(source or ""))
        source_path = Path(source_url.toLocalFile() if source_url.isLocalFile() else str(source or ""))
        try:
            resolved_source = source_path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            return {"success": False, "error": "missing_file", "path": ""}
        if resolved_source.suffix.lower() not in {".png", ".jpg", ".jpeg"} or not resolved_source.is_file():
            return {"success": False, "error": "unsupported_image", "path": ""}
        reader = QImageReader(str(resolved_source))
        image = reader.read()
        if image.isNull():
            return {"success": False, "error": "invalid_image", "path": ""}
        position_x = min(max(float(horizontal_position), 0.0), 1.0)
        position_y = min(max(float(vertical_position), 0.0), 1.0)
        scale = min(max(float(crop_scale), 0.05), 1.0)
        side = max(1, round(min(image.width(), image.height()) * scale))
        left = round(position_x * max(0, image.width() - side))
        top = round(position_y * max(0, image.height() - side))
        cropped = image.copy(left, top, side, side).scaled(
            256,
            256,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )
        avatar_dir = self._uploaded_avatar_dir().resolve()
        avatar_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(self._avatar_identity().encode("utf-8")).hexdigest()[:24]
        destination = (avatar_dir / f"{digest}.png").resolve()
        temporary = destination.with_name(f".{destination.name}.tmp.png")
        try:
            if avatar_dir not in destination.parents or not cropped.save(str(temporary), "PNG"):
                return {"success": False, "error": "save_failed", "path": ""}
            temporary.replace(destination)
        except OSError as exc:
            smart_log("Failed to save cropped account avatar %s: %s", destination, exc, level="warning")
            return {"success": False, "error": "save_failed", "path": ""}
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        self._avatar_url = destination.as_uri()
        self.authChanged.emit()
        return {"success": True, "error": "", "path": str(destination)}

    def _get_display_name(self) -> str:
        return self._display_name or self._username

    def _get_initials(self) -> str:
        return initials_from_name(self._get_display_name())

    def _profile_value(self, key: str) -> str:
        return str(self._profile.get(key, "") or "")

    def _get_grade(self) -> str:
        return self._profile_value("grade")

    def _get_job_title(self) -> str:
        return self._profile_value("job_title")

    def _get_department(self) -> str:
        return self._profile_value("department")

    def _get_team(self) -> str:
        return self._profile_value("team")

    def _get_reports_to(self) -> str:
        return self._profile_value("reports_to")

    def _get_product_lines(self) -> list[str]:
        return list(self._profile.get("product_lines", []) or [])

    def _get_role_text(self) -> str:
        roles = self._profile.get("roles", []) or []
        return self._get_job_title() or (str(roles[0]) if roles else self._profile_value("employee_type"))

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
        ldap_display_name = str(auth_result.get("display_name", "") or "").strip()
        self._set_auth_state(
            username=validated_username,
            authenticated=True,
            password=clean_password,
            display_name=ldap_display_name,
        )
        avatar_bytes = auth_result.get("avatar_bytes", b"")
        if isinstance(avatar_bytes, bytes) and avatar_bytes:
            avatar_url = self._set_avatar_bytes(validated_username, avatar_bytes)
            if avatar_url:
                self._avatar_url = avatar_url
                self.authChanged.emit()
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
    avatarUrl = Property(str, _get_avatar_url, notify=authChanged)
    displayName = Property(str, _get_display_name, notify=authChanged)
    initials = Property(str, _get_initials, notify=authChanged)
    grade = Property(str, _get_grade, notify=authChanged)
    jobTitle = Property(str, _get_job_title, notify=authChanged)
    department = Property(str, _get_department, notify=authChanged)
    team = Property(str, _get_team, notify=authChanged)
    reportsTo = Property(str, _get_reports_to, notify=authChanged)
    productLines = Property("QVariantList", _get_product_lines, notify=authChanged)
    roleText = Property(str, _get_role_text, notify=authChanged)


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


def _escape_ldap_filter_value(value: str) -> str:
    return (
        value.replace("\\", r"\5c")
        .replace("*", r"\2a")
        .replace("(", r"\28")
        .replace(")", r"\29")
        .replace("\x00", r"\00")
    )
