"""Asynchronous UI boundary for managed Daily Report projects."""

from __future__ import annotations

import os
from threading import Thread

from PySide6.QtCore import QObject, Property, Signal, Slot

from core.logging import smart_log
from core.tools.common.daily_report import DailyReportError
from core.tools.common.daily_report.background import CREDENTIAL_REF


class DailyReportBridge(QObject):
    stateChanged = Signal()
    scheduleRowsChanged = Signal()
    _operationFinished = Signal(object)
    _operationFailed = Signal(object)

    def __init__(
        self, auth_bridge, *, service, projects, schedule, credentials,
        run_now=None, delivery_mode=None,
    ):
        super().__init__(auth_bridge if isinstance(auth_bridge, QObject) else None)
        self._auth, self._service = auth_bridge, service
        self._projects, self._schedule = projects, schedule
        self._credentials = credentials
        self._run_now = run_now
        self._delivery_mode = delivery_mode
        self._state, self._status = "idle", ""
        self._batch = None
        self._preview_revision = None
        self._selected_project = ""
        self._schedule_state = None
        self._operationFinished.connect(self._on_finished)
        self._operationFailed.connect(self._on_failed)

    @Property(str, notify=stateChanged)
    def state(self): return self._state

    @Property(str, notify=stateChanged)
    def statusText(self): return self._status

    @Property(int, notify=stateChanged)
    def projectCount(self): return len(self._projects.list())

    @Property(int, notify=stateChanged)
    def enabledProjectCount(self): return len(self._projects.enabled())

    @Property(bool, notify=stateChanged)
    def personalMailbox(self):
        return bool(
            self._delivery_mode and self._delivery_mode.load() == "personal"
        )

    @Property(str, notify=stateChanged)
    def mailboxLabel(self):
        return (
            self.tr("LDAP personal mailbox") if self.personalMailbox else
            self.tr("Public mailbox (fae-qa-auto)")
        )

    @Slot(bool)
    def setPersonalMailbox(self, enabled):
        if self._delivery_mode is None:
            raise RuntimeError("Daily Report delivery mode store is unavailable")
        self._delivery_mode.save("personal" if enabled else "public")
        self.stateChanged.emit()

    @Property("QVariantList", notify=stateChanged)
    def projectRows(self):
        previews = {
            report.project.safe_id: report.artifacts.html_path.resolve().as_uri()
            for report in (() if self._batch is None else self._batch.reports)
        }
        return [
            {
                "projectId": project.safe_id, "projectName": project.name,
                "subject": project.subject,
                "jql": project.jql, "to": ", ".join(project.to),
                "cc": ", ".join(project.cc), "enabled": project.enabled,
                "previewUrl": previews.get(project.safe_id, ""),
            }
            for project in self._projects.list()
        ]

    @Property(str, notify=stateChanged)
    def previewUrl(self):
        return next(
            (row["previewUrl"] for row in self.projectRows
             if row["projectId"] == self._selected_project), ""
        )

    @Property(bool, notify=stateChanged)
    def previewValid(self):
        return (
            self._batch is not None and bool(self._batch.reports)
            and self._preview_revision == self._projects.revision()
        )

    @Property("QVariantList", notify=scheduleRowsChanged)
    def scheduleRows(self):
        value = self._schedule.load()
        if value is None:
            return []
        state = self._schedule_state
        names = [project.name for project in self._projects.enabled()]
        content = "; ".join(names) if names else self.tr("No enabled projects")
        send_time = f"{value.hour:02d}:{value.minute:02d}"
        if value.cadence == "daily":
            plan = self.tr("Daily %1").replace("%1", send_time)
        else:
            weekdays = (
                self.tr("Monday"), self.tr("Tuesday"),
                self.tr("Wednesday"), self.tr("Thursday"),
                self.tr("Friday"), self.tr("Saturday"), self.tr("Sunday"),
            )
            plan = (
                self.tr("Weekly %1 %2")
                .replace("%1", weekdays[int(value.weekday)])
                .replace("%2", send_time)
            )
        return [{
            "provider": "daily_report", "planId": "batch",
            "businessTitle": self.tr("Daily Report"),
            "title": self.tr("Daily Report batch"), "enabled": value.enabled,
            "taskTypeText": self.tr("Daily Report"),
            "contentText": content, "planText": plan,
            "registered": bool(state and state.registered),
            "reconciliation": (
                state.reconciliation if state else "task_not_checked"
            ),
            "nextRunAt": str(state.next_run_at or "") if state else "",
            "operationRunning": self._state == "running",
            "operationText": self._status,
            "manageable": True,
            "targetToolId": "daily_report",
        }]

    @Slot()
    def generatePreview(self):
        def operation():
            username, password = self._credential()
            return ("preview", self._service.preview(username, password))
        self._submit(operation, self.tr("Generating report previews..."))

    @Slot()
    def sendPreview(self):
        def operation():
            if not self.previewValid:
                raise ValueError("Daily Report preview is unavailable or stale")
            return ("send", self._service.send_preview(self._batch))
        self._submit(operation, self.tr("Sending reports now..."))

    @Slot("QVariantMap")
    def saveProject(self, payload):
        try:
            self._projects.save(dict(payload))
            self._invalidate(self.tr("Project configuration saved."))
        except Exception as exc: self._on_failed(exc)

    @Slot(str)
    def deleteProject(self, project_id):
        try:
            self._projects.delete(project_id)
            self._invalidate(self.tr("Project deleted."))
        except Exception as exc: self._on_failed(exc)

    @Slot(str, bool)
    def setProjectEnabled(self, project_id, enabled):
        try:
            self._projects.set_enabled(project_id, enabled)
            self._invalidate(self.tr("Project status updated."))
        except Exception as exc: self._on_failed(exc)

    @Slot("QVariantMap")
    def saveSchedule(self, payload):
        def operation():
            username, password = self._credential()
            self._credentials.write(CREDENTIAL_REF, username, password)
            state = self._schedule.save(
                str(payload.get("cadence", "daily")),
                hour=int(payload.get("hour", 18)),
                minute=int(payload.get("minute", 0)),
                weekday=payload.get("weekday"),
            )
            return ("schedule", state)
        self._submit(operation, self.tr("Saving batch schedule..."))

    @Slot()
    def refreshPlans(self):
        self._submit(
            lambda: ("schedule_refresh", self._schedule.state()),
            self.tr("Refreshing batch schedule..."),
        )

    @Slot(str, bool)
    def setPlanEnabled(self, _plan_id, enabled):
        self._submit(
            lambda: ("schedule_enabled", self._schedule.set_enabled(enabled)),
            self.tr("Updating batch schedule status..."),
        )

    @Slot(str)
    def runPlanNow(self, _plan_id):
        if self._state == "running":
            self._status = self.tr("Another Daily Report operation is already running.")
            self.stateChanged.emit(); self.scheduleRowsChanged.emit()
            return
        def operation():
            if self._run_now is None:
                raise RuntimeError("Daily Report immediate runner is unavailable")
            return ("schedule_run", (self._run_now(), self._schedule.state()))
        self._submit(operation, self.tr("Running Daily Report now..."))

    @Slot(str)
    def deletePlan(self, _plan_id):
        def operation():
            deleted = self._schedule.delete()
            self._credentials.delete(CREDENTIAL_REF)
            return ("schedule_delete", deleted)
        self._submit(operation, self.tr("Deleting batch schedule..."))

    def _credential(self):
        username, password = self._auth.transientCredential()
        if not username or not password:
            raise ValueError("Current login credential is unavailable")
        return username, password

    def _invalidate(self, status):
        self._batch = None; self._preview_revision = None
        self._state, self._status = "success", status
        self.stateChanged.emit()

    def _submit(self, operation, running_status):
        if self._state == "running": return
        self._state, self._status = "running", running_status
        self.stateChanged.emit(); self.scheduleRowsChanged.emit()
        def work():
            try: self._operationFinished.emit(operation())
            except Exception as exc: self._operationFailed.emit(exc)
        Thread(target=work, daemon=True).start()

    @Slot(object)
    def _on_finished(self, payload):
        kind, result = payload
        if kind == "preview":
            self._batch = result; self._preview_revision = self._projects.revision()
            self._selected_project = result.reports[0].project.safe_id if result.reports else ""
            status = self.tr("Report previews generated.")
        elif kind == "send":
            status = self.tr("Immediate delivery completed.") if all(
                item.status == "sent" for item in result
            ) else self.tr("Immediate delivery completed with failures.")
        elif kind == "schedule":
            self._schedule_state = result
            status = self.tr("Batch schedule saved.")
        elif kind == "schedule_refresh":
            self._schedule_state = result
            status = self.tr("Batch schedule status refreshed.")
        elif kind == "schedule_enabled":
            self._schedule_state = result
            status = self.tr("Batch schedule status updated.")
        elif kind == "schedule_run":
            exit_code, self._schedule_state = result
            status = (
                self.tr("Daily Report run now completed.")
                if exit_code == 0 else
                self.tr("Daily Report run now completed with failures.")
            )
        elif kind == "schedule_delete":
            self._schedule_state = None
            status = self.tr("Batch schedule deleted.")
        else:
            self._schedule_state = None
            status = self.tr("Batch schedule saved.")
        self._state, self._status = "success", status
        self.stateChanged.emit(); self.scheduleRowsChanged.emit()

    @Slot(object)
    def _on_failed(self, exc):
        smart_log("Daily Report UI operation failed", domain="ui", source="DailyReportBridge", level="error", extra={"error_type": type(exc).__name__})
        self._state = "failed"
        self._status = self.tr("Daily Report configuration or operation failed.")
        self.stateChanged.emit(); self.scheduleRowsChanged.emit()


def create_daily_report_bridge(auth_bridge, data_root):
    from core.jira.auth.basic import JiraBasicAuth
    from core.jira.services.issue_service import JiraIssueService
    from core.jira.transport.client import JiraClient, JiraClientConfig
    from core.credentials.windows import WindowsCredentialStore
    from core.tools.common.daily_report import DailyReportService, DeliveryModeStore, ProjectConfigStore
    from core.tools.common.daily_report.background import run_scheduled_batch
    from core.tools.common.daily_report.schedule import DailyReportScheduleManager
    base_url = os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
    root = data_root / "daily_report"
    projects = ProjectConfigStore(root / "projects.json")
    delivery_mode = DeliveryModeStore(root / "delivery.json")
    def issue_factory(username, password):
        return JiraIssueService(JiraClient(JiraClientConfig(base_url=base_url), JiraBasicAuth(username=username, password=password)))
    service = DailyReportService(issue_service_factory=issue_factory, project_store=projects, report_root=root / "reports", jira_base_url=base_url, delivery_mode=delivery_mode)
    credentials = WindowsCredentialStore(target_prefix="SmartTest/DailyReport/")
    return DailyReportBridge(auth_bridge, service=service, projects=projects,
        schedule=DailyReportScheduleManager(root / "schedule.json"),
        credentials=credentials, delivery_mode=delivery_mode,
        run_now=lambda: run_scheduled_batch(data_root=data_root, immediate=True))
