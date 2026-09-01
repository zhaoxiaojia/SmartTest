"""Four-project Daily Report orchestration."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from datetime import date, timedelta
import os
from pathlib import Path
from typing import Callable
from uuid import uuid4

from core.logging import smart_log
from core.email.outlook import send_email
from core.email.personal_outlook import send_email as send_personal_email
from core.reporting import render_html_page_image

from .report import (
    DailyReportArtifacts,
    ProjectConfig,
    build_historical_jql,
    generate_artifacts,
    records_to_issues,
)


class DailyReportError(RuntimeError):
    """Base error for a four-project report operation."""


@dataclass(frozen=True)
class ProjectReport:
    project: ProjectConfig
    day: date
    artifacts: DailyReportArtifacts
    history_failures: tuple[date, ...] = ()


@dataclass(frozen=True)
class DailyReportBatch:
    reports: tuple[ProjectReport, ...]
    failures: tuple["ProjectFailure", ...] = ()


@dataclass(frozen=True)
class ProjectFailure:
    project: ProjectConfig
    status: str
    error_type: str


@dataclass(frozen=True)
class ProjectSendResult:
    project: ProjectConfig
    status: str
    error_type: str = ""


class DailyReportService:
    def __init__(
        self,
        *,
        issue_service_factory: Callable,
        project_store,
        report_root: str | Path,
        sender: Callable = send_email,
        personal_sender: Callable = send_personal_email,
        long_image_renderer: Callable = render_html_page_image,
        delivery_mode=None,
        today: Callable[[], date] = date.today,
        logger: Callable = smart_log,
        jira_base_url: str | None = None,
        manager=None,
    ):
        self._issue_service_factory = issue_service_factory
        self._project_store = project_store
        self._report_root = Path(report_root)
        self._sender = sender
        self._personal_sender = personal_sender
        self._long_image_renderer = long_image_renderer
        self._delivery_mode = delivery_mode
        self._today = today
        self._logger = logger
        self._manager = manager
        self._jira_base_url = (
            jira_base_url
            or os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
        ).rstrip("/")

    def preview(self, username: str, password: str) -> DailyReportBatch:
        day = self._today()
        projects = self._project_store.enabled()
        root = self._report_root / day.isoformat() / uuid4().hex
        jira = self._issue_service_factory(username, password)
        password = ""
        history_days = tuple(
            day - timedelta(days=offset) for offset in range(13, 0, -1)
        )
        self._log("Daily Report query started", project_count=len(projects))

        def current(project):
            return jira.search_records(project.jql)

        def historical(project, history_day):
            records = jira.search_records(
                build_historical_jql(history_day, project.label),
            )
            return frozenset(record.identity.key for record in records)

        def submit(label, work, *args):
            if self._manager is not None:
                return self._manager.submit(label, lambda _token, _progress: work(*args))
            future = Future()
            try: future.set_result(work(*args))
            except Exception as error: future.set_exception(error)
            return future

        current_futures = {
            project: submit(f"daily-report-current:{project.safe_id}", current, project) for project in projects
        }
        history_futures = {
            (project, history_day): submit(f"daily-report-history:{project.safe_id}", historical, project, history_day)
            for project in projects for history_day in history_days
        }

        reports, project_failures = [], []
        for project in projects:
            try:
                issues = records_to_issues(
                    current_futures[project].result(), self._jira_base_url
                )
            except Exception as exc:
                self._log_failure("query", project, exc)
                project_failures.append(
                    ProjectFailure(project, "query_failed", type(exc).__name__)
                )
                continue
            trend, failures, previous_keys = [], [], None
            for history_day in history_days:
                try:
                    keys = history_futures[(project, history_day)].result()
                    trend.append((history_day, len(keys)))
                    if history_day == day - timedelta(days=1):
                        previous_keys = keys
                except Exception as exc:
                    failures.append(history_day)
                    trend.append((history_day, None))
                    self._log_failure("history", project, exc)
            trend.append((day, len(issues)))
            self._log(
                "Daily Report history completed",
                project=project.safe_id,
                unavailable_count=len(failures),
            )
            try:
                artifacts = generate_artifacts(
                    issues,
                    tuple(trend),
                    root / project.safe_id,
                    day,
                    project=project,
                    previous_keys=previous_keys,
                )
            except Exception as exc:
                self._log_failure("build", project, exc)
                project_failures.append(
                    ProjectFailure(project, "build_failed", type(exc).__name__)
                )
                continue
            self._log(
                "Daily Report artifacts built",
                project=project.safe_id,
                issue_count=len(issues),
                history_unavailable_count=len(failures),
            )
            reports.append(
                ProjectReport(project, day, artifacts, tuple(failures))
            )
        return DailyReportBatch(tuple(reports), tuple(project_failures))

    def send_preview(
        self, batch: DailyReportBatch
    ) -> tuple[ProjectSendResult, ...]:
        results = []
        for report in batch.reports:
            project = report.project
            self._log("Daily Report send started", project=project.safe_id)
            try:
                subject = f"{project.subject} {report.day.isoformat()}"
                mode = self._delivery_mode.load() if self._delivery_mode else "public"
                if mode == "personal":
                    image_path = self._long_image_renderer(
                        report.artifacts.html_path,
                        report.artifacts.html_path.parent / "daily-report.png",
                    )
                    self._personal_sender(
                        subject=subject, image_path=image_path,
                        to=project.to, cc=project.cc,
                    )
                else:
                    self._sender(
                        subject=subject,
                        body=report.artifacts.html_path.read_text("utf-8"),
                        body_format="html", template=None,
                        to=project.to, cc=project.cc, attachments=(),
                        base_dir=report.artifacts.html_path.parent,
                    )
            except Exception as exc:
                self._log_failure("send", project, exc)
                results.append(
                    ProjectSendResult(project, "send_failed", type(exc).__name__)
                )
                continue
            self._log("Daily Report send accepted", project=project.safe_id)
            results.append(ProjectSendResult(project, "sent"))
        return tuple(results)

    def _log(self, message: str, **extra) -> None:
        self._logger(
            message,
            domain="tool",
            source="daily_report",
            extra=extra,
        )

    def _log_failure(
        self, phase: str, project: ProjectConfig, exc: BaseException
    ) -> None:
        self._logger(
            f"Daily Report {phase} failed",
            domain="tool",
            source="daily_report",
            level="error",
            extra={
                "project": project.safe_id,
                "error_type": type(exc).__name__,
            },
        )
