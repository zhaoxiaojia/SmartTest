from dataclasses import replace
from pathlib import Path
import subprocess

import pytest

from support.scheduling import (
    DailyTrigger,
    LaunchCommand,
    RegisteredTask,
    ScheduleDefinition,
    WeeklyTrigger,
    WindowsTaskScheduler,
    resolve_launch_command,
    serialize_arguments,
)
from support.scheduling.windows import (
    _TaskSchedulerComAdapter,
    _weekday_to_windows_mask,
    _windows_mask_to_weekday,
)


class FakeTaskAdapter:
    def __init__(self):
        self.tasks = {}

    def upsert(self, definition):
        self.tasks[definition.task_id] = RegisteredTask.from_definition(definition)

    def set_enabled(self, task_id, enabled):
        self.tasks[task_id] = replace(
            self.tasks[task_id], enabled=enabled, trigger_enabled=enabled
        )

    def delete(self, task_id):
        return self.tasks.pop(task_id, None) is not None

    def list(self, prefix):
        return [task for task_id, task in self.tasks.items() if task_id.startswith(prefix)]


def _definition(task_id="SmartTest.Example.daily", enabled=True):
    return ScheduleDefinition(
        task_id=task_id,
        description="Example",
        launch=LaunchCommand(Path("C:/SmartTest.exe"), ("--run", "daily")),
        trigger=DailyTrigger(18, 0),
        enabled=enabled,
    )


def test_daily_and_weekly_triggers_validate_clock_values():
    assert DailyTrigger(18, 30).hour == 18
    assert WeeklyTrigger(4, 0, 5).weekday == 4
    with pytest.raises(ValueError):
        DailyTrigger(24, 0)
    with pytest.raises(ValueError):
        WeeklyTrigger(7, 0, 5)


@pytest.mark.parametrize(
    ("weekday", "windows_mask"),
    [(0, 2), (1, 4), (2, 8), (3, 16), (4, 32), (5, 64), (6, 1)],
)
def test_weekday_round_trips_all_windows_task_scheduler_day_bits(
    weekday, windows_mask
):
    assert _weekday_to_windows_mask(weekday) == windows_mask
    assert _windows_mask_to_weekday(windows_mask) == weekday


@pytest.mark.parametrize("windows_mask", [0, 3, 5, 65, 128])
def test_invalid_or_multi_day_windows_masks_are_not_single_weekdays(windows_mask):
    assert _windows_mask_to_weekday(windows_mask) is None


@pytest.mark.parametrize("weekday", [-1, 7])
def test_invalid_python_weekdays_are_rejected(weekday):
    with pytest.raises(ValueError):
        _weekday_to_windows_mask(weekday)


def test_scheduler_round_trips_definition_with_fake_adapter():
    adapter = FakeTaskAdapter()
    scheduler = WindowsTaskScheduler(adapter)

    state = scheduler.upsert(_definition())

    assert state.reconciliation == "ok"
    assert scheduler.list("SmartTest.Example.")[0].reconciliation == "ok"


def test_scheduler_enables_existing_task_and_reports_missing_task():
    scheduler = WindowsTaskScheduler(FakeTaskAdapter())
    assert scheduler.set_enabled("missing", True).reconciliation == "task_missing"
    scheduler.upsert(_definition(enabled=False))
    state = scheduler.set_enabled("SmartTest.Example.daily", True)
    assert state.registered and state.enabled


def test_scheduler_deletes_existing_task_and_is_idempotent():
    adapter = FakeTaskAdapter()
    scheduler = WindowsTaskScheduler(adapter)
    scheduler.upsert(_definition())
    assert scheduler.delete("SmartTest.Example.daily") is True
    assert scheduler.delete("SmartTest.Example.daily") is False
    assert scheduler.list("SmartTest.Example.") == []


@pytest.mark.parametrize(
    "mutation",
    [
        {"action_count": 2},
        {"action_type": 5},
        {"trigger_type": 9},
        {"parsed": False},
    ],
)
def test_scheduler_marks_malformed_native_task_invalid(mutation):
    adapter = FakeTaskAdapter()
    scheduler = WindowsTaskScheduler(adapter)
    scheduler.upsert(_definition())
    task_id = "SmartTest.Example.daily"
    adapter.tasks[task_id] = replace(adapter.tasks[task_id], **mutation)
    assert scheduler.list("SmartTest.Example.")[0].reconciliation == "invalid_task"


def test_launch_resolution_and_windows_argument_serialization(tmp_path):
    source = resolve_launch_command(
        executable=Path("C:/Python/python.exe"),
        packaged=False,
        main_script=tmp_path / "main.py",
    )
    assert source.arguments == (str((tmp_path / "main.py").resolve()),)
    packaged = resolve_launch_command(
        executable=tmp_path / "SmartTest.exe", packaged=True
    )
    assert packaged.arguments == ()
    arguments = (r"C:\Smart Test\main.py", "--label", 'say "hello"')
    assert serialize_arguments(arguments) == subprocess.list2cmdline(arguments)


def test_com_adapter_maps_daily_and_weekly_triggers_without_connecting():
    class Box:
        pass

    class Factory:
        def __init__(self):
            self.created = []

        def Create(self, kind):
            value = Box()
            value.kind = kind
            self.created.append(value)
            return value

    class Service:
        def NewTask(self, _flags):
            task = Box()
            task.RegistrationInfo, task.Settings = Box(), Box()
            task.Actions, task.Triggers = Factory(), Factory()
            return task

    class Folder:
        def GetTask(self, task_id):
            return self.registered_tasks[task_id]

        def DeleteTask(self, task_id, _flags):
            del self.registered_tasks[task_id]

        def RegisterTaskDefinition(self, *args):
            self.registered = args

    adapter = _TaskSchedulerComAdapter.__new__(_TaskSchedulerComAdapter)
    adapter._service, adapter._folder = Service(), Folder()
    adapter.upsert(_definition())
    daily_task = adapter._folder.registered[1]
    assert daily_task.Triggers.created[0].kind == adapter.TASK_TRIGGER_DAILY
    assert (daily_task.Triggers.created[0].DaysInterval,) == (1,)

    weekly = replace(_definition("SmartTest.Example.weekly"), trigger=WeeklyTrigger(4, 0, 5))
    adapter.upsert(weekly)
    weekly_task = adapter._folder.registered[1]
    assert weekly_task.Triggers.created[0].kind == adapter.TASK_TRIGGER_WEEKLY
    assert weekly_task.Triggers.created[0].DaysOfWeek == 32
    adapter._folder.registered_tasks = {"SmartTest.Example.weekly": weekly_task}
    assert adapter.delete("SmartTest.Example.weekly") is True
    assert adapter.delete("SmartTest.Example.weekly") is False
