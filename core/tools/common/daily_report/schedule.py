"""Single global schedule for the Daily Report batch."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path

from support.scheduling import (
    DailyTrigger, ScheduleDefinition, WeeklyTrigger,
    WindowsTaskScheduler, resolve_launch_command,
)


TASK_ID = "SmartTest.DailyReport.Batch"
PREPARATION_LEAD_MINUTES = 5


@dataclass(frozen=True)
class BatchSchedule:
    cadence: str
    hour: int
    minute: int
    weekday: int | None = None
    enabled: bool = True


class DailyReportScheduleManager:
    def __init__(self, path: str | Path, *, scheduler=None, launch=None):
        self.path = Path(path)
        self._scheduler = scheduler or WindowsTaskScheduler()
        self._launch = launch or resolve_launch_command()

    def load(self) -> BatchSchedule | None:
        if not self.path.is_file():
            return None
        return BatchSchedule(**json.loads(self.path.read_text("utf-8")))

    def save(self, cadence: str, *, hour: int, minute: int, weekday=None):
        cadence = str(cadence)
        if cadence == "daily":
            trigger = _preparation_trigger(cadence, hour, minute, weekday)
            weekday = None
        elif cadence == "weekly":
            trigger = _preparation_trigger(cadence, hour, minute, weekday)
            weekday = int(weekday)
        else:
            raise ValueError("Schedule cadence must be daily or weekly")
        value = BatchSchedule(cadence, int(hour), int(minute), weekday, True)
        definition = ScheduleDefinition(
            TASK_ID, "SmartTest Daily Report batch",
            self._launch.for_arguments("--daily-report-run"), trigger, True,
        )
        state = self._scheduler.upsert(definition)
        self._write(value)
        return state

    def delete(self) -> bool:
        deleted = self._scheduler.delete(TASK_ID)
        if self.path.is_file():
            self.path.unlink()
        return deleted

    def set_enabled(self, enabled: bool):
        value = self.load()
        if value is None:
            raise ValueError("Daily Report schedule is not configured")
        state = self._scheduler.set_enabled(TASK_ID, bool(enabled))
        self._write(replace(value, enabled=bool(enabled)))
        return state

    def state(self):
        value = self.load()
        if value is None:
            return None
        states = self._scheduler.list(TASK_ID, [self._definition(value)])
        return states[0] if states else None

    def _definition(self, value: BatchSchedule):
        trigger = _preparation_trigger(
            value.cadence, value.hour, value.minute, value.weekday
        )
        return ScheduleDefinition(
            TASK_ID, "SmartTest Daily Report batch",
            self._launch.for_arguments("--daily-report-run"),
            trigger, value.enabled,
        )

    def _write(self, value: BatchSchedule) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value.__dict__, indent=2), "utf-8")
        temporary.replace(self.path)


def _preparation_trigger(cadence, hour, minute, weekday=None):
    if cadence == "daily":
        target = DailyTrigger(int(hour), int(minute))
    else:
        target = WeeklyTrigger(int(weekday), int(hour), int(minute))
    send_minutes = target.hour * 60 + target.minute
    start_minutes = (send_minutes - PREPARATION_LEAD_MINUTES) % (24 * 60)
    start_hour, start_minute = divmod(start_minutes, 60)
    if cadence == "daily":
        return DailyTrigger(start_hour, start_minute)
    start_weekday = (
        target.weekday - int(send_minutes < PREPARATION_LEAD_MINUTES)
    ) % 7
    return WeeklyTrigger(start_weekday, start_hour, start_minute)
