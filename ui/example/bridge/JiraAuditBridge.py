from __future__ import annotations

import os
import subprocess
from pathlib import Path
from threading import Thread
from typing import Any, Callable

from PySide6.QtCore import QObject, Property, Signal, Slot

from support.jira_integration.audit import AuditReport, active_rules
from support.jira_integration.audit.exporter import export_audit_xlsx
from support.jira_integration.audit.input_resolver import resolve_audit_input
from support.jira_integration.audit.service import JiraAuditService
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
        export_function: Callable[[AuditReport], Path] = export_audit_xlsx,
        process_launcher: Callable[..., Any] = subprocess.Popen,
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
        self._process_launcher = process_launcher
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
        if not self._can_start():
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
        if not self._can_export() or self._report is None:
            self._input_error = self.tr("Complete a Jira audit before exporting.")
            self.stateChanged.emit()
            return
        try:
            path = Path(self._export_function(self._report)).resolve()
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

    @Slot()
    def revealExport(self) -> None:
        path = Path(self._export_path) if self._export_path else None
        if path is None or not path.is_file():
            self._input_error = self.tr("The exported file does not exist.")
            self.stateChanged.emit()
            return
        try:
            self._process_launcher(
                ["explorer.exe", f"/select,{path.resolve()}"],
                shell=False,
            )
        except OSError:
            self._input_error = self.tr("Windows File Explorer could not be opened.")
            self.stateChanged.emit()
            return
        self._input_error = ""
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
        self._status_text = str(payload.get("message", "") or self.tr("Jira audit failed."))
        self._input_error = self._status_text
        self.stateChanged.emit()

    @Slot()
    def _on_auth_changed(self) -> None:
        if self._state in {"resolving", "fetching", "auditing"}:
            self._generation += 1
            self._state = "failed"
            self._status_text = self.tr("The login changed. Start the Jira audit again.")
            self.stateChanged.emit()

    def _rule_rows(self) -> list[dict[str, str]]:
        return [
            {
                "ruleId": rule.rule_id,
                "section": rule.section,
                "field": rule.field,
                "requirement": rule.requirement,
                "guidance": rule.guidance,
            }
            for rule in active_rules()
        ]

    def _result_summary(self) -> dict[str, int]:
        if self._report is None:
            return {}
        return {
            "totalCount": self._report.total_count,
            "passedCount": self._report.passed_count,
            "failedCount": self._report.failed_count,
            "violationCount": self._report.violation_count,
        }

    def _violation_rows(self) -> list[dict[str, str]]:
        if self._report is None:
            return []
        rows = []
        for issue in self._report.issues:
            for violation in issue.violations:
                rows.append(
                    {
                        "key": issue.key,
                        "url": issue.url,
                        "ruleId": violation.rule_id,
                        "section": violation.section,
                        "field": violation.field,
                        "observed": violation.observed,
                        "reason": violation.reason,
                        "guidance": violation.guidance,
                    }
                )
        return rows

    def _can_start(self) -> bool:
        return self._state not in {"resolving", "fetching", "auditing"}

    def _can_export(self) -> bool:
        return self._state == "completed" and self._report is not None

    state = Property(str, lambda self: self._state, notify=stateChanged)
    statusText = Property(str, lambda self: self._status_text, notify=stateChanged)
    inputError = Property(str, lambda self: self._input_error, notify=stateChanged)
    progressValue = Property(float, lambda self: self._progress_value, notify=stateChanged)
    processedCount = Property(int, lambda self: self._processed_count, notify=stateChanged)
    totalCount = Property(int, lambda self: self._total_count, notify=stateChanged)
    ruleRows = Property("QVariantList", _rule_rows, notify=stateChanged)
    resultSummary = Property("QVariantMap", _result_summary, notify=stateChanged)
    violationRows = Property("QVariantList", _violation_rows, notify=stateChanged)
    exportPath = Property(str, lambda self: self._export_path, notify=stateChanged)
    canStart = Property(bool, _can_start, notify=stateChanged)
    canExport = Property(bool, _can_export, notify=stateChanged)
