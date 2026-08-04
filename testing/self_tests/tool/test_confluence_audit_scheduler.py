from dataclasses import replace
from datetime import datetime
import importlib
import importlib.util
from pathlib import Path
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

import pytest

from support.scheduling import DailyTrigger, LaunchCommand, RegisteredTask
from tool.common.project_weekly_audit.models import ProjectCollectionFilter
from tool.common.project_weekly_audit.plans import AuditPlan
from tool.common.project_weekly_audit.scheduler import (
    BACKGROUND_SWITCH,
    TASK_PREFIX,
    WEEKLY_TRIGGER,
    WindowsAuditScheduler,
    resolve_audit_launch_command,
)


TZ = ZoneInfo("Asia/Shanghai")


def _plan(plan_id="plan-a", enabled=True):
    now = datetime(2026, 7, 29, tzinfo=TZ)
    return AuditPlan(
        plan_id,
        "Weekly",
        ProjectCollectionFilter("https://c/projects", (2026,)),
        enabled,
        f"cred-{plan_id}",
        "ignored-config-task-name",
        now,
        now,
    )


class Adapter:
    def __init__(self):
        self.tasks = {}
        self.upserts = []

    def upsert(self, definition):
        self.upserts.append(definition)
        self.tasks[definition.task_id] = RegisteredTask.from_definition(definition)

    def set_enabled(self, task_id, enabled):
        self.tasks[task_id] = replace(
            self.tasks[task_id], enabled=enabled, trigger_enabled=enabled
        )

    def list(self, prefix):
        return [task for task_id, task in self.tasks.items() if task_id.startswith(prefix)]


def test_project_weekly_audit_owns_business_but_not_task_com():
    owner = importlib.import_module("tool.common.project_weekly_audit")
    scheduler = importlib.import_module("tool.common.project_weekly_audit.scheduler")
    assert owner.ConfluenceAuditService.__module__.startswith(
        "tool.common.project_weekly_audit"
    )
    assert not hasattr(scheduler, "_TaskSchedulerComAdapter")
    assert importlib.util.find_spec("support." + "confluence_audit") is None


def test_upsert_preserves_identity_action_and_friday_trigger(tmp_path):
    adapter = Adapter()
    state = WindowsAuditScheduler(adapter).upsert(
        _plan(), tmp_path / "SmartTest.exe"
    )
    definition = adapter.upserts[0]
    assert state.task_name == TASK_PREFIX + "plan-a"
    assert definition.launch.executable == (tmp_path / "SmartTest.exe").resolve()
    assert definition.launch.arguments == (BACKGROUND_SWITCH, "plan-a")
    assert definition.trigger == WEEKLY_TRIGGER
    assert (definition.trigger.weekday, definition.trigger.hour, definition.trigger.minute) == (4, 0, 5)
    serialized = repr(definition)
    assert "cred-plan-a" not in serialized
    assert "https://c/projects" not in serialized


def test_source_launch_runs_main_before_background_switch(tmp_path):
    command = resolve_audit_launch_command(
        executable=Path(sys.executable), packaged=False
    )
    assert command.arguments[:1] == (
        str(Path(__file__).resolve().parents[3] / "main.py"),
    )
    environment = dict(os.environ)
    environment["LOCALAPPDATA"] = str(tmp_path)
    completed = subprocess.run(
        [
            str(command.executable),
            *command.for_arguments(BACKGROUND_SWITCH, "missing-plan").arguments,
        ],
        cwd=Path(__file__).resolve().parents[3],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 2


def test_packaged_launch_uses_executable_entrypoint(tmp_path):
    executable = tmp_path / "SmartTest.exe"
    command = resolve_audit_launch_command(executable=executable, packaged=True)
    assert command.executable == executable.resolve()
    assert command.for_arguments(BACKGROUND_SWITCH, "plan-a").arguments == (
        BACKGROUND_SWITCH,
        "plan-a",
    )


def test_repeated_upsert_and_enable_reuse_one_task(tmp_path):
    adapter = Adapter()
    scheduler = WindowsAuditScheduler(adapter)
    scheduler.upsert(_plan(), tmp_path / "SmartTest.exe")
    scheduler.upsert(_plan(), tmp_path / "SmartTest-v2.exe")
    assert list(adapter.tasks) == [TASK_PREFIX + "plan-a"]
    assert not scheduler.set_enabled("plan-a", False).enabled
    assert scheduler.set_enabled("plan-a", True).enabled


def test_list_reconciles_owned_missing_invalid_and_orphan_tasks(tmp_path):
    adapter = Adapter()
    scheduler = WindowsAuditScheduler(adapter)
    for plan_id in ("ok", "invalid", "orphan"):
        scheduler.upsert(_plan(plan_id), tmp_path / "SmartTest.exe")
    invalid_id = TASK_PREFIX + "invalid"
    adapter.tasks[invalid_id] = replace(adapter.tasks[invalid_id], action_count=2)
    states = scheduler.list([_plan("ok"), _plan("invalid"), _plan("missing")])
    assert {state.plan_id: state.reconciliation for state in states} == {
        "invalid": "invalid_task",
        "missing": "task_missing",
        "ok": "ok",
        "orphan": "config_missing",
    }


def test_list_rejects_changed_launch_and_schedule(tmp_path):
    adapter = Adapter()
    scheduler = WindowsAuditScheduler(adapter)
    scheduler.upsert(_plan("launch"), tmp_path / "SmartTest.exe")
    scheduler.upsert(_plan("trigger"), tmp_path / "SmartTest.exe")
    launch_id = TASK_PREFIX + "launch"
    trigger_id = TASK_PREFIX + "trigger"
    adapter.tasks[launch_id] = replace(
        adapter.tasks[launch_id],
        launch=LaunchCommand(
            (tmp_path / "SmartTest.exe").resolve(), ("--wrong", "launch")
        ),
    )
    adapter.tasks[trigger_id] = replace(
        adapter.tasks[trigger_id], trigger=DailyTrigger(0, 5), trigger_type=2
    )

    assert {
        state.plan_id: state.reconciliation
        for state in scheduler.list([_plan("launch"), _plan("trigger")])
    } == {"launch": "invalid_task", "trigger": "invalid_task"}


def test_plan_id_rejects_task_name_injection():
    with pytest.raises(ValueError):
        WindowsAuditScheduler(Adapter()).upsert(_plan("bad name"))
