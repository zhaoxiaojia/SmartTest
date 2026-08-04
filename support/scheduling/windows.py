"""Windows Task Scheduler adapter and reconciliation."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from .launch import serialize_arguments
from .models import (
    DailyTrigger,
    LaunchCommand,
    RegisteredTask,
    ScheduleDefinition,
    ScheduledTaskState,
    WeeklyTrigger,
)


_WINDOWS_WEEKDAY_MASKS = (2, 4, 8, 16, 32, 64, 1)


def _weekday_to_windows_mask(weekday: int) -> int:
    if not isinstance(weekday, int) or not 0 <= weekday < len(_WINDOWS_WEEKDAY_MASKS):
        raise ValueError("Invalid weekday")
    return _WINDOWS_WEEKDAY_MASKS[weekday]


def _windows_mask_to_weekday(mask: int) -> int | None:
    try:
        return _WINDOWS_WEEKDAY_MASKS.index(mask)
    except ValueError:
        return None


class WindowsTaskScheduler:
    def __init__(self, adapter=None) -> None:
        self._adapter = adapter
        self._definitions: dict[str, ScheduleDefinition] = {}

    def _native(self):
        if self._adapter is None:
            self._adapter = _TaskSchedulerComAdapter()
        return self._adapter

    def upsert(self, definition: ScheduleDefinition) -> ScheduledTaskState:
        self._native().upsert(definition)
        self._definitions[definition.task_id] = definition
        return _state(RegisteredTask.from_definition(definition), "ok")

    def set_enabled(self, task_id: str, enabled: bool) -> ScheduledTaskState:
        current = next(
            (task for task in self._native().list(task_id) if task.task_id == task_id),
            None,
        )
        if current is None:
            return ScheduledTaskState(task_id, False, False, None, None, None, "task_missing")
        self._native().set_enabled(task_id, bool(enabled))
        updated = replace(current, enabled=bool(enabled), trigger_enabled=bool(enabled))
        if task_id in self._definitions:
            self._definitions[task_id] = replace(
                self._definitions[task_id], enabled=bool(enabled)
            )
        return _state(updated, "ok" if _valid(updated, self._definitions.get(task_id)) else "invalid_task")

    def delete(self, task_id: str) -> bool:
        deleted = bool(self._native().delete(task_id))
        self._definitions.pop(task_id, None)
        return deleted

    def list(
        self,
        prefix: str,
        definitions: tuple[ScheduleDefinition, ...] | list[ScheduleDefinition] | None = None,
    ) -> list[ScheduledTaskState]:
        expected = (
            {definition.task_id: definition for definition in definitions}
            if definitions is not None
            else {key: value for key, value in self._definitions.items() if key.startswith(prefix)}
        )
        tasks = {task.task_id: task for task in self._native().list(prefix)}
        states = []
        for task_id, task in tasks.items():
            definition = expected.get(task_id)
            reconciliation = (
                "config_missing"
                if definitions is not None and definition is None
                else "ok" if _valid(task, definition) else "invalid_task"
            )
            states.append(_state(task, reconciliation))
        for task_id in expected.keys() - tasks.keys():
            states.append(
                ScheduledTaskState(task_id, False, False, None, None, None, "task_missing")
            )
        return sorted(states, key=lambda state: state.task_id)


class _TaskSchedulerComAdapter:
    TASK_CREATE_OR_UPDATE = 6
    TASK_LOGON_INTERACTIVE_TOKEN = 3
    TASK_TRIGGER_DAILY = 2
    TASK_TRIGGER_WEEKLY = 3
    TASK_ACTION_EXEC = 0

    def __init__(self) -> None:
        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError("Windows Task Scheduler requires pywin32.") from exc
        service = win32com.client.Dispatch("Schedule.Service")
        service.Connect()
        self._service = service
        self._folder = service.GetFolder("\\")

    def upsert(self, definition: ScheduleDefinition) -> None:
        task = self._service.NewTask(0)
        task.RegistrationInfo.Description = definition.description
        task.Settings.Enabled = definition.enabled
        task.Settings.StartWhenAvailable = True
        trigger_type = (
            self.TASK_TRIGGER_DAILY
            if isinstance(definition.trigger, DailyTrigger)
            else self.TASK_TRIGGER_WEEKLY
        )
        trigger = task.Triggers.Create(trigger_type)
        trigger.StartBoundary = _next_start(definition.trigger).isoformat(timespec="seconds")
        if isinstance(definition.trigger, DailyTrigger):
            trigger.DaysInterval = 1
        else:
            trigger.DaysOfWeek = _weekday_to_windows_mask(
                definition.trigger.weekday
            )
            trigger.WeeksInterval = 1
        trigger.Enabled = definition.enabled
        action = task.Actions.Create(self.TASK_ACTION_EXEC)
        action.Path = str(definition.launch.executable)
        action.Arguments = serialize_arguments(definition.launch.arguments)
        self._folder.RegisterTaskDefinition(
            definition.task_id,
            task,
            self.TASK_CREATE_OR_UPDATE,
            "",
            "",
            self.TASK_LOGON_INTERACTIVE_TOKEN,
        )

    def set_enabled(self, task_id: str, enabled: bool) -> None:
        registered = self._folder.GetTask(task_id)
        registered.Enabled = bool(enabled)
        definition = registered.Definition
        definition.Settings.Enabled = bool(enabled)
        for index in range(1, int(definition.Triggers.Count) + 1):
            definition.Triggers.Item(index).Enabled = bool(enabled)
        self._folder.RegisterTaskDefinition(
            task_id,
            definition,
            self.TASK_CREATE_OR_UPDATE,
            "",
            "",
            self.TASK_LOGON_INTERACTIVE_TOKEN,
        )

    def delete(self, task_id: str) -> bool:
        try:
            self._folder.GetTask(task_id)
        except Exception:
            return False
        self._folder.DeleteTask(task_id, 0)
        return True

    def list(self, prefix: str) -> list[RegisteredTask]:
        result = []
        for task in self._folder.GetTasks(1):
            try:
                task_id = str(task.Name)
            except Exception:
                continue
            if not task_id.startswith(prefix):
                continue
            result.append(self._read(task_id, task))
        return result

    def _read(self, task_id: str, task) -> RegisteredTask:
        try:
            definition = task.Definition
            action_count = int(definition.Actions.Count)
            trigger_count = int(definition.Triggers.Count)
            action = definition.Actions.Item(1) if action_count else None
            trigger = definition.Triggers.Item(1) if trigger_count else None
            action_type = int(action.Type) if action else -1
            trigger_type = int(trigger.Type) if trigger else -1
            launch = LaunchCommand(
                Path(str(action.Path)) if action else Path(),
                (str(action.Arguments or ""),) if action else (),
            )
            schedule = _read_trigger(trigger, trigger_type)
            return RegisteredTask(
                task_id=task_id,
                description=str(definition.RegistrationInfo.Description or ""),
                launch=launch,
                trigger=schedule,
                enabled=bool(task.Enabled),
                trigger_enabled=bool(trigger.Enabled) if trigger else False,
                action_count=action_count,
                trigger_count=trigger_count,
                action_type=action_type,
                trigger_type=trigger_type,
                next_run_at=_com_datetime(task.NextRunTime),
                last_run_at=_com_datetime(task.LastRunTime),
                last_result_code=int(task.LastTaskResult),
            )
        except Exception:
            return RegisteredTask(
                task_id, "", LaunchCommand(Path()), None, False, False,
                action_count=-1, trigger_count=-1, action_type=-1,
                trigger_type=-1, parsed=False,
            )


def _valid(task: RegisteredTask, expected: ScheduleDefinition | None) -> bool:
    valid = (
        task.parsed
        and task.action_count == 1
        and task.trigger_count == 1
        and task.action_type == _TaskSchedulerComAdapter.TASK_ACTION_EXEC
        and task.trigger_type in {
            _TaskSchedulerComAdapter.TASK_TRIGGER_DAILY,
            _TaskSchedulerComAdapter.TASK_TRIGGER_WEEKLY,
        }
        and task.trigger is not None
        and task.enabled == task.trigger_enabled
    )
    if not valid or expected is None:
        return valid
    arguments = task.launch.arguments
    if len(arguments) == 1:
        actual_arguments = arguments[0]
    else:
        actual_arguments = serialize_arguments(arguments)
    return (
        _same_path(task.launch.executable, expected.launch.executable)
        and actual_arguments == serialize_arguments(expected.launch.arguments)
        and task.trigger == expected.trigger
        and task.enabled == expected.enabled
    )


def _state(task: RegisteredTask, reconciliation: str) -> ScheduledTaskState:
    return ScheduledTaskState(
        task.task_id,
        task.enabled,
        True,
        task.next_run_at,
        task.last_run_at,
        task.last_result_code,
        reconciliation,
    )


def _same_path(left: Path, right: Path) -> bool:
    return str(Path(left).resolve()).casefold() == str(Path(right).resolve()).casefold()


def _next_start(trigger: DailyTrigger | WeeklyTrigger) -> datetime:
    now = datetime.now().astimezone()
    if isinstance(trigger, DailyTrigger):
        candidate = now.replace(hour=trigger.hour, minute=trigger.minute, second=0, microsecond=0)
        return candidate if candidate > now else candidate + timedelta(days=1)
    days = (trigger.weekday - now.weekday()) % 7
    candidate = (now + timedelta(days=days)).replace(
        hour=trigger.hour, minute=trigger.minute, second=0, microsecond=0
    )
    return candidate if candidate > now else candidate + timedelta(days=7)


def _read_trigger(trigger, trigger_type: int):
    boundary = datetime.fromisoformat(str(trigger.StartBoundary).replace("Z", "+00:00"))
    if trigger_type == _TaskSchedulerComAdapter.TASK_TRIGGER_DAILY:
        return DailyTrigger(boundary.hour, boundary.minute)
    if trigger_type == _TaskSchedulerComAdapter.TASK_TRIGGER_WEEKLY:
        weekday = _windows_mask_to_weekday(int(trigger.DaysOfWeek))
        if weekday is None:
            return None
        return WeeklyTrigger(weekday, boundary.hour, boundary.minute)
    return None


def _com_datetime(value):
    try:
        result = datetime(value.year, value.month, value.day, value.hour, value.minute, value.second)
    except (AttributeError, TypeError, ValueError):
        return None
    return None if result.year <= 1900 else result.astimezone()
