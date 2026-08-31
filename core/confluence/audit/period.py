from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .models import AuditPeriod


_SHANGHAI = ZoneInfo("Asia/Shanghai")


def previous_business_week(
    now: datetime | None = None, tz: ZoneInfo = _SHANGHAI,
) -> AuditPeriod:
    current = (now or datetime.now(tz)).astimezone(tz)
    this_monday = current.date() - timedelta(days=current.weekday())
    start = this_monday - timedelta(days=7)
    return AuditPeriod(
        datetime.combine(start, time.min, tz),
        datetime.combine(start + timedelta(days=7), time.min, tz),
    )


def manual_audit_period(
    start: date, end: date, tz: ZoneInfo = _SHANGHAI,
) -> AuditPeriod:
    return AuditPeriod(
        datetime.combine(start, time.min, tz),
        datetime.combine(end, time.min, tz),
    )
