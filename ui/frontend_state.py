from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings

from support.logging import smart_log
from ui.jsonTool import read_json, write_json


_VERSION = 1
_VALUE_TYPES = {"string", "bool", "int", "float", "object"}
_SENSITIVE_PARTS = {
    "api_key", "apikey", "credential", "ldap", "password",
    "passwd", "secret", "token",
}
_LEGACY_GLOBAL = (
    ("darkMode", "darkMode", "int"),
    ("useSystemAppBar", "useSystemAppBar", "bool"),
    ("language", "language", "string"),
)
_LEGACY_WINDOW = (
    ("tourShown", "tourShown", "bool"),
    ("rememberCloseAction", "rememberCloseAction", "bool"),
    ("closeAction", "closeAction", "string"),
)
_LEGACY_JIRA = (
    ("projects", "projects", "csv"),
    ("statuses", "statuses", "csv"),
    ("priorities", "priorities", "csv"),
    ("issue_types", "issueTypes", "csv"),
    ("assignees", "assignees", "csv"),
    ("reporters", "reporters", "csv"),
    ("labels", "labels", "csv"),
    ("board_index", "boardIndex", "int"),
    ("timeframe_index", "timeframeIndex", "int"),
    ("raw_jql", "rawJql", "string"),
    ("keyword", "keyword", "string"),
)


class FrontendStateStore:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._data = self._read()

    def load(
        self,
        user: str,
        scope: str,
        key: str,
        value_type: str,
        default: Any,
    ) -> Any:
        entry = (
            self._data.get("users", {})
            .get(str(user), {})
            .get(str(scope), {})
            .get(str(key))
        )
        if (
            not isinstance(entry, dict)
            or entry.get("type") != value_type
            or not _matches_type(value_type, entry.get("value"))
        ):
            return default
        value = entry["value"]
        return deepcopy(value) if value_type == "object" else value

    def save(
        self,
        user: str,
        scope: str,
        key: str,
        value_type: str,
        value: Any,
        *,
        sensitive: bool = False,
    ) -> None:
        if sensitive or _sensitive_name(scope, key, value_type) or (
            value_type == "object" and _contains_sensitive_key(value)
        ):
            raise ValueError("Sensitive frontend state cannot be persisted.")
        if value_type not in _VALUE_TYPES or not _matches_type(value_type, value):
            raise ValueError("Frontend state value does not match its declared type.")

        updated = deepcopy(self._data)
        _scope(updated, str(user), str(scope))[str(key)] = {
            "type": value_type,
            "value": value,
        }
        self._write(updated)

    def migrate_legacy_ini(self, path: Path, user: str) -> None:
        path = Path(path)
        if not path.exists():
            return
        settings = QSettings(str(path), QSettings.Format.IniFormat)
        updated = deepcopy(self._data)
        migration = updated.setdefault("migrations", {}).setdefault(
            "example_ini_v1", {}
        )
        changed = False

        if not migration.get("global"):
            values = _legacy_values(settings, _LEGACY_GLOBAL)
            target = _scope(updated, "global", "global")
            imported = False
            for key, (value_type, value) in values.items():
                if key not in target:
                    target[key] = {"type": value_type, "value": value}
                    imported = True
            window_values = {
                key: value
                for key, (_value_type, value) in _legacy_values(
                    settings, _LEGACY_WINDOW
                ).items()
            }
            if window_values and "windowState" not in target:
                target["windowState"] = {
                    "type": "object",
                    "value": window_values,
                }
                imported = True
            if imported:
                migration["global"] = True
                changed = True

        account = normalize_frontend_user(user)
        if account != "anonymous" and not migration.get("jiraUser"):
            target = _scope(updated, account, "jira")
            if "filterState" not in target:
                values = {
                    key: value
                    for key, (_value_type, value) in _legacy_values(
                        settings, _LEGACY_JIRA, prefix="jira/"
                    ).items()
                }
                if values:
                    target["filterState"] = {"type": "object", "value": values}
                    migration["jiraUser"] = account
                    changed = True

        if changed:
            self._write(updated)

    def _read(self) -> dict[str, Any]:
        try:
            payload = read_json(self._path, {})
        except (OSError, ValueError):
            _log("Frontend state is invalid; defaults will be used.", "warning")
            return _empty_state()
        if not payload:
            return _empty_state()
        if (
            not isinstance(payload, dict)
            or payload.get("version") != _VERSION
            or not isinstance(payload.get("users"), dict)
        ):
            _log("Frontend state version is incompatible; defaults will be used.", "warning")
            return _empty_state()
        return _sanitize_state(payload)

    def _write(self, updated: dict[str, Any]) -> None:
        try:
            write_json(self._path, updated)
        except OSError:
            _log("Frontend state could not be written.", "error")
        else:
            self._data = updated


def normalize_frontend_user(value: str) -> str:
    account = str(value or "").strip().casefold().rsplit("\\", 1)[-1]
    return account.split("@", 1)[0].strip() or "anonymous"


def _empty_state() -> dict[str, Any]:
    return {"version": _VERSION, "users": {}}


def _scope(state: dict[str, Any], user: str, scope: str) -> dict[str, Any]:
    return state.setdefault("users", {}).setdefault(user, {}).setdefault(scope, {})


def _sanitize_state(payload: dict[str, Any]) -> dict[str, Any]:
    state = _empty_state()
    for user, scopes in payload["users"].items():
        if not isinstance(user, str) or not isinstance(scopes, dict):
            continue
        for scope, entries in scopes.items():
            if not isinstance(scope, str) or not isinstance(entries, dict):
                continue
            for key, entry in entries.items():
                if not isinstance(key, str) or not isinstance(entry, dict):
                    continue
                entry_type = entry.get("type")
                if (
                    not isinstance(entry_type, str)
                    or entry_type not in _VALUE_TYPES
                    or not _matches_type(entry_type, entry.get("value"))
                ):
                    continue
                _scope(state, user, scope)[key] = deepcopy(entry)
    migrations = payload.get("migrations")
    if isinstance(migrations, dict):
        state["migrations"] = {
            name: deepcopy(marker)
            for name, marker in migrations.items()
            if (
                isinstance(name, str)
                and name != "example_ini_v1"
                and isinstance(marker, dict)
            )
        }
        legacy = migrations.get("example_ini_v1")
        if isinstance(legacy, dict):
            state["migrations"]["example_ini_v1"] = {}
            if legacy.get("global") is True:
                state["migrations"]["example_ini_v1"]["global"] = True
            if isinstance(legacy.get("jiraUser"), str):
                state["migrations"]["example_ini_v1"]["jiraUser"] = legacy[
                    "jiraUser"
                ]
    return state


def _legacy_values(settings, mappings, *, prefix=""):
    values = {}
    for source, target, value_type in mappings:
        source = prefix + source
        if not settings.contains(source):
            continue
        value = _legacy_value(settings.value(source), value_type)
        if value_type == "csv" or _matches_type(value_type, value):
            values[target] = (value_type, value)
    return values


def _legacy_value(value: Any, value_type: str) -> Any:
    if value_type == "csv":
        return [item.strip() for item in str(value).split(",") if item.strip()]
    if value_type == "string":
        return str(value)
    if value_type == "bool":
        return value if type(value) is bool else str(value).casefold() == "true"
    if value_type == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return value


def _matches_type(value_type: str, value: Any) -> bool:
    if value_type == "string":
        return isinstance(value, str)
    if value_type == "bool":
        return type(value) is bool
    if value_type == "int":
        return type(value) is int
    if value_type == "float":
        return type(value) in {int, float}
    return value_type == "object" and isinstance(value, dict) and _json_value(value)


def _json_value(value: Any) -> bool:
    if value is None or type(value) in {str, bool, int, float}:
        return True
    if isinstance(value, list):
        return all(_json_value(item) for item in value)
    return isinstance(value, dict) and all(
        isinstance(key, str) and _json_value(item)
        for key, item in value.items()
    )


def _sensitive_name(*parts: str) -> bool:
    name = "_".join(map(str, parts)).casefold().replace("-", "_").replace(" ", "_")
    return any(part in name for part in _SENSITIVE_PARTS)


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _sensitive_name(key) or _contains_sensitive_key(child)
            for key, child in value.items()
        )
    return isinstance(value, list) and any(_contains_sensitive_key(item) for item in value)


def _log(message: str, level: str) -> None:
    try:
        smart_log(message, level=level, domain="ui", source="FrontendStateStore")
    except OSError:
        pass
