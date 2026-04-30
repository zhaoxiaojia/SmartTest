from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QObject


def translated_text(template: str, **values: Any) -> dict[str, Any]:
    return {"kind": "translated", "template": template, "values": dict(values)}


def raw_text(text: str) -> dict[str, Any]:
    return {"kind": "raw", "text": text}


def render_text(owner: QObject, state: Mapping[str, Any] | None) -> str:
    if not state:
        return ""
    if state.get("kind") == "translated":
        template = str(state.get("template", "") or "")
        return owner.tr(template).format(**dict(state.get("values") or {}))
    return str(state.get("text", "") or "")


def render_template(owner: QObject, template: str, values: Mapping[str, Any] | None = None) -> str:
    return owner.tr(str(template or "")).format(**dict(values or {}))
