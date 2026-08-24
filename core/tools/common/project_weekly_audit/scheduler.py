"""Map Project Weekly Audit plans to the common scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Literal, Sequence

from support.scheduling import (
    LaunchCommand,
    ScheduleDefinition,
    WeeklyTrigger,
    WindowsTaskScheduler,
    resolve_launch_command,
)

from .plans import AuditPlan


TASK_PREFIX = "SmartTest.ProjectWeeklyAudit."
BACKGROUND_SWITCH = "--project-weekly-audit-plan"
TASK_DESCRIPTION = "SmartTest Project Weekly Audit"
WEEKLY_TRIGGER = WeeklyTrigger(4, 0, 5)


@dataclass(frozen=True)
class ScheduledPlanState:
    plan_id: str
    task_name: str
    enabled: bool
    registered: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_result_code: int | None
    reconciliation: Literal[
        "ok", "config_missing", "task_missing", "invalid_task"
    ]


def resolve_audit_launch_command(
    *,
    executable: Path | None = None,
    packaged: bool | None = None,
    main_script: Path | None = None,
) -> LaunchCommand:
    return resolve_launch_command(
        executable=executable,
        packaged=packaged,
        main_script=main_script,
    )


class WindowsAuditScheduler:
    def __init__(self, native=None, launch_command: LaunchCommand | None = None):
        self._scheduler = WindowsTaskScheduler(native)
        self._launch_command = launch_command or resolve_audit_launch_command()

    def upsert(
        self, plan: AuditPlan, executable: Path | None = None
    ) -> ScheduledPlanState:
        if executable is not None:
            self._launch_command = resolve_audit_launch_command(
                executable=executable,
                packaged=Path(executable).suffix.casefold() == ".exe",
            )
        definition = _definition(plan, self._launch_command)
        return _plan_state(self._scheduler.upsert(definition))

    def set_enabled(self, plan_id: str, enabled: bool) -> ScheduledPlanState:
        value = _plan_id(plan_id)
        return _plan_state(
            self._scheduler.set_enabled(TASK_PREFIX + value, enabled)
        )

    def list(self, plans: Sequence[AuditPlan]) -> list[ScheduledPlanState]:
        definitions = [_definition(plan, self._launch_command) for plan in plans]
        return [
            _plan_state(state)
            for state in self._scheduler.list(TASK_PREFIX, definitions)
        ]


def _definition(plan: AuditPlan, launch: LaunchCommand) -> ScheduleDefinition:
    plan_id = _plan_id(plan.plan_id)
    return ScheduleDefinition(
        task_id=TASK_PREFIX + plan_id,
        description=TASK_DESCRIPTION,
        launch=launch.for_arguments(BACKGROUND_SWITCH, plan_id),
        trigger=WEEKLY_TRIGGER,
        enabled=bool(plan.enabled),
    )


def _plan_state(state) -> ScheduledPlanState:
    task_name = state.task_id
    return ScheduledPlanState(
        plan_id=task_name[len(TASK_PREFIX):],
        task_name=task_name,
        enabled=state.enabled,
        registered=state.registered,
        next_run_at=state.next_run_at,
        last_run_at=state.last_run_at,
        last_result_code=state.last_result_code,
        reconciliation=state.reconciliation,
    )


def _plan_id(value) -> str:
    text = str(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise ValueError("Invalid audit plan id")
    return text
