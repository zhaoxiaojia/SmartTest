from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import xml.etree.ElementTree as ET


TraceFn = Callable[[str], None] | Callable[..., None]


class TsTextCatalog:
    def __init__(self, root_dir: Path, *, trace: TraceFn | None = None):
        self._root_dir = Path(root_dir).resolve()
        self._trace = trace
        self._cache: dict[str, dict[str, dict[str, str]]] = {}
        self._missing_logged: set[tuple[str, str, str]] = set()

    def text(self, *, locale: str, context: str, source: str) -> str:
        normalized_locale = self._normalize_locale(locale)
        normalized_context = str(context or "").strip()
        normalized_source = str(source or "").strip()
        value = self._messages(normalized_locale).get(normalized_context, {}).get(normalized_source, "")
        if not value:
            self._trace_missing(normalized_locale, normalized_context, normalized_source)
        return value

    def _normalize_locale(self, locale: str) -> str:
        value = str(locale or "").strip()
        return value if value in {"en_US", "zh_CN"} else "en_US"

    def _messages(self, locale: str) -> dict[str, dict[str, str]]:
        if locale not in self._cache:
            self._cache[locale] = self._load(locale)
        return self._cache[locale]

    def _load(self, locale: str) -> dict[str, dict[str, str]]:
        ts_path = self._ts_path(locale)
        if ts_path is None:
            self._trace_missing(locale, "<file>", f"example_{locale}.ts")
            return {}

        tree = ET.parse(ts_path)
        root = tree.getroot()
        messages: dict[str, dict[str, str]] = {}
        priorities: dict[tuple[str, str], int] = {}
        for context_node in root.findall("context"):
            name_node = context_node.find("name")
            if name_node is None or not name_node.text:
                continue
            context_name = name_node.text.strip()
            for message_node in context_node.findall("message"):
                if message_node.get("type") == "obsolete":
                    continue
                source_node = message_node.find("source")
                translation_node = message_node.find("translation")
                if source_node is None or translation_node is None or source_node.text is None:
                    continue
                translation_type = translation_node.get("type")
                if translation_type in {"obsolete", "unfinished"}:
                    continue
                text = "".join(translation_node.itertext()).strip()
                if not text:
                    continue
                source_text = source_node.text
                priority = 1 if translation_type == "vanished" else 2
                cache_key = (context_name, source_text)
                if priority < priorities.get(cache_key, 0):
                    continue
                messages.setdefault(context_name, {})[source_text] = text
                priorities[cache_key] = priority
        return messages

    def _ts_path(self, locale: str) -> Path | None:
        filename = f"example_{locale}.ts"
        candidates = [
            self._root_dir / "ui" / "example" / filename,
            Path(__file__).resolve().parents[1] / filename,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _trace_missing(self, locale: str, context: str, source: str) -> None:
        key = (locale, context, source)
        if key in self._missing_logged:
            return
        self._missing_logged.add(key)
        if self._trace is None:
            return
        try:
            self._trace("ts_text_missing", locale=locale, context=context, key=source)
        except TypeError:
            self._trace(f"ts_text_missing locale={locale} context={context} key={source}")
