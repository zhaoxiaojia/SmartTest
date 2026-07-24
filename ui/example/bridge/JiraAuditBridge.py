from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from threading import Thread
from typing import Any, Callable

from PySide6.QtCore import QObject, Property, QStandardPaths, Signal, Slot

from support.jira_integration.audit import (
    AuditReport,
    JiraAuditService,
    active_rules,
    export_audit_xlsx,
    resolve_audit_input,
)
from support.jira_integration.auth.basic import JiraBasicAuth
from support.jira_integration.transport.client import JiraClient, JiraClientConfig
from support.logging import smart_log


JIRA_BASE_URL = os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
_BUSY_STATES = {"resolving", "fetching", "auditing"}


class JiraAuditBridge(QObject):
    viewStateChanged = Signal()
    _workerProgress = Signal(object)
    _workerFinished = Signal(object)
    _workerFailed = Signal(object)

    def __init__(
        self,
        auth_bridge: QObject,
        *,
        base_url: str = JIRA_BASE_URL,
        client_factory: Callable[..., Any] = JiraClient,
        service_factory: Callable[..., Any] | None = None,
        export_function: Callable[..., Path] = export_audit_xlsx,
        thread_factory: Callable[..., Thread] = Thread,
    ):
        super().__init__(auth_bridge)
        self._auth = auth_bridge
        self._base_url = str(base_url or "").rstrip("/")
        self._client_factory = client_factory
        self._service_factory = service_factory or JiraAuditService
        self._export_function = export_function
        self._thread_factory = thread_factory
        self._generation = 0
        self._report: AuditReport | None = None
        self._view = {
            "state": "idle",
            "statusText": self.tr("Ready to review Jira issues."),
            "inputError": "",
            "progressValue": 0.0,
            "processedCount": 0,
            "totalCount": 0,
            "ruleRows": [asdict(rule) for rule in active_rules()],
            "resultSummary": {},
            "violationRows": [],
            "exportPath": "",
            "canStart": True,
            "canExport": False,
        }
        self._workerProgress.connect(self._on_worker_progress)
        self._workerFinished.connect(self._on_worker_finished)
        self._workerFailed.connect(self._on_worker_failed)
        if hasattr(self._auth, "authChanged"):
            self._auth.authChanged.connect(self._on_auth_changed)

    @Slot(str)
    def startAudit(self, text: str) -> None:
        clean_text = str(text or "").strip()
        if not clean_text:
            self._set(inputError=self.tr("Enter JQL or a Jira URL."))
            return
        if not self._view["canStart"]:
            return
        username = str(self._auth.currentUsername() or "").strip()
        credential_username, password = self._auth.transientCredential()
        username = str(credential_username or username).strip()
        if not (
            self._auth.isAuthenticated()
            and self._auth.hasCredential()
            and username
            and password
        ):
            self._set(
                state="failed",
                inputError="",
                statusText=self.tr("Sign in with LDAP again to review Jira issues."),
            )
            return
        self._generation += 1
        generation = self._generation
        self._report = None
        self._set(
            state="resolving",
            statusText=self.tr("Validating Jira input..."),
            inputError="",
            processedCount=0,
            totalCount=0,
            progressValue=0.0,
            resultSummary={},
            violationRows=[],
            exportPath="",
        )
        args = (generation, clean_text, username, str(password))
        self._thread_factory(target=self._run_audit, args=args, daemon=True).start()

    def _run_audit(self, generation, text, username, password) -> None:
        try:
            client = self._client_factory(
                JiraClientConfig(base_url=self._base_url),
                JiraBasicAuth(username=username, password=password),
            )
            resolved = resolve_audit_input(text, base_url=self._base_url, client=client)
            report = self._service_factory(client, base_url=self._base_url).run(
                resolved,
                lambda stage, processed, total: self._workerProgress.emit(
                    (generation, stage, processed, total)
                ),
            )
            self._workerFinished.emit({"generation": generation, "report": report})
        except Exception as exc:
            smart_log("Jira format audit failed: %s", exc, level="error",
                      domain="jira", source="JiraAuditBridge")
            self._workerFailed.emit({"generation": generation, "message": str(exc)[:400]})
    @Slot()
    def exportReport(self) -> None:
        if not self._view["canExport"] or self._report is None:
            self._set(inputError=self.tr("Complete a Jira audit before exporting."))
            return
        try:
            location = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
            downloads_dir = Path(location) if location else Path.home() / "Downloads"
            path = Path(
                self._export_function(self._report, downloads_dir=downloads_dir)
            ).resolve()
        except Exception as exc:
            smart_log("Jira audit export failed: %s", exc, level="error",
                      domain="jira", source="JiraAuditBridge")
            self._set(inputError=self.tr("Failed to export the Jira audit workbook."))
            return
        self._set(
            exportPath=str(path),
            inputError="",
            statusText=self.tr("Jira audit workbook exported."),
        )
    @Slot(object)
    def _on_worker_progress(self, payload) -> None:
        generation, stage, processed, total = payload
        if int(generation) != self._generation:
            return
        stage = str(stage or "")
        processed, total = max(0, int(processed or 0)), max(0, int(total or 0))
        state = stage if stage in {"fetching", "auditing"} else self._view["state"]
        self._set(
            state=state,
            processedCount=processed,
            totalCount=total,
            progressValue=min(1.0, processed / total) if total else 0.0,
            statusText=(
                self.tr("Fetching Jira issues...")
                if state == "fetching"
                else self.tr("Reviewing Jira issue formats...")
            ),
        )
    @Slot(object)
    def _on_worker_finished(self, payload: dict[str, Any]) -> None:
        if int(payload.get("generation", -1)) != self._generation:
            return
        report = payload.get("report")
        if not isinstance(report, AuditReport):
            self._on_worker_failed(
                {"generation": self._generation,
                 "message": self.tr("The Jira audit returned an invalid result.")}
            )
            return
        self._report = report
        self._set(
            state="completed",
            processedCount=max(self._view["processedCount"], report.total_count),
            totalCount=max(self._view["totalCount"], report.total_count),
            progressValue=1.0,
            statusText=self.tr("Jira format audit completed."),
            inputError="",
            resultSummary={
                "totalCount": report.total_count,
                "passedCount": report.passed_count,
                "failedCount": report.failed_count,
                "violationCount": report.violation_count,
            },
            violationRows=[
                dict(asdict(violation), key=issue.key, url=issue.url)
                for issue in report.issues
                for violation in issue.violations
            ],
        )
    @Slot(object)
    def _on_worker_failed(self, payload: dict[str, Any]) -> None:
        if int(payload.get("generation", -1)) != self._generation:
            return
        message = self.tr(str(payload.get("message", "") or "Jira audit failed."))
        self._set(state="failed", statusText=message, inputError=message)
    @Slot()
    def _on_auth_changed(self) -> None:
        if self._view["state"] in _BUSY_STATES:
            self._generation += 1
            self._set(
                state="failed",
                statusText=self.tr("The login changed. Start the Jira audit again."),
            )
    def _set(self, **changes) -> None:
        state = str(changes.get("state", self._view["state"]))
        self._view = {
            **self._view,
            **changes,
            "canStart": state not in _BUSY_STATES,
            "canExport": state == "completed" and self._report is not None,
        }
        self.viewStateChanged.emit()
    viewState = Property("QVariantMap", lambda self: self._view, notify=viewStateChanged)
