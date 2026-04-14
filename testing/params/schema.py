from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ParamType = Literal["string", "int", "float", "bool", "enum", "path", "multiline"]


@dataclass(frozen=True)
class ParamField:
    key: str
    label: str
    type: ParamType = "string"
    default: Any = ""
    description: str = ""
    group: str = ""
    required: bool = False
    enum_values: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParamSchema:
    """
    A schema describes configurable fields for a case type (or global context).
    """

    schema_id: str
    title: str
    fields: list[ParamField]


def defaults_for_schema(schema: ParamSchema) -> dict[str, Any]:
    return {f.key: f.default for f in schema.fields}

