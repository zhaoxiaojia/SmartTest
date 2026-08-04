from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from .models import AuditPeriod

def previous_business_week(now: datetime | None = None, tz=ZoneInfo("Asia/Shanghai")) -> AuditPeriod:
    current = (now or datetime.now(tz)).astimezone(tz)
    this_monday = current.date() - timedelta(days=current.weekday())
    start_date = this_monday - timedelta(days=7)
    return AuditPeriod(
        datetime.combine(start_date, time.min, tz),
        datetime.combine(start_date + timedelta(days=7), time.min, tz),
    )

def current_reporting_window(now: datetime | None = None, tz=ZoneInfo("Asia/Shanghai")) -> AuditPeriod:
    current = (now or datetime.now(tz)).astimezone(tz)
    monday = current.date() - timedelta(days=current.weekday())
    return AuditPeriod(
        datetime.combine(monday, time.min, tz),
        current,
    )


def scheduled_reporting_window(
    now: datetime | None = None,
    tz=ZoneInfo("Asia/Shanghai"),
) -> AuditPeriod:
    current = (now or datetime.now(tz)).astimezone(tz)
    monday = current.date() - timedelta(days=current.weekday())
    return AuditPeriod(
        datetime.combine(monday, time.min, tz),
        datetime.combine(monday + timedelta(days=4), time.min, tz),
    )
