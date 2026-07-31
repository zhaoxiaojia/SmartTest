from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
import re
import subprocess
import sys
from typing import Literal, Sequence

from .plans import AuditPlan


TASK_PREFIX = "SmartTest.ProjectWeeklyAudit."
BACKGROUND_SWITCH = "--project-weekly-audit-plan"


@dataclass(frozen=True)
class AuditLaunchCommand:
    executable: Path
    arguments: tuple[str, ...] = ()

    def for_plan(self, plan_id: str) -> tuple[str, ...]:
        return self.arguments + (BACKGROUND_SWITCH, _plan_id(plan_id))


def resolve_audit_launch_command(
    *, executable: Path | None = None, packaged: bool | None = None,
    main_script: Path | None = None,
) -> AuditLaunchCommand:
    executable_was_provided = executable is not None
    executable = Path(executable or sys.executable).resolve()
    if packaged is None:
        packaged = bool(
            getattr(sys, "frozen", False)
            or executable_was_provided and executable.suffix.casefold() == ".exe"
        )
    if packaged:
        return AuditLaunchCommand(executable)
    script = Path(
        main_script or Path(__file__).resolve().parents[2] / "main.py",
    ).resolve()
    return AuditLaunchCommand(executable, (str(script),))


@dataclass(frozen=True)
class ScheduledPlanState:
    plan_id: str
    task_name: str
    enabled: bool
    registered: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_result_code: int | None
    reconciliation: Literal["ok", "config_missing", "task_missing", "invalid_task"]


@dataclass(frozen=True)
class TaskDefinition:
    name: str
    executable: Path
    arguments: tuple[str, ...]
    serialized_arguments: str = ""
    weekday: int = 4
    hour: int = 0
    minute: int = 5
    enabled: bool = True
    trigger_enabled: bool = True
    action_count: int = 1
    trigger_count: int = 1
    action_type: int = 0
    trigger_type: int = 3
    parsed: bool = True
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_result_code: int | None = None

    def with_enabled(self, enabled: bool):
        return replace(
            self, enabled=bool(enabled), trigger_enabled=bool(enabled),
        )

    def with_arguments(self, arguments):
        return replace(
            self, arguments=tuple(arguments), serialized_arguments="",
        )


class WindowsAuditScheduler:
    def __init__(self, native=None, launch_command=None):
        self._native = native or _TaskSchedulerComAdapter()
        self._launch_command = (
            launch_command or resolve_audit_launch_command()
        )

    def upsert(
        self, plan: AuditPlan, executable: Path | None = None,
    ) -> ScheduledPlanState:
        plan_id = _plan_id(plan.plan_id)
        if executable is not None:
            self._launch_command = resolve_audit_launch_command(
                executable=executable,
                packaged=Path(executable).suffix.casefold() == ".exe",
            )
        definition = TaskDefinition(
            name=TASK_PREFIX + plan_id,
            executable=self._launch_command.executable,
            arguments=self._launch_command.for_plan(plan_id),
            enabled=bool(plan.enabled),
            trigger_enabled=bool(plan.enabled),
        )
        self._native.upsert(definition)
        return _state(plan_id, definition, "ok")

    def set_enabled(self, plan_id: str, enabled: bool) -> ScheduledPlanState:
        value = _plan_id(plan_id)
        name = TASK_PREFIX + value
        tasks = {task.name: task for task in self._native.list(TASK_PREFIX)}
        current = tasks.get(name)
        if current is None:
            return ScheduledPlanState(
                value, name, False, False, None, None, None, "task_missing",
            )
        self._native.set_enabled(name, enabled)
        return _state(value, current.with_enabled(enabled), "ok")

    def list(self, plans: Sequence[AuditPlan]) -> list[ScheduledPlanState]:
        configured = {_plan_id(plan.plan_id): plan for plan in plans}
        tasks = {
            task.name[len(TASK_PREFIX):]: task
            for task in self._native.list(TASK_PREFIX)
            if task.name.startswith(TASK_PREFIX)
        }
        states = []
        for plan_id, plan in configured.items():
            task = tasks.get(plan_id)
            if task is None:
                states.append(ScheduledPlanState(
                    plan_id, TASK_PREFIX + plan_id, False, False,
                    None, None, None, "task_missing",
                ))
                continue
            valid = (
                task.name == TASK_PREFIX + plan_id
                and _same_path(
                    task.executable, self._launch_command.executable,
                )
                and _arguments_match(
                    task, self._launch_command.for_plan(plan_id),
                )
                and task.action_count == 1
                and task.trigger_count == 1
                and task.action_type == _TaskSchedulerComAdapter.TASK_ACTION_EXEC
                and task.trigger_type == _TaskSchedulerComAdapter.TASK_TRIGGER_WEEKLY
                and task.parsed
                and (task.weekday, task.hour, task.minute) == (4, 0, 5)
                and task.enabled == plan.enabled
                and task.trigger_enabled == plan.enabled
            )
            states.append(_state(
                plan_id, task, "ok" if valid else "invalid_task",
            ))
        for plan_id, task in tasks.items():
            if plan_id not in configured:
                states.append(_state(plan_id, task, "config_missing"))
        return sorted(states, key=lambda row: row.plan_id)


class _TaskSchedulerComAdapter:
    TASK_CREATE_OR_UPDATE = 6
    TASK_LOGON_INTERACTIVE_TOKEN = 3
    TASK_TRIGGER_WEEKLY = 3
    TASK_ACTION_EXEC = 0
    FRIDAY = 32

    def __init__(self):
        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError("Windows Task Scheduler requires pywin32.") from exc
        service = win32com.client.Dispatch("Schedule.Service")
        service.Connect()
        self._service = service
        self._folder = service.GetFolder("\\")

    def upsert(self, definition: TaskDefinition):
        task = self._service.NewTask(0)
        task.RegistrationInfo.Description = "SmartTest Project Weekly Audit"
        task.Settings.Enabled = definition.enabled
        task.Settings.StartWhenAvailable = True
        trigger = task.Triggers.Create(self.TASK_TRIGGER_WEEKLY)
        trigger.StartBoundary = _next_start().isoformat(timespec="seconds")
        trigger.DaysOfWeek = self.FRIDAY
        trigger.WeeksInterval = 1
        trigger.Enabled = definition.enabled
        action = task.Actions.Create(self.TASK_ACTION_EXEC)
        action.Path = str(definition.executable)
        action.Arguments = _serialize_arguments(definition.arguments)
        self._folder.RegisterTaskDefinition(
            definition.name, task, self.TASK_CREATE_OR_UPDATE,
            "", "", self.TASK_LOGON_INTERACTIVE_TOKEN,
        )

    def set_enabled(self, name: str, enabled: bool):
        registered = self._folder.GetTask(name)
        registered.Enabled = bool(enabled)
        definition = registered.Definition
        definition.Settings.Enabled = bool(enabled)
        for index in range(1, int(definition.Triggers.Count) + 1):
            definition.Triggers.Item(index).Enabled = bool(enabled)
        self._folder.RegisterTaskDefinition(
            name, definition, self.TASK_CREATE_OR_UPDATE,
            "", "", self.TASK_LOGON_INTERACTIVE_TOKEN,
        )

    def list(self, prefix: str):
        result = []
        for task in self._folder.GetTasks(1):
            try:
                name = str(task.Name)
            except Exception:
                continue
            if not name.startswith(prefix):
                continue
            try:
                definition = task.Definition
                action_count = int(definition.Actions.Count)
                trigger_count = int(definition.Triggers.Count)
                action = definition.Actions.Item(1) if action_count else None
                trigger = definition.Triggers.Item(1) if trigger_count else None
                action_type = int(action.Type) if action else -1
                trigger_type = int(trigger.Type) if trigger else -1
                executable = Path(str(action.Path)) if action else Path()
                serialized_arguments = (
                    str(action.Arguments or "") if action else ""
                )
                boundary = _boundary(trigger.StartBoundary) if trigger else None
                result.append(TaskDefinition(
                    name=name,
                    executable=executable,
                    arguments=(),
                    serialized_arguments=serialized_arguments,
                    weekday=(
                        4 if trigger and int(trigger.DaysOfWeek) == self.FRIDAY else -1
                    ),
                    hour=boundary.hour if boundary else -1,
                    minute=boundary.minute if boundary else -1,
                    enabled=bool(task.Enabled),
                    trigger_enabled=bool(trigger.Enabled) if trigger else False,
                    action_count=action_count,
                    trigger_count=trigger_count,
                    action_type=action_type,
                    trigger_type=trigger_type,
                    next_run_at=_com_datetime(task.NextRunTime),
                    last_run_at=_com_datetime(task.LastRunTime),
                    last_result_code=int(task.LastTaskResult),
                ))
            except Exception:
                result.append(TaskDefinition(
                    name=name,
                    executable=Path(),
                    arguments=("", ""),
                    weekday=-1,
                    hour=-1,
                    minute=-1,
                    enabled=False,
                    trigger_enabled=False,
                    action_count=-1,
                    trigger_count=-1,
                    action_type=-1,
                    trigger_type=-1,
                    parsed=False,
                ))
        return result


def _state(plan_id, task, reconciliation):
    return ScheduledPlanState(
        plan_id=plan_id,
        task_name=task.name,
        enabled=task.enabled,
        registered=True,
        next_run_at=task.next_run_at,
        last_run_at=task.last_run_at,
        last_result_code=task.last_result_code,
        reconciliation=reconciliation,
    )


def _plan_id(value) -> str:
    text = str(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise ValueError("Invalid audit plan id")
    return text


def _same_path(left: Path, right: Path) -> bool:
    return str(Path(left).resolve()).casefold() == str(Path(right).resolve()).casefold()


def _serialize_arguments(arguments) -> str:
    return subprocess.list2cmdline([str(value) for value in arguments])


def _arguments_match(task: TaskDefinition, expected) -> bool:
    actual = (
        task.serialized_arguments
        if task.serialized_arguments
        else _serialize_arguments(task.arguments)
    )
    return actual == _serialize_arguments(expected)


def _next_start() -> datetime:
    now = datetime.now().astimezone()
    days = (4 - now.weekday()) % 7
    candidate = (now + timedelta(days=days)).replace(
        hour=0, minute=5, second=0, microsecond=0,
    )
    return candidate if candidate > now else candidate + timedelta(days=7)


def _boundary(value) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _com_datetime(value):
    try:
        result = datetime(
            value.year, value.month, value.day, value.hour, value.minute, value.second,
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return None if result.year <= 1900 else result.astimezone()
