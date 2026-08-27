"""Business-neutral scheduling models."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Literal


def _validate_clock(hour: int, minute: int) -> None:
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Invalid schedule time")


@dataclass(frozen=True)
class DailyTrigger:
    hour: int
    minute: int

    def __post_init__(self) -> None:
        _validate_clock(self.hour, self.minute)


@dataclass(frozen=True)
class WeeklyTrigger:
    weekday: int
    hour: int
    minute: int

    def __post_init__(self) -> None:
        if not 0 <= self.weekday <= 6:
            raise ValueError("Invalid weekday")
        _validate_clock(self.hour, self.minute)


@dataclass(frozen=True)
class LaunchCommand:
    executable: Path
    arguments: tuple[str, ...] = ()

    def for_arguments(self, *arguments: str) -> "LaunchCommand":
        return replace(self, arguments=self.arguments + tuple(arguments))


@dataclass(frozen=True)
class ScheduleDefinition:
    task_id: str
    description: str
    launch: LaunchCommand
    trigger: DailyTrigger | WeeklyTrigger
    enabled: bool = True


@dataclass(frozen=True)
class RegisteredTask:
    task_id: str
    description: str
    launch: LaunchCommand
    trigger: DailyTrigger | WeeklyTrigger | None
    enabled: bool
    trigger_enabled: bool
    action_count: int = 1
    trigger_count: int = 1
    action_type: int = 0
    trigger_type: int = 0
    parsed: bool = True
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_result_code: int | None = None

    @classmethod
    def from_definition(cls, definition: ScheduleDefinition) -> "RegisteredTask":
        trigger_type = 2 if isinstance(definition.trigger, DailyTrigger) else 3
        return cls(
            definition.task_id,
            definition.description,
            definition.launch,
            definition.trigger,
            definition.enabled,
            definition.enabled,
            trigger_type=trigger_type,
        )


@dataclass(frozen=True)
class ScheduledTaskState:
    task_id: str
    enabled: bool
    registered: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_result_code: int | None
    reconciliation: Literal[
        "ok", "config_missing", "task_missing", "invalid_task"
    ]
