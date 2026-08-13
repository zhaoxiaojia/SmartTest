from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FILENAME = "auth_accounts.json"
SCHEMA_VERSION = 1


def canonical_username(username: str) -> str:
    value = str(username or "").strip().casefold()
    if "\\" in value:
        value = value.rsplit("\\", 1)[-1]
    if "@" in value:
        value = value.split("@", 1)[0]
    return value


def account_id_for_username(username: str) -> str:
    return hashlib.sha256(canonical_username(username).encode("utf-8")).hexdigest()[:32]


class AuthAccountStore:
    def __init__(self, state_root: Path):
        self._path = Path(state_root) / FILENAME
        self._data = self._load()

    @property
    def last_account_id(self) -> str:
        return str(self._data.get("last_account_id", "") or "")

    @property
    def active_account_id(self) -> str:
        return str(self._data.get("active_account_id", "") or "")

    def set_active_account(self, account_id: str) -> bool:
        if not self.get(account_id):
            return False
        self._data["active_account_id"] = account_id
        self._save()
        return True

    def clear_active_account(self) -> None:
        if self.active_account_id:
            self._data["active_account_id"] = ""
            self._save()

    def accounts(self) -> list[dict[str, Any]]:
        return sorted(
            (dict(item) for item in self._data["accounts"]),
            key=lambda item: str(item.get("last_login_at", "")),
            reverse=True,
        )

    def get(self, account_id: str) -> dict[str, Any] | None:
        return next((dict(item) for item in self._data["accounts"] if item["account_id"] == account_id), None)

    def record_login(
        self,
        username: str,
        display_name: str,
        remember_password: bool,
        last_login_at: str | None = None,
        *,
        auto_login: bool = False,
    ) -> str:
        account_id = account_id_for_username(username)
        timestamp = last_login_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        item = self.get(account_id) or {"account_id": account_id}
        item.update({
            "username": str(username).strip(),
            "display_name": str(display_name or username).strip(),
            "remember_password": bool(remember_password),
            "auto_login": bool(auto_login and remember_password),
            "last_login_at": timestamp,
        })
        if item["auto_login"]:
            for entry in self._data["accounts"]:
                entry["auto_login"] = False
        self._data["accounts"] = [entry for entry in self._data["accounts"] if entry["account_id"] != account_id]
        self._data["accounts"].append(item)
        self._data["last_account_id"] = account_id
        self._save()
        return account_id

    def set_remember_password(self, account_id: str, enabled: bool) -> bool:
        for item in self._data["accounts"]:
            if item["account_id"] == account_id:
                item["remember_password"] = bool(enabled)
                if not enabled:
                    item["auto_login"] = False
                self._save()
                return True
        return False

    def set_auto_login(self, account_id: str, enabled: bool) -> bool:
        for item in self._data["accounts"]:
            if item["account_id"] == account_id:
                if enabled and item.get("remember_password"):
                    for entry in self._data["accounts"]:
                        entry["auto_login"] = False
                item["auto_login"] = bool(enabled and item.get("remember_password"))
                self._save()
                return True
        return False

    def remove(self, account_id: str) -> bool:
        before = len(self._data["accounts"])
        self._data["accounts"] = [item for item in self._data["accounts"] if item["account_id"] != account_id]
        if len(self._data["accounts"]) == before:
            return False
        if self.last_account_id == account_id:
            ordered = self.accounts()
            self._data["last_account_id"] = ordered[0]["account_id"] if ordered else ""
        if self.active_account_id == account_id:
            self._data["active_account_id"] = ""
        self._save()
        return True

    def pending_credential_cleanup(self) -> list[str]:
        return list(self._data.get("pending_credential_cleanup", []))

    def mark_credential_cleanup(self, account_id: str) -> None:
        pending = set(self.pending_credential_cleanup())
        pending.add(str(account_id))
        self._data["pending_credential_cleanup"] = sorted(pending)
        self._save()

    def clear_credential_cleanup(self, account_id: str) -> None:
        self._data["pending_credential_cleanup"] = [
            value for value in self.pending_credential_cleanup() if value != account_id
        ]
        self._save()

    def _empty(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "last_account_id": "",
            "active_account_id": "",
            "accounts": [],
            "pending_credential_cleanup": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._empty()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("accounts"), list):
                raise ValueError("invalid account index")
            clean = self._empty()
            clean["last_account_id"] = str(data.get("last_account_id", "") or "")
            clean["active_account_id"] = str(data.get("active_account_id", "") or "")
            clean["pending_credential_cleanup"] = [
                str(value) for value in data.get("pending_credential_cleanup", [])
                if isinstance(value, str)
            ]
            seen = set()
            for raw in data["accounts"]:
                if not isinstance(raw, dict) or not str(raw.get("username", "")).strip():
                    continue
                account_id = account_id_for_username(raw["username"])
                if account_id in seen:
                    continue
                seen.add(account_id)
                clean["accounts"].append({
                    "account_id": account_id,
                    "username": str(raw["username"]).strip(),
                    "display_name": str(raw.get("display_name", raw["username"])).strip(),
                    "remember_password": bool(raw.get("remember_password", False)),
                    "auto_login": bool(raw.get("auto_login", False) and raw.get("remember_password", False)),
                    "last_login_at": str(raw.get("last_login_at", "")),
                })
            return clean
        except (OSError, ValueError, json.JSONDecodeError):
            stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            self._path.replace(self._path.with_name(f"{self._path.name}.{stamp}.corrupt"))
            data = self._empty()
            self._write(data)
            return data

    def _save(self) -> None:
        self._write(self._data)

    def _write(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, self._path)
