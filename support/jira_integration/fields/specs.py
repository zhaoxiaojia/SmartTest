from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


FieldConverter = Callable[[Any], Any]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    path: str
    default: Any = None
    converter: FieldConverter | None = None
    jira_fields: tuple[str, ...] = ()
    expand: tuple[str, ...] = ()
    heavy: bool = False

    def convert(self, value: Any) -> Any:
        if value is None:
            return self.default
        if self.converter is None:
            return value
        return self.converter(value)

    def required_jira_fields(self) -> tuple[str, ...]:
        if self.jira_fields:
            return self.jira_fields
        if not self.path.startswith("fields."):
            return ()
        segments = self.path.split(".")
        if len(segments) < 2:
            return ()
        field_name = segments[1].replace("[]", "")
        return (field_name,) if field_name else ()

    def required_expand(self) -> tuple[str, ...]:
        if self.expand:
            return self.expand
        if self.path == "changelog" or self.path.startswith("changelog."):
            return ("changelog",)
        return ()
