"""Unattended Daily Report batch entrypoint."""

from __future__ import annotations

import os
from pathlib import Path

from support.jira_integration.auth.basic import JiraBasicAuth
from support.jira_integration.services.issue_service import JiraIssueService
from support.jira_integration.transport.client import JiraClient, JiraClientConfig
from support.windows_credentials import WindowsCredentialStore

from .projects import ProjectConfigStore
from .service import DailyReportService


CREDENTIAL_REF = "daily-report-batch"


def run_scheduled_batch(*, credentials=None, service=None, data_root=None) -> int:
    root = Path(data_root or _data_root()) / "daily_report"
    credentials = credentials or WindowsCredentialStore(
        target_prefix="SmartTest/DailyReport/"
    )
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
            report_root=root / "reports", jira_base_url=base_url,
        )
    try:
        username, password = credentials.read(CREDENTIAL_REF)
        batch = service.preview(username, password)
        results = service.send_preview(batch)
    except Exception:
        return 1
    return int(
        bool(batch.failures)
        or not results
        or any(result.status != "sent" for result in results)
    )


def _data_root() -> Path:
    local = os.getenv("LOCALAPPDATA")
    return (
        Path(local) / "Amlogic" / "SmartTest"
        if local else Path.home() / ".smarttest"
    )
