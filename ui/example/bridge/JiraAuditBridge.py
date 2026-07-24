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


class JiraAuditBridge(QObject):
    stateChanged = Signal()
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
        self._auth_bridge = auth_bridge
        self._base_url = str(base_url or "").rstrip("/")
        self._client_factory = client_factory
        self._service_factory = service_factory or (
            lambda client, base_url: JiraAuditService(client, base_url=base_url)
        )
        self._export_function = export_function
        self._thread_factory = thread_factory
        self._generation = 0
        self._state = "idle"
        self._status_text = self.tr("Ready to review Jira issues.")
        self._input_error = ""
        self._processed_count = 0
        self._total_count = 0
        self._progress_value = 0.0
        self._report: AuditReport | None = None
        self._export_path = ""
        self._rule_rows = [asdict(rule) for rule in active_rules()]
        self._result_summary: dict[str, int] = {}
        self._violation_rows: list[dict[str, Any]] = []
        self._workerProgress.connect(self._on_worker_progress)
        self._workerFinished.connect(self._on_worker_finished)
        self._workerFailed.connect(self._on_worker_failed)
        if hasattr(auth_bridge, "authChanged"):
            auth_bridge.authChanged.connect(self._on_auth_changed)

    @Slot(str)
    def startAudit(self, text: str) -> None:
        clean_text = str(text or "").strip()
        if not clean_text:
            self._input_error = self.tr("Enter JQL or a Jira URL.")
            self.stateChanged.emit()
            return
        if not self.canStart:
            return

        username = str(self._auth_bridge.currentUsername() or "").strip()
        credential_username, password = self._auth_bridge.transientCredential()
        username = str(credential_username or username).strip()
        if (
            not self._auth_bridge.isAuthenticated()
            or not self._auth_bridge.hasCredential()
            or not username
            or not password
        ):
            self._state = "failed"
            self._input_error = ""
            self._status_text = self.tr("Sign in with LDAP again to review Jira issues.")
            self.stateChanged.emit()
            return

        self._generation += 1
        generation = self._generation
        self._state = "resolving"
        self._status_text = self.tr("Validating Jira input...")
        self._input_error = ""
        self._processed_count = 0
        self._total_count = 0
        self._progress_value = 0.0
        self._report = None
        self._export_path = ""
        self._result_summary = {}
        self._violation_rows = []
        self.stateChanged.emit()
        worker = self._thread_factory(
            target=self._run_audit,
            args=(generation, clean_text, username, str(password)),
            daemon=True,
        )
        worker.start()

    def _run_audit(self, generation: int, text: str, username: str, password: str) -> None:
        try:
            client = self._client_factory(
                JiraClientConfig(base_url=self._base_url),
                JiraBasicAuth(username=username, password=password),
            )
            resolved = resolve_audit_input(
                text,
                base_url=self._base_url,
                client=client,
            )
            service = self._service_factory(client, self._base_url)
            report = service.run(
                resolved,
                lambda stage, processed, total: self._workerProgress.emit(
                    {
                        "generation": generation,
                        "stage": stage,
                        "processed": processed,
                        "total": total,
                    }
                ),
            )
            self._workerFinished.emit({"generation": generation, "report": report})
        except Exception as exc:
            smart_log(
                "Jira format audit failed: %s",
                exc,
                level="error",
                domain="jira",
                source="JiraAuditBridge",
            )
            self._workerFailed.emit(
                {
                    "generation": generation,
                    "message": str(exc)[:400],
                }
            )

    @Slot()
    def exportReport(self) -> None:
        if not self.canExport or self._report is None:
            self._input_error = self.tr("Complete a Jira audit before exporting.")
            self.stateChanged.emit()
            return
        try:
            location = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
            downloads_dir = Path(location) if location else Path.home() / "Downloads"
            path = Path(
                self._export_function(
                    self._report,
                    downloads_dir=downloads_dir,
                )
            ).resolve()
        except Exception as exc:
            smart_log(
                "Jira audit export failed: %s",
                exc,
                level="error",
                domain="jira",
                source="JiraAuditBridge",
            )
            self._input_error = self.tr("Failed to export the Jira audit workbook.")
            self.stateChanged.emit()
            return
        self._export_path = str(path)
        self._input_error = ""
        self._status_text = self.tr("Jira audit workbook exported.")
        self.stateChanged.emit()

    @Slot(object)
    def _on_worker_progress(self, payload: dict[str, Any]) -> None:
        if int(payload.get("generation", -1)) != self._generation:
            return
        stage = str(payload.get("stage", "") or "")
        processed = max(0, int(payload.get("processed", 0) or 0))
        total = max(0, int(payload.get("total", 0) or 0))
        self._state = stage if stage in {"fetching", "auditing"} else self._state
        self._processed_count = processed
        self._total_count = total
        self._progress_value = min(1.0, processed / total) if total else 0.0
        self._status_text = (
            self.tr("Fetching Jira issues...")
            if self._state == "fetching"
            else self.tr("Reviewing Jira issue formats...")
        )
        self.stateChanged.emit()

    @Slot(object)
    def _on_worker_finished(self, payload: dict[str, Any]) -> None:
        if int(payload.get("generation", -1)) != self._generation:
            return
        report = payload.get("report")
        if not isinstance(report, AuditReport):
            self._on_worker_failed(
                {
                    "generation": self._generation,
                    "message": self.tr("The Jira audit returned an invalid result."),
                }
            )
            return
        self._report = report
        self._result_summary = {
            "totalCount": report.total_count,
            "passedCount": report.passed_count,
            "failedCount": report.failed_count,
            "violationCount": report.violation_count,
        }
        self._violation_rows = [
            dict(asdict(violation), key=issue.key, url=issue.url)
            for issue in report.issues
            for violation in issue.violations
        ]
        self._state = "completed"
        self._processed_count = max(self._processed_count, report.total_count)
        self._total_count = max(self._total_count, report.total_count)
        self._progress_value = 1.0
        self._status_text = self.tr("Jira format audit completed.")
        self._input_error = ""
        self.stateChanged.emit()

    @Slot(object)
    def _on_worker_failed(self, payload: dict[str, Any]) -> None:
        if int(payload.get("generation", -1)) != self._generation:
            return
        self._state = "failed"
        message = str(payload.get("message", "") or "Jira audit failed.")
        self._status_text = self.tr(message)
        self._input_error = self._status_text
        self.stateChanged.emit()

    @Slot()
    def _on_auth_changed(self) -> None:
        if self._state in {"resolving", "fetching", "auditing"}:
            self._generation += 1
            self._state = "failed"
            self._status_text = self.tr("The login changed. Start the Jira audit again.")
            self.stateChanged.emit()

    state = Property(str, lambda self: self._state, notify=stateChanged)
    statusText = Property(str, lambda self: self._status_text, notify=stateChanged)
    inputError = Property(str, lambda self: self._input_error, notify=stateChanged)
    progressValue = Property(float, lambda self: self._progress_value, notify=stateChanged)
    processedCount = Property(int, lambda self: self._processed_count, notify=stateChanged)
    totalCount = Property(int, lambda self: self._total_count, notify=stateChanged)
    ruleRows = Property("QVariantList", lambda self: self._rule_rows, notify=stateChanged)
    resultSummary = Property(
        "QVariantMap",
        lambda self: self._result_summary,
        notify=stateChanged,
    )
    violationRows = Property(
        "QVariantList",
        lambda self: self._violation_rows,
        notify=stateChanged,
    )
    exportPath = Property(str, lambda self: self._export_path, notify=stateChanged)
    canStart = Property(
        bool,
        lambda self: self._state not in {"resolving", "fetching", "auditing"},
        notify=stateChanged,
    )
    canExport = Property(
        bool,
        lambda self: self._state == "completed" and self._report is not None,
        notify=stateChanged,
    )
