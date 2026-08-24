from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


class QueryValues(Protocol):
    def get(self, key: str, default: str | None = None) -> str | None: ...
    def getlist(self, key: str) -> list[str]: ...


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _canonical_data_type(value: str | None) -> str | None:
    normalized = (value or "").strip().upper()
    if normalized in {"PERFORMANCE", "THROUGHPUT", "PEAK THROUGHPUT", "PEAK_THROUGHPUT"}:
        return "PEAK_THROUGHPUT"
    return normalized or None


@dataclass
class WifiFilters:
    product_lines: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    report_names: list[str] = field(default_factory=list)
    standards: list[str] = field(default_factory=list)
    data_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    limit: int | None = None

    @classmethod
    def from_query(cls, query: QueryValues) -> "WifiFilters":
        def parsed_date(key: str) -> date | None:
            value = query.get(key)
            return date.fromisoformat(value) if value else None

        raw_limit = query.get("limit")
        limit = int(raw_limit) if raw_limit else None
        if limit is not None and limit <= 0:
            limit = None
        return cls(
            product_lines=_unique(query.getlist("product_line")),
            projects=_unique(query.getlist("project")),
            report_names=_unique(query.getlist("report_name")),
            standards=_unique(query.getlist("standard")),
            data_type=_canonical_data_type(query.get("data_type")),
            start_date=parsed_date("start_date"),
            end_date=parsed_date("end_date"),
            limit=limit,
        )
