"""Daily Report data used by the fixed report canvas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class DailyReportIssue:
    key: str
    summary: str
    status: str
    assignee: str
    priority: str
    components: tuple[str, ...]
    labels: tuple[str, ...]
    created: datetime | None
    updated: datetime | None
    url: str = ""


@dataclass(frozen=True)
class DailyReportAnalysis:
    day: date
    issues: tuple[DailyReportIssue, ...]
    total: int
    created_today: tuple[str, ...]
    updated_today: tuple[str, ...]
    stale: tuple[str, ...]
