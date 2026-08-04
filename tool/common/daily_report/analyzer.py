"""Deterministic metrics for the fixed Daily Report canvas."""

from __future__ import annotations

from datetime import date, datetime, tzinfo

from .models import DailyReportAnalysis, DailyReportIssue


STALE_DAYS = 7


def analyze_daily_report(
    issues: tuple[DailyReportIssue, ...] | list[DailyReportIssue],
    *,
    day: date,
    previous=None,
    local_timezone: tzinfo | None = None,
) -> DailyReportAnalysis:
    del previous
    local_timezone = local_timezone or datetime.now().astimezone().tzinfo
    current = tuple({issue.key: issue for issue in issues}.values())
    created_today = tuple(
        sorted(
            issue.key
            for issue in current
            if issue.created and _local_date(issue.created, local_timezone) == day
        )
    )
    updated_today = tuple(
        sorted(
            issue.key
            for issue in current
            if issue.updated and _local_date(issue.updated, local_timezone) == day
        )
    )
    stale = tuple(
        sorted(
            issue.key
            for issue in current
            if issue.updated is None
            or (day - _local_date(issue.updated, local_timezone)).days >= STALE_DAYS
        )
    )
    return DailyReportAnalysis(
        day=day,
        issues=current,
        total=len(current),
        created_today=created_today,
        updated_today=updated_today,
        stale=stale,
    )


def _local_date(value: datetime, local_timezone: tzinfo) -> date:
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(local_timezone).date()
