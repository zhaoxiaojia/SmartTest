from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class JiraFieldMetadata:
    field_id: str
    name: str
    schema_type: str | None = None
    schema_items: str | None = None
    custom: bool = False
    custom_id: int | None = None
    schema_custom: str | None = None
    clause_names: tuple[str, ...] = ()
    navigable: bool = True
    searchable: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["clause_names"] = list(self.clause_names)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JiraFieldMetadata":
        return cls(
            field_id=str(data.get("field_id", "")),
            name=str(data.get("name", "")),
            schema_type=data.get("schema_type"),
            schema_items=data.get("schema_items"),
            custom=bool(data.get("custom", False)),
            custom_id=data.get("custom_id"),
            schema_custom=data.get("schema_custom"),
            clause_names=tuple(data.get("clause_names") or ()),
            navigable=bool(data.get("navigable", True)),
            searchable=bool(data.get("searchable", True)),
        )
