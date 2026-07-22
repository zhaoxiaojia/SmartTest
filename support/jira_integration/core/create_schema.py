from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CreateFieldControl(str, Enum):
    TEXT = "text"
    MULTILINE = "multiline"
    SINGLE = "single"
    MULTI = "multi"
    CASCADE = "cascade"
    USER = "user"


@dataclass(frozen=True)
class CreateFieldOption:
    value: str
    label: str
    children: tuple["CreateFieldOption", ...] = ()


@dataclass(frozen=True)
class CreateFieldSchema:
    field_id: str
    name: str
    required: bool
    control: CreateFieldControl
    options: tuple[CreateFieldOption, ...] = ()
    value: Any = None
    children: tuple["CreateFieldSchema", ...] = ()
