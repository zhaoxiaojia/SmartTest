"""Unattended Daily Report batch entrypoint."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
import time

from support.jira_integration.auth.basic import JiraBasicAuth
from support.jira_integration.services.issue_service import JiraIssueService
from support.jira_integration.transport.client import JiraClient, JiraClientConfig
from core.logging import smart_log
from support.windows_credentials import WindowsCredentialStore

from .projects import ProjectConfigStore
from .delivery import DeliveryModeStore
from .schedule import DailyReportScheduleManager
from .service import DailyReportService


CREDENTIAL_REF = "daily-report-batch"


def run_scheduled_batch(
    *, credentials=None, service=None, schedule=None, data_root=None,
    now=None, wait=None, logger=None, immediate=False,
) -> int:
    root = Path(data_root or _data_root()) / "daily_report"
    now = now or datetime.now
    wait = wait or time.sleep
    logger = logger or smart_log
    def lifecycle(message, stage, *, level="info", **extra):
        logger(
            message, domain="tool", source="daily_report", level=level,
            extra={"stage": stage, **extra},
        )
    def finish(exit_code):
        lifecycle(
            "Daily Report scheduled task exited", "exit", exit_code=exit_code
        )
        return exit_code

    lifecycle("Daily Report scheduled task entered", "entry")
    credentials = credentials or WindowsCredentialStore(
        target_prefix="SmartTest/DailyReport/"
    )
    schedule = schedule or DailyReportScheduleManager(root / "schedule.json")
    if service is None:
        base_url = os.getenv(
            "SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com"
        )
        def issue_factory(username, password):
            return JiraIssueService(JiraClient(
                JiraClientConfig(base_url=base_url),
                JiraBasicAuth(username=username, password=password),
            ))
        service = DailyReportService(
            issue_service_factory=issue_factory,
            project_store=ProjectConfigStore(root / "projects.json"),
            delivery_mode=DeliveryModeStore(root / "delivery.json"),
            report_root=root / "reports", jira_base_url=base_url,
        )
    stage = "schedule_load"
    try:
        configured = schedule.load()
        if configured is None or (not configured.enabled and not immediate):
            return finish(1)
        lifecycle(
            "Daily Report schedule loaded", stage,
            cadence=configured.cadence,
            send_time=f"{configured.hour:02d}:{configured.minute:02d}",
            enabled=bool(configured.enabled),
        )
        send_deadline = _next_send_deadline(configured, now())
        lifecycle(
            "Daily Report send deadline resolved", "deadline",
            send_deadline=send_deadline.isoformat(),
        )
        stage = "credential_read"
        username, password = credentials.read(CREDENTIAL_REF)
        lifecycle("Daily Report credential read succeeded", stage)
        stage = "preparation"
        lifecycle("Daily Report fresh preparation started", stage)
        batch = service.preview(username, password)
        lifecycle(
            "Daily Report fresh preparation completed", stage,
            report_count=len(batch.reports), failure_count=len(batch.failures),
        )
        if batch.failures or not batch.reports:
            return finish(1)
        if not immediate:
            stage = "wait"
            lifecycle(
                "Daily Report deadline wait started", stage,
                remaining_seconds=max(
                    0, round((send_deadline - now()).total_seconds())
                ),
            )
            _wait_until(
                send_deadline, now, wait,
                heartbeat=lambda remaining: lifecycle(
                    "Daily Report deadline wait heartbeat", stage,
                    remaining_seconds=round(remaining),
                ),
            )
            lifecycle("Daily Report deadline wait completed", stage)
        stage = "send"
        lifecycle("Daily Report scheduled send started", stage)
        results = service.send_preview(batch)
        statuses = {}
        for result in results:
            statuses[result.status] = statuses.get(result.status, 0) + 1
        sent_count = statuses.get("sent", 0)
        lifecycle(
            "Daily Report scheduled send completed", stage,
            result_count=len(results), sent_count=sent_count,
            failure_count=len(results) - sent_count, statuses=statuses,
        )
    except Exception as exc:
        if stage == "credential_read":
            lifecycle(
                "Daily Report credential read failed", stage, level="error",
                error_type=type(exc).__name__,
            )
        lifecycle(
            "Daily Report scheduled task failed", stage, level="error",
            error_type=type(exc).__name__,
        )
        return finish(1)
    exit_code = int(
        bool(batch.failures)
        or not results
        or any(result.status != "sent" for result in results)
    )
    return finish(exit_code)


def _next_send_deadline(schedule, current: datetime) -> datetime:
    candidate = current.replace(
        hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0
    )
    if schedule.cadence == "daily":
        return candidate if candidate >= current else candidate + timedelta(days=1)
    days = (int(schedule.weekday) - current.weekday()) % 7
    candidate += timedelta(days=days)
    return candidate if candidate >= current else candidate + timedelta(days=7)


def _wait_until(deadline: datetime, now, wait, heartbeat=None) -> None:
    while True:
        remaining = (deadline - now()).total_seconds()
        if remaining <= 0:
            return
        wait(min(remaining, 60.0))
        remaining = (deadline - now()).total_seconds()
        if remaining > 0 and heartbeat is not None:
            heartbeat(remaining)


def _data_root() -> Path:
    local = os.getenv("LOCALAPPDATA")
    return (
        Path(local) / "Amlogic" / "SmartTest"
        if local else Path.home() / ".smarttest"
    )
