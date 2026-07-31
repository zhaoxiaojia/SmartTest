from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from support.confluence_audit.models import ProjectCollectionFilter
from support.confluence_audit.plans import AuditPlan
from support.confluence_audit.scheduler import (
    AuditLaunchCommand, BACKGROUND_SWITCH, TASK_PREFIX, TaskDefinition,
    WindowsAuditScheduler,
    resolve_audit_launch_command,
    _serialize_arguments,
    _TaskSchedulerComAdapter,
)


TZ = ZoneInfo("Asia/Shanghai")


def _plan(plan_id="plan-a", enabled=True):
    now = datetime(2026, 7, 29, tzinfo=TZ)
    return AuditPlan(
        plan_id, "Weekly", ProjectCollectionFilter("https://c/projects", (2026,)),
        enabled, f"cred-{plan_id}", "ignored-config-task-name", now, now,
    )


class Adapter:
    def __init__(self):
        self.tasks = {}
        self.upserts = []

    def upsert(self, definition):
        self.upserts.append(definition)
        self.tasks[definition.name] = definition

    def set_enabled(self, name, enabled):
        self.tasks[name] = self.tasks[name].with_enabled(enabled)

    def list(self, prefix):
        return [value for name, value in self.tasks.items() if name.startswith(prefix)]


def test_upsert_uses_fixed_identity_safe_action_and_friday_trigger(tmp_path):
    adapter = Adapter()
    scheduler = WindowsAuditScheduler(adapter)
    plan = _plan()
    state = scheduler.upsert(plan, tmp_path / "SmartTest.exe")
    definition = adapter.upserts[0]
    assert state.task_name == TASK_PREFIX + "plan-a"
    assert definition.executable == (tmp_path / "SmartTest.exe").resolve()
    assert definition.arguments == ("--project-weekly-audit-plan", "plan-a")
    assert definition.weekday == 4
    assert (definition.hour, definition.minute) == (0, 5)
    serialized = repr(definition)
    assert "cred-plan-a" not in serialized
    assert "https://c/projects" not in serialized


def test_source_launch_command_runs_main_script_before_plan_switch(tmp_path):
    import os
    import subprocess
    import sys

    command = resolve_audit_launch_command(
        executable=Path(sys.executable), packaged=False,
    )
    assert command.arguments[:1] == (
        str(Path(__file__).resolve().parents[3] / "main.py"),
    )
    environment = dict(os.environ)
    environment["LOCALAPPDATA"] = str(tmp_path)
    completed = subprocess.run(
        [str(command.executable), *command.for_plan("missing-plan")],
        cwd=Path(__file__).resolve().parents[3],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 2


def test_packaged_launch_command_uses_executable_entrypoint(tmp_path):
    executable = tmp_path / "SmartTest.exe"
    command = resolve_audit_launch_command(executable=executable, packaged=True)
    assert command.executable == executable.resolve()
    assert command.for_plan("plan-a") == (BACKGROUND_SWITCH, "plan-a")


def test_windows_arguments_use_standard_argv_serialization_for_spaces_and_quotes():
    arguments = (
        r"C:\Smart Test Source\main.py",
        "--label",
        'say "hello"',
        BACKGROUND_SWITCH,
        "plan-a",
    )
    assert _serialize_arguments(arguments) == subprocess.list2cmdline(arguments)
    assert '"C:\\Smart Test Source\\main.py"' in _serialize_arguments(arguments)
    assert r'\"hello\"' in _serialize_arguments(arguments)


def test_native_upsert_writes_standard_serialized_arguments(tmp_path):
    class Box:
        pass

    class Factory:
        def __init__(self, value):
            self.value = value

        def Create(self, kind):
            return self.value

    action, trigger = Box(), Box()
    task = Box()
    task.RegistrationInfo, task.Settings = Box(), Box()
    task.Actions, task.Triggers = Factory(action), Factory(trigger)

    class Service:
        def NewTask(self, flags):
            return task

    class Folder:
        def RegisterTaskDefinition(self, *args):
            self.registered = args

    adapter = _TaskSchedulerComAdapter.__new__(_TaskSchedulerComAdapter)
    adapter._service, adapter._folder = Service(), Folder()
    arguments = (
        str(tmp_path / "Smart Test Source" / "main.py"),
        BACKGROUND_SWITCH,
        "plan-a",
    )
    definition = TaskDefinition(
        TASK_PREFIX + "plan-a", Path(sys.executable), arguments,
    )

    adapter.upsert(definition)

    assert action.Arguments == subprocess.list2cmdline(arguments)


def test_repeated_upsert_updates_one_task_and_stop_enable_reuse_it(tmp_path):
    adapter = Adapter()
    scheduler = WindowsAuditScheduler(adapter)
    scheduler.upsert(_plan(), tmp_path / "SmartTest.exe")
    scheduler.upsert(_plan(), tmp_path / "SmartTest-v2.exe")
    assert list(adapter.tasks) == [TASK_PREFIX + "plan-a"]
    stopped = scheduler.set_enabled("plan-a", False)
    assert stopped.registered and not stopped.enabled
    resumed = scheduler.set_enabled("plan-a", True)
    assert resumed.registered and resumed.enabled
    assert list(adapter.tasks) == [TASK_PREFIX + "plan-a"]


def test_disabled_upsert_then_enable_turns_on_task_and_trigger(tmp_path):
    adapter = Adapter()
    scheduler = WindowsAuditScheduler(adapter)
    created = scheduler.upsert(_plan(enabled=False), tmp_path / "SmartTest.exe")
    assert not created.enabled
    assert not adapter.tasks[created.task_name].trigger_enabled
    enabled = scheduler.set_enabled("plan-a", True)
    definition = adapter.tasks[enabled.task_name]
    assert enabled.enabled
    assert definition.enabled and definition.trigger_enabled


def test_preexisting_disabled_task_enable_turns_on_task_and_trigger(tmp_path):
    adapter = Adapter()
    name = TASK_PREFIX + "plan-a"
    adapter.tasks[name] = TaskDefinition(
        name, (tmp_path / "SmartTest.exe").resolve(),
        (BACKGROUND_SWITCH, "plan-a"),
        enabled=False, trigger_enabled=False,
    )
    state = WindowsAuditScheduler(adapter).set_enabled("plan-a", True)
    assert state.enabled
    assert adapter.tasks[name].enabled
    assert adapter.tasks[name].trigger_enabled


def test_list_reconciles_owned_tasks_and_ignores_unrelated(tmp_path):
    adapter = Adapter()
    scheduler = WindowsAuditScheduler(adapter)
    scheduler.upsert(_plan("ok"), tmp_path / "SmartTest.exe")
    scheduler.upsert(_plan("invalid"), tmp_path / "SmartTest.exe")
    adapter.tasks[TASK_PREFIX + "invalid"] = adapter.tasks[
        TASK_PREFIX + "invalid"
    ].with_arguments(("--wrong", "invalid"))
    scheduler.upsert(_plan("orphan"), tmp_path / "SmartTest.exe")
    adapter.tasks["Other.Application.Task"] = adapter.tasks[TASK_PREFIX + "ok"]
    states = scheduler.list([_plan("ok"), _plan("invalid"), _plan("missing")])
    assert {row.plan_id: row.reconciliation for row in states} == {
        "invalid": "invalid_task",
        "missing": "task_missing",
        "ok": "ok",
        "orphan": "config_missing",
    }


def test_list_marks_missing_or_extra_action_and_trigger_invalid(tmp_path):
    from dataclasses import replace

    adapter = Adapter()
    scheduler = WindowsAuditScheduler(adapter)
    mutations = {
        "no-action": {"action_count": 0},
        "extra-action": {"action_count": 2},
        "no-trigger": {"trigger_count": 0},
        "extra-trigger": {"trigger_count": 2},
    }
    for plan_id, changes in mutations.items():
        scheduler.upsert(_plan(plan_id), tmp_path / "SmartTest.exe")
        name = TASK_PREFIX + plan_id
        adapter.tasks[name] = replace(adapter.tasks[name], **changes)
    states = scheduler.list([_plan(plan_id) for plan_id in mutations])
    assert {row.plan_id: row.reconciliation for row in states} == {
        plan_id: "invalid_task" for plan_id in mutations
    }


def test_list_marks_wrong_executable_invalid(tmp_path):
    from dataclasses import replace

    adapter = Adapter()
    scheduler = WindowsAuditScheduler(adapter)
    scheduler.upsert(_plan(), tmp_path / "SmartTest.exe")
    name = TASK_PREFIX + "plan-a"
    adapter.tasks[name] = replace(
        adapter.tasks[name], executable=tmp_path / "Other.exe",
    )

    assert scheduler.list([_plan()])[0].reconciliation == "invalid_task"


class ComCollection:
    def __init__(self, *items):
        self.items = items
        self.Count = len(items)

    def Item(self, index):
        return self.items[index - 1]


class ComAction:
    Type = 0
    Path = r"C:\SmartTest\SmartTest.exe"
    Arguments = "--project-weekly-audit-plan plan-a"


class ComTrigger:
    Type = 3
    DaysOfWeek = 32
    StartBoundary = "2026-07-31T00:05:00+08:00"
    Enabled = True


class ComTask:
    Name = TASK_PREFIX + "plan-a"
    Enabled = True
    NextRunTime = None
    LastRunTime = None
    LastTaskResult = 0

    def __init__(self, action=None, trigger=None):
        self.Definition = type("Definition", (), {
            "Actions": ComCollection(action or ComAction()),
            "Triggers": ComCollection(trigger or ComTrigger()),
        })()


class ComFolder:
    def __init__(self, tasks):
        self.tasks = tasks

    def GetTasks(self, flags):
        return self.tasks


def _native_scheduler(task):
    adapter = _TaskSchedulerComAdapter.__new__(_TaskSchedulerComAdapter)
    adapter._folder = ComFolder([task])
    return WindowsAuditScheduler(adapter)


def test_native_readback_reconciles_quoted_source_main_path(tmp_path):
    main_script = tmp_path / "Smart Test Source" / "main.py"
    launch = AuditLaunchCommand(Path(sys.executable).resolve(), (str(main_script),))
    action = ComAction()
    action.Path = str(launch.executable)
    action.Arguments = subprocess.list2cmdline(launch.for_plan("plan-a"))
    adapter = _TaskSchedulerComAdapter.__new__(_TaskSchedulerComAdapter)
    adapter._folder = ComFolder([ComTask(action=action)])

    state = WindowsAuditScheduler(
        adapter, launch_command=launch,
    ).list([_plan()])[0]

    assert state.reconciliation == "ok"


def test_native_list_marks_non_exec_action_invalid():
    action = ComAction()
    action.Type = 5
    states = _native_scheduler(ComTask(action=action)).list([_plan()])
    assert states[0].reconciliation == "invalid_task"


def test_native_list_marks_non_weekly_trigger_invalid():
    trigger = ComTrigger()
    trigger.Type = 2
    states = _native_scheduler(ComTask(trigger=trigger)).list([_plan()])
    assert states[0].reconciliation == "invalid_task"


def test_native_list_marks_malformed_start_boundary_invalid_without_escaping():
    trigger = ComTrigger()
    trigger.StartBoundary = "not-a-date"
    states = _native_scheduler(ComTask(trigger=trigger)).list([_plan()])
    assert states[0].reconciliation == "invalid_task"
