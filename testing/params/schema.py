from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class ParamValueType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    ENUM = "enum"
    PATH = "path"
    MULTILINE = "multiline"


class ParamCategory(str, Enum):
    GENERAL = "general"
    DEVICE = "device"
    ENVIRONMENT = "environment"
    NETWORK = "network"
    EXECUTION = "execution"
    REPORT = "report"


class ParamScope(str, Enum):
    GLOBAL_CONTEXT = "global_context"
    CASE_TYPE_SHARED = "case_type_shared"
    CASE = "case"


ParamType = Literal["string", "int", "float", "bool", "enum", "path", "multiline"] | ParamValueType


@dataclass(frozen=True)
class ParamField:
    key: str
    label: str
    type: ParamType = ParamValueType.STRING
    category: ParamCategory = ParamCategory.GENERAL
    scope: ParamScope = ParamScope.CASE
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
