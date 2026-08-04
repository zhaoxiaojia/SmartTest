from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from threading import Thread
from typing import Any

from PySide6.QtCore import QObject, Property, QStandardPaths, Signal, Slot

from tool.common.jira_format_audit import (
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
_BUSY_STATES = {
    "resolving",
    "fetching",
    "rule_auditing",
    "ai_reviewing",
    "finalizing",
}
_STAGE_PROGRESS_RANGES = {
    "fetching": (0.0, 0.2),
    "rule_auditing": (0.2, 0.5),
    "ai_reviewing": (0.5, 0.75),
    "finalizing": (0.75, 0.9),
}
_VIOLATION_PAGE_SIZE = 100


class JiraAuditBridge(QObject):
    viewStateChanged = Signal()
    _workerProgress = Signal(object)
    _workerFinished = Signal(object)
    _workerFailed = Signal(object)

    def __init__(
        self,
        auth_bridge: QObject,
    ):
        super().__init__(auth_bridge)
        self._auth = auth_bridge
        self._base_url = JIRA_BASE_URL.rstrip("/")
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
            "violationRowCount": 0,
            "violationPage": 0,
            "violationPageCount": 0,
            "aiReviewText": self.tr("No AI review was required."),
            "exportPath": "",
            "canStart": True,
            "canConfirm": False,
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
            violationRowCount=0,
            violationPage=0,
            violationPageCount=0,
            aiReviewText=self.tr("No AI review was required."),
            exportPath="",
        )
        args = (generation, clean_text, username, str(password))
        Thread(target=self._run_audit, args=args, daemon=True).start()

    def _run_audit(self, generation, text, username, password) -> None:
        try:
            client = JiraClient(
                JiraClientConfig(base_url=self._base_url),
                JiraBasicAuth(username=username, password=password),
            )
            resolved = resolve_audit_input(text, base_url=self._base_url, client=client)
            last_progress = None

            def emit_progress(stage, processed, total):
                nonlocal last_progress
                current = (str(stage or ""), int(processed), int(total))
                if current == last_progress:
                    return
                if last_progress and current[0] == last_progress[0]:
                    if current[1] < last_progress[1]:
                        return
                    step = max(1, (max(current[2], 0) + 99) // 100)
                    if not (
                        current[1] == 0
                        or current[1] >= current[2] > 0
                        or current[2] != last_progress[2]
                        or current[1] - last_progress[1] >= step
                    ):
                        return
                last_progress = current
                self._workerProgress.emit((generation, *current))

            report = JiraAuditService(client, base_url=self._base_url).run(
                resolved,
                emit_progress,
            )
            self._workerFinished.emit({"generation": generation, "report": report})
        except ValueError as exc:
            smart_log("Jira audit input validation failed: %s", exc, level="warning",
                      domain="jira", source="JiraAuditBridge")
            self._workerFailed.emit(
                {"generation": generation, "kind": "input", "message": str(exc)}
            )
        except Exception as exc:
            smart_log("Jira format audit failed: %s", exc, level="error",
                      domain="jira", source="JiraAuditBridge")
            self._workerFailed.emit({"generation": generation, "kind": "audit"})

    @Slot()
    def confirmAudit(self) -> None:
        if self._report is None or self._view["state"] != "awaiting_confirmation":
            self._set(inputError=self.tr("Complete a Jira audit before confirming it."))
            return
        self._set(
            state="confirmed",
            inputError="",
            statusText=self.tr("Jira audit confirmed. Export is ready."),
        )

    @Slot()
    def exportReport(self) -> None:
        if not self._view["canExport"] or self._report is None:
            self._set(inputError=self.tr("Confirm the Jira audit before exporting."))
            return
        try:
            location = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
            downloads_dir = Path(location) if location else Path.home() / "Downloads"
            path = Path(
                export_audit_xlsx(self._report, downloads_dir=downloads_dir)
            ).resolve()
        except Exception:
            smart_log("Jira audit export failed", level="error",
                      domain="jira", source="JiraAuditBridge")
            self._set(inputError=self.tr("Failed to export the Jira audit workbook."))
            return
        self._set(
            state="exported",
            exportPath=str(path),
            inputError="",
            statusText=self.tr("Jira audit workbook exported."),
        )

    @Slot()
    def previousViolationPage(self) -> None:
        if self._report is None:
            return
        page = int(self._view["violationPage"] or 0)
        if page <= 1:
            return
        self._set(**self._violation_page_view(self._report, page - 1))

    @Slot()
    def nextViolationPage(self) -> None:
        if self._report is None:
            return
        page = int(self._view["violationPage"] or 0)
        page_count = int(self._view["violationPageCount"] or 0)
        if page <= 0 or page >= page_count:
            return
        self._set(**self._violation_page_view(self._report, page + 1))

    @Slot(object)
    def _on_worker_progress(self, payload) -> None:
        generation, stage, processed, total = payload
        if int(generation) != self._generation:
            return
        stage = str(stage or "")
        processed, total = max(0, int(processed or 0)), max(0, int(total or 0))
        state = (
            stage
            if stage in _STAGE_PROGRESS_RANGES
            else self._view["state"]
        )
        progress_value = self._view["progressValue"]
        if stage in _STAGE_PROGRESS_RANGES:
            start, end = _STAGE_PROGRESS_RANGES[stage]
            fraction = min(processed / total, 1.0) if total else 1.0
            progress_value = max(
                progress_value,
                start + (end - start) * fraction,
            )
        self._set(
            state=state,
            processedCount=processed,
            totalCount=total,
            progressValue=progress_value,
            statusText=self._stage_text(state),
        )
    @Slot(object)
    def _on_worker_finished(self, payload: dict[str, Any]) -> None:
        if int(payload.get("generation", -1)) != self._generation:
            return
        report = payload.get("report")
        if not isinstance(report, AuditReport):
            self._on_worker_failed(
                {"generation": self._generation, "kind": "audit"}
            )
            return
        violation_view = self._violation_page_view(report, 1)
        self._report = report
        self._set(
            state="awaiting_confirmation",
            processedCount=max(self._view["processedCount"], report.total_count),
            totalCount=max(self._view["totalCount"], report.total_count),
            progressValue=1.0,
            statusText=self.tr("Jira audit completed. Confirm the audit before exporting."),
            inputError="",
            resultSummary={
                "totalCount": report.total_count,
                "passedCount": report.passed_count,
                "failedCount": report.failed_count,
                "violationCount": report.violation_count,
            },
            **violation_view,
            **self._ai_review_view(report),
        )
    @Slot(object)
    def _on_worker_failed(self, payload: dict[str, Any]) -> None:
        if int(payload.get("generation", -1)) != self._generation:
            return
        message = (
            self._input_error_text(str(payload.get("message", "")))
            if payload.get("kind") == "input"
            else self.tr("Jira audit failed. Review the input and sign-in, then try again.")
        )
        self._set(state="failed", statusText=message, inputError=message)
    @Slot()
    def _on_auth_changed(self) -> None:
        self._generation += 1
        self._report = None
        self._set(
            state="failed",
            statusText=self.tr("The login changed. Start the Jira audit again."),
            inputError="",
            progressValue=0.0,
            processedCount=0,
            totalCount=0,
            resultSummary={},
            violationRows=[],
            violationRowCount=0,
            violationPage=0,
            violationPageCount=0,
            aiReviewText=self.tr("No AI review was required."),
            exportPath="",
        )

    def _stage_text(self, state: str) -> str:
        texts = {
            "fetching": self.tr("Fetching Jira issues..."),
            "rule_auditing": self.tr("Reviewing Jira issue formats..."),
            "ai_reviewing": self.tr("Reviewing ambiguous results with AI..."),
            "finalizing": self.tr("Finalizing Jira audit results..."),
        }
        return texts.get(state, self._view["statusText"])

    def _ai_review_view(self, report: AuditReport) -> dict[str, str]:
        statuses = {
            issue.ai_review_status
            for issue in report.issues
            if issue.ai_review_status.value != "not_required"
        }
        if not statuses:
            return {
                "aiReviewText": self.tr("No AI review was required."),
            }
        if any(status.value in {"unconfigured", "failed"} for status in statuses):
            return {
                "aiReviewText": self.tr(
                    "AI review is unavailable. Character-rule results were retained."
                ),
            }
        return {
            "aiReviewText": self.tr("AI review completed."),
        }

    def _violation_page_view(
        self,
        report: AuditReport,
        page: int,
    ) -> dict[str, Any]:
        row_count = report.violation_count
        page_count = (
            (row_count + _VIOLATION_PAGE_SIZE - 1)
            // _VIOLATION_PAGE_SIZE
        )
        if page_count == 0:
            return {
                "violationRows": [],
                "violationRowCount": 0,
                "violationPage": 0,
                "violationPageCount": 0,
            }
        current_page = min(max(int(page), 1), page_count)
        start = (current_page - 1) * _VIOLATION_PAGE_SIZE
        stop = min(start + _VIOLATION_PAGE_SIZE, row_count)
        rows = []
        row_index = 0
        for issue in report.issues:
            for violation in issue.violations:
                if row_index >= stop:
                    break
                if row_index >= start:
                    rows.append(
                        {
                            "issueKey": issue.key,
                            "issueUrl": issue.url,
                            "rule_id": violation.rule_id,
                            "field": violation.field,
                            "observed": violation.observed,
                            "reason": violation.reason,
                            "guidance": violation.guidance,
                        }
                    )
                row_index += 1
            if row_index >= stop:
                break
        return {
            "violationRows": rows,
            "violationRowCount": row_count,
            "violationPage": current_page,
            "violationPageCount": page_count,
        }

    def _input_error_text(self, message: str) -> str:
        texts = {
            "Jira URLs must use HTTP or HTTPS.": self.tr("Jira URLs must use HTTP or HTTPS."),
            "The Jira URL is malformed.": self.tr("The Jira URL is malformed."),
            "The Jira URL host must match the configured Jira host.": self.tr("The Jira URL host must match the configured Jira host."),
            "The Jira issue URL contains an invalid issue key.": self.tr("The Jira issue URL contains an invalid issue key."),
            "Use a Jira issue, filter, or search URL.": self.tr("Use a Jira issue, filter, or search URL."),
            "The Jira filter could not be loaded. Check its permissions.": self.tr("The Jira filter could not be loaded. Check its permissions."),
            "The Jira filter does not contain JQL.": self.tr("The Jira filter does not contain JQL."),
            "JQL validation failed. Check the query and Jira permissions.": self.tr("JQL validation failed. Check the query and Jira permissions."),
        }
        return texts.get(
            message,
            self.tr("Jira input is invalid. Enter JQL or a Jira issue, filter, or search URL."),
        )

    def _set(self, **changes) -> None:
        state = str(changes.get("state", self._view["state"]))
        self._view = {
            **self._view,
            **changes,
            "canStart": state not in _BUSY_STATES,
            "canConfirm": state == "awaiting_confirmation" and self._report is not None,
            "canExport": state in {"confirmed", "exported"} and self._report is not None,
        }
        self.viewStateChanged.emit()
    viewState = Property("QVariantMap", lambda self: self._view, notify=viewStateChanged)
