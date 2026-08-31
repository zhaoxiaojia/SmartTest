from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NamedValue:
    id: str = ""
    name: str = ""


@dataclass(frozen=True)
class PersonRef:
    identity: str = ""
    account: str = ""
    display_name: str = ""


@dataclass(frozen=True)
class SourceRevision:
    value: str = ""


@dataclass(frozen=True)
class FieldBag:
    values: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "FieldBag":
        return cls(tuple((str(key), value) for key, value in values.items()))
