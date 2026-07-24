from __future__ import annotations

import copy
import json
import math
import time
import uuid
from pathlib import Path
from string import Formatter
from typing import Any, Callable


_STRING_ROW_FIELDS = {
    "role",
    "author",
    "message",
    "timestamp",
    "kind",
    "state",
    "message_template",
    "timestamp_template",
}
_VALUES_ROW_FIELDS = {"message_values", "timestamp_values"}
_LIST_ROW_FIELDS = {"actions"}
_BOOL_ROW_FIELDS = {"is_progress"}
_ALLOWED_ROW_FIELDS = _STRING_ROW_FIELDS | _VALUES_ROW_FIELDS | _LIST_ROW_FIELDS | _BOOL_ROW_FIELDS
_TEMPLATE_VALUE_FIELDS = (
    ("message_template", "message_values"),
    ("timestamp_template", "timestamp_values"),
)
_FORMATTER = Formatter()


class JiraConversationController:
    def __init__(
        self,
        history_path: str | Path,
        *,
        initial_row: dict[str, Any],
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], float] = time.time,
        history_limit: int = 50,
    ):
        self._history_path = Path(history_path)
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._clock = clock
        self._history_limit = history_limit
        self._history = self._load_history()
        self._current_id = self._id_factory()
        self._rows = [copy.deepcopy(initial_row)]

    @property
    def current_conversation_id(self) -> str:
        return self._current_id

    def conversation_rows(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._rows)

    def history_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": str(entry.get("id", "") or ""),
                "title": str(entry.get("title", "") or ""),
                "preview": str(entry.get("preview", "") or ""),
                "updated_at": self._integer(entry.get("updated_at")),
                "message_count": len(self._entry_messages(entry)),
            }
            for entry in self._history
        ]

    def append_system(
        self,
        *,
        message_template: str,
        timestamp_template: str,
        message_values: dict[str, Any] | None = None,
        timestamp_values: dict[str, Any] | None = None,
    ) -> None:
        self._rows.append(
            self.system_row(
                message_template=message_template,
                timestamp_template=timestamp_template,
                message_values=message_values,
                timestamp_values=timestamp_values,
            )
        )

    def append_user(self, *, author: str, message: str, timestamp: str) -> None:
        self._append_message(role="user", author=author, message=message, timestamp=timestamp)

    def append_assistant(self, *, message: str, timestamp: str) -> None:
        self._append_message(role="assistant", author="SmartTest AI", message=message, timestamp=timestamp)

    def replace_progress(self, *, message: str, timestamp: str) -> None:
        clean = str(message or "").strip()
        if not clean:
            return
        if self._rows and self._rows[-1].get("is_progress") is True:
            self._rows[-1].update(message=clean, timestamp=str(timestamp or ""))
            return
        self._rows.append(
            {
                "role": "assistant",
                "author": "SmartTest AI",
                "message": clean,
                "timestamp": str(timestamp or ""),
                "is_progress": True,
            }
        )

    def remove_progress(self) -> None:
        self._rows = [row for row in self._rows if row.get("is_progress") is not True]

    def persist(self) -> None:
        messages = [
            copy.deepcopy(row)
            for row in self._rows
            if row.get("is_progress") is not True and str(row.get("message", "") or "").strip()
        ]
        if not messages:
            return
        entry = {
            "id": self._current_id,
            "title": self._title(messages),
            "preview": self._preview(messages),
            "updated_at": int(self._clock()),
            "messages": messages,
        }
        self._history = [item for item in self._history if item.get("id") != self._current_id]
        self._history.insert(0, entry)
        self._save_history()

    def clear(self, *, initial_row: dict[str, Any]) -> None:
        self.persist()
        self._current_id = self._id_factory()
        self._rows = [copy.deepcopy(initial_row)]

    def restore(self, conversation_id: str) -> bool:
        for entry in self._history:
            if str(entry.get("id", "") or "") == str(conversation_id or ""):
                messages = self._sanitize_messages(entry.get("messages"))
                if not messages:
                    return False
                self._current_id = str(entry.get("id", "") or self._id_factory())
                self._rows = messages
                return True
        return False

    @staticmethod
    def system_row(
        *,
        message_template: str,
        timestamp_template: str,
        message_values: dict[str, Any] | None = None,
        timestamp_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "role": "assistant",
            "author": "SmartTest AI",
            "message_template": message_template,
            "message_values": dict(message_values or {}),
            "timestamp_template": timestamp_template,
            "timestamp_values": dict(timestamp_values or {}),
        }

    def _append_message(self, *, role: str, author: str, message: str, timestamp: str) -> None:
        clean = str(message or "").strip()
        if not clean:
            return
        self._rows.append(
            {
                "role": role,
                "author": str(author or ""),
                "message": clean,
                "timestamp": str(timestamp or ""),
            }
        )

    def _load_history(self) -> list[dict[str, Any]]:
        if not self._history_path.exists():
            return []
        try:
            with self._history_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        rows = payload.get("conversations") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return []
        history = [self._sanitize_history_entry(row) for row in rows[: self._history_limit]]
        return [entry for entry in history if entry is not None]

    def _save_history(self) -> None:
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._history_path.with_name(f"{self._history_path.name}.tmp")
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {"conversations": self._history[: self._history_limit]},
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        temporary_path.replace(self._history_path)

    @staticmethod
    def _entry_messages(entry: dict[str, Any]) -> list[dict[str, Any]]:
        messages = entry.get("messages")
        if not isinstance(messages, list):
            return []
        return [message for message in messages if isinstance(message, dict)]

    def _sanitize_history_entry(self, value: Any) -> dict[str, Any] | None:
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("id"), str)
            or not value["id"].strip()
        ):
            return None
        messages = self._sanitize_messages(value.get("messages"))
        if not messages:
            return None
        return {
            "id": value["id"],
            "title": str(value.get("title", "") or ""),
            "preview": str(value.get("preview", "") or ""),
            "updated_at": self._integer(value.get("updated_at")),
            "messages": messages,
        }

    @classmethod
    def _sanitize_messages(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        rows = [cls._sanitize_message_row(row) for row in value]
        return [row for row in rows if row is not None]

    @classmethod
    def _sanitize_message_row(cls, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict) or not set(value) <= _ALLOWED_ROW_FIELDS:
            return None
        if value.get("is_progress") is True:
            return None
        if not any(field in value for field in ("message", "message_template")):
            return None
        if any(field in value and not isinstance(value[field], str) for field in _STRING_ROW_FIELDS):
            return None
        if any(field in value and not cls._valid_values(value[field]) for field in _VALUES_ROW_FIELDS):
            return None
        if any(
            values_field in value and template_field not in value
            for template_field, values_field in _TEMPLATE_VALUE_FIELDS
        ):
            return None
        if any(
            template_field in value
            and not cls._valid_template(value[template_field], value.get(values_field, {}))
            for template_field, values_field in _TEMPLATE_VALUE_FIELDS
        ):
            return None
        if any(
            field in value
            and (
                not isinstance(value[field], list)
                or not all(isinstance(item, str) for item in value[field])
            )
            for field in _LIST_ROW_FIELDS
        ):
            return None
        if any(field in value and not isinstance(value[field], bool) for field in _BOOL_ROW_FIELDS):
            return None
        return copy.deepcopy(value)

    @staticmethod
    def _valid_template(template: str, values: dict[str, Any]) -> bool:
        try:
            parsed = _FORMATTER.parse(template)
            for _literal, field_name, format_spec, conversion in parsed:
                if field_name is None:
                    continue
                if (
                    not field_name
                    or not field_name.isidentifier()
                    or field_name not in values
                    or format_spec
                    or conversion
                ):
                    return False
        except ValueError:
            return False
        return True

    @staticmethod
    def _valid_values(value: Any) -> bool:
        return isinstance(value, dict) and all(
            isinstance(key, str)
            and (
                item is None
                or isinstance(item, (str, bool, int))
                or (isinstance(item, float) and math.isfinite(item))
            )
            for key, item in value.items()
        )

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _title(messages: list[dict[str, Any]]) -> str:
        for row in messages:
            if row.get("role") == "user":
                message = str(row.get("message", "") or "").strip()
                if message:
                    return message[:60]
        return ""

    @staticmethod
    def _preview(messages: list[dict[str, Any]]) -> str:
        for row in reversed(messages):
            message = str(row.get("message", "") or "").strip()
            if message:
                return " ".join(message.split())[:100]
        return ""
