from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from ui.frontend_state import FrontendStateStore, normalize_frontend_user


_IDENTITY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


class FrontendStateBridge(QObject):
    stateContextChanged = Signal()

    def __init__(
        self,
        auth_bridge: QObject,
        store: FrontendStateStore,
        *,
        legacy_path: Path | None = None,
    ):
        super().__init__(auth_bridge)
        self._auth = auth_bridge
        self._store = store
        self._legacy_path = Path(legacy_path) if legacy_path else None
        self._registrations: set[tuple[str, str]] = set()
        self._account = normalize_frontend_user(self._auth.currentUsername())
        self._migrate()
        self._auth.authChanged.connect(self._on_auth_changed)

    @Slot(str, str, str, "QVariant", result="QVariant")
    def restore(
        self,
        scope: str,
        key: str,
        value_type: str,
        default_value: Any,
    ) -> Any:
        identity = self._identity(scope, key)
        if identity in self._registrations:
            raise ValueError("Frontend state identity is already registered.")
        self._registrations.add(identity)
        return self._store.load(
            self._user(identity[0]), *identity, value_type, default_value
        )

    @Slot(str, str, str, "QVariant", bool)
    def save(
        self,
        scope: str,
        key: str,
        value_type: str,
        value: Any,
        sensitive: bool,
    ) -> None:
        identity = self._identity(scope, key)
        if identity not in self._registrations:
            raise ValueError("Frontend state identity is not registered.")
        to_variant = getattr(value, "toVariant", None)
        if callable(to_variant):
            value = to_variant()
        self._store.save(
            self._user(identity[0]), *identity, value_type, value,
            sensitive=sensitive,
        )

    @Slot(str, str)
    def release(self, scope: str, key: str) -> None:
        self._registrations.discard(self._identity(scope, key))

    @Slot()
    def _on_auth_changed(self) -> None:
        account = normalize_frontend_user(self._auth.currentUsername())
        if account == self._account:
            return
        self._account = account
        self._registrations.clear()
        self._migrate()
        self.stateContextChanged.emit()

    def _migrate(self) -> None:
        if self._legacy_path:
            self._store.migrate_legacy_ini(
                self._legacy_path, self._account
            )

    def _identity(self, scope: str, key: str) -> tuple[str, str]:
        normalized = (str(scope or "").strip(), str(key or "").strip())
        if not all(_IDENTITY.fullmatch(value) for value in normalized):
            raise ValueError("Frontend state scope and key must be stable identifiers.")
        return normalized

    def _user(self, scope: str) -> str:
        return "global" if scope == "global" else self._account
