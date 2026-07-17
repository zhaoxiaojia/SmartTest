from __future__ import annotations

import asyncio
from concurrent.futures import Future
from threading import Event, Thread

from PySide6.QtCore import QObject, Property, Signal, Slot

from support.browser_automation import BrowserRuntime
from support.logging import smart_log
from tool.SmartHome.redmine.auth import RedmineAuthService
from tool.SmartHome.redmine.collector import RedmineContextCollector
from tool.SmartHome.redmine import context_store
from tool.SmartHome.redmine.models import AuthResult, AuthState, Credential
from tool.SmartHome.redmine.view_model import detail_row, empty_view, replace_detail, view


class _AsyncLoopWorker:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._ready = Event()
        self._thread = Thread(target=self._run, name="redmine-browser", daemon=True)
        self._thread.start()
        self._ready.wait()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        self.loop.run_forever()

    def submit(self, coroutine) -> Future:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def stop(self, timeout=5):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            return False
        if not self.loop.is_closed():
            self.loop.close()
        return True


class RedmineBridge(QObject):
    changed = Signal()
    credentialsRequired = Signal()
    verificationRequired = Signal()
    resultReady = Signal(int, object)
    dataReady = Signal(int, object)

    def __init__(
        self,
        auth_bridge,
        *,
        runtime=None,
        service_factory=None,
        worker=None,
    ):
        super().__init__()
        self._auth = auth_bridge
        self._runtime = runtime or BrowserRuntime()
        self._service_factory = service_factory
        self._worker = worker or _AsyncLoopWorker()
        self._service = None
        self._login_future = None
        self._generation = 0
        self._data_generation = 0
        self._closed = False
        self._state = AuthState.IDLE
        self._status = self.tr("Ready to sign in to Redmine.")
        self._account = ""
        self._view = empty_view(self.tr("All projects"), self.tr("All statuses"))
        self._data_status = self.tr("Redmine data is not loaded.")
        self._data_loading = False
        self.resultReady.connect(self._apply)
        self.dataReady.connect(self._apply_data)

    state = Property(str, lambda self: self._state.value, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    account = Property(str, lambda self: self._account, notify=changed)
    loading = Property(bool, lambda self: self._state is AuthState.SIGNING_IN, notify=changed)
    dataLoading = Property(bool, lambda self: self._data_loading, notify=changed)
    dataStatusText = Property(str, lambda self: self._data_status, notify=changed)
    redmineContext = Property("QVariantMap", lambda self: dict(self._view.get("context_payload", {})), notify=changed)
    projectFilterLabels = Property("QVariantList", lambda self: list(self._view.get("projectFilterLabels", [])), notify=changed)
    statusFilterLabels = Property("QVariantList", lambda self: list(self._view.get("statusFilterLabels", [])), notify=changed)
    issueRows = Property("QVariantList", lambda self: list(self._view.get("issueRows", [])), notify=changed)
    selectedIssue = Property("QVariantMap", lambda self: dict(self._view.get("selectedIssue", {})), notify=changed)

    def _load_cached_view(self):
        cached = context_store.load_view(
            self._account,
            all_projects=self.tr("All projects"),
            all_statuses=self.tr("All statuses"),
        )
        if not cached:
            return
        self._view = cached
        self._data_status = self.tr("Redmine data loaded.")
        self.changed.emit()

    async def _service_for(self, account):
        if self._service is None:
            if self._service_factory:
                self._service = self._service_factory(account)
            else:
                session = await self._runtime.context("amlogic_redmine", account)
                self._service = RedmineAuthService(session)
        return self._service

    def _launch(self, operation):
        if self._closed or self._state is AuthState.SIGNING_IN:
            return
        self._generation += 1
        generation = self._generation
        self._state = AuthState.SIGNING_IN
        self._status = self.tr("Signing in to Redmine...")
        self.changed.emit()
        future = self._worker.submit(operation())
        self._login_future = future

        def finished(future):
            try:
                result = future.result()
            except Exception:
                result = AuthResult(AuthState.FAILED, username=self._account)
            self.resultReady.emit(generation, result)

        future.add_done_callback(finished)

    @Slot(int, object)
    def _apply(self, generation, result):
        if self._closed or generation != self._generation:
            return
        self._login_future = None
        self._state = result.state
        self._account = result.username or self._account
        reason_status = {
            "incorrect_verification_code": self.tr(
                "The verification code was rejected. Enter the latest code from your phone."
            ),
            "verification_required": self.tr("Enter the mobile verification code."),
            "credentials_rejected": self.tr("Redmine needs a different account or password."),
            "login_failed": self.tr("Redmine sign-in failed."),
            "verification_not_pending": self.tr("Redmine sign-in failed."),
            "verification_failed": self.tr("Redmine sign-in failed."),
            "unsupported_auth_state": self.tr("Redmine sign-in failed."),
        }
        default_status = {
            AuthState.AUTHENTICATED: self.tr("Redmine sign-in succeeded."),
            AuthState.CREDENTIALS_REQUIRED: self.tr("Redmine needs a different account or password."),
            AuthState.VERIFICATION_REQUIRED: self.tr("Enter the mobile verification code."),
            AuthState.FAILED: self.tr("Redmine sign-in failed."),
        }.get(result.state, result.message)
        self._status = reason_status.get(result.reason, result.message or default_status)
        self.changed.emit()
        if result.state is AuthState.CREDENTIALS_REQUIRED:
            self.credentialsRequired.emit()
        elif result.state is AuthState.VERIFICATION_REQUIRED:
            self.verificationRequired.emit()
        elif result.state is AuthState.AUTHENTICATED:
            self.refreshData()

    def _launch_data_load(self, operation, *, status):
        if self._closed:
            return
        self._data_generation += 1
        generation = self._data_generation
        self._data_loading = True
        self._data_status = status
        self.changed.emit()
        future = self._worker.submit(operation())

        def finished(future):
            try:
                result = future.result()
            except Exception as exc:
                result = exc
            self.dataReady.emit(generation, result)

        future.add_done_callback(finished)

    @Slot()
    def startLogin(self):
        username, password = self._auth.transientCredential()
        self._account = username

        async def operation():
            return await (await self._service_for(username)).login(Credential(username, password))

        self._launch(operation)

    @Slot(str, str)
    def submitCredentials(self, username, password):
        self._account = username.strip()
        self._service = None

        async def operation():
            return await (await self._service_for(self._account)).login(Credential(self._account, password))

        self._launch(operation)

    @Slot(str)
    def submitVerification(self, code):
        async def operation():
            return await self._service.submit_verification(code)

        self._launch(operation)

    @Slot()
    def refreshData(self):
        if self._state is not AuthState.AUTHENTICATED:
            return
        self._load_cached_view()

        async def operation():
            service = await self._service_for(self._account)
            collector = RedmineContextCollector(service.page, account=self._account)
            context = await collector.collect_context()
            projects = [project for project in context.projects if project.project_id]
            first_issue = next((issue for project in projects for issue in project.issues), None)
            if first_issue:
                project = next(project for project in projects if first_issue in project.issues)
                detail = await collector.collect_issue_detail(first_issue, project=project)
                return context, project.identifier, detail
            return context, "", None

        self._launch_data_load(operation, status=self.tr("Loading Redmine data..."))

    @Slot(dict)
    @Slot(object)
    def applyFilters(self, filters):
        filters = dict(filters or {})
        project = "" if filters.get("project") == self.tr("All projects") else filters.get("project", "")
        status = "" if filters.get("status") == self.tr("All statuses") else filters.get("status", "")
        self._view = view(
            self._view["context"],
            all_projects=self.tr("All projects"),
            all_statuses=self.tr("All statuses"),
            filters={"project": project, "status": status, "text": str(filters.get("text", "") or "")},
        )
        self._data_status = self.tr("Redmine data loaded.")
        self.changed.emit()
        rows = self._view.get("issueRows", [])
        first = rows[0] if rows else {}
        if first:
            self.selectIssue(str(first.get("id") or ""))
        else:
            self._view = {**self._view, "selectedIssue": {}, "selectedIssueId": ""}
            self.changed.emit()

    @Slot(str)
    def selectIssue(self, issue_id):
        issue_id = str(issue_id or "").strip()
        if not issue_id or self._state is not AuthState.AUTHENTICATED:
            return
        project, item = self._view["context"].item_for_issue(issue_id)
        if not item:
            return
        self._view = {**self._view, "selectedIssue": detail_row(item=item, project=project), "selectedIssueId": issue_id}

        async def operation():
            service = await self._service_for(self._account)
            collector = RedmineContextCollector(service.page, account=self._account)
            return "detail", issue_id, await collector.collect_issue_detail(item, project=project)

        self._launch_data_load(operation, status=self.tr("Refreshing Redmine issue detail..."))

    @Slot(int, object)
    def _apply_data(self, generation, result):
        if self._closed or generation != self._data_generation:
            return
        self._data_loading = False
        if isinstance(result, Exception):
            smart_log(
                "Redmine data load failed",
                domain="ui",
                source="RedmineBridge",
                level="warning",
                exc_info=(type(result), result, result.__traceback__),
            )
            self._data_status = self.tr("Redmine data load failed.")
            self.changed.emit()
            return
        if isinstance(result, tuple) and len(result) == 3 and result[0] == "detail":
            _kind, issue_id, detail = result
            if issue_id != self._view.get("selectedIssueId"):
                return
            self._view = view(
                replace_detail(self._view["context"], detail),
                all_projects=self.tr("All projects"),
                all_statuses=self.tr("All statuses"),
                filters=self._view.get("filters", {}),
                selected_detail=detail,
            )
            self._data_status = self.tr("Redmine issue detail refreshed.")
            context_store.save_view(self._account, self._view)
            self.changed.emit()
            return
        context, _project_identifier, detail = result
        if detail:
            context = replace_detail(context, detail)
        self._view = view(context, all_projects=self.tr("All projects"), all_statuses=self.tr("All statuses"), selected_detail=detail)
        self._data_status = self.tr("Redmine data loaded.")
        context_store.save_view(self._account, self._view)
        self.changed.emit()

    async def _close_flow(self):
        service, self._service = self._service, None
        if service is not None:
            try:
                await service.close()
            except Exception:
                pass
        await self._runtime.close()

    @Slot()
    def cancelLogin(self):
        self._generation += 1
        self._data_generation += 1
        if self._login_future is not None:
            self._login_future.cancel()
            self._login_future = None
        self._worker.submit(self._close_flow())
        self._state = AuthState.IDLE
        self._status = self.tr("Redmine sign-in cancelled.")
        self._data_loading = False
        self.changed.emit()

    @Slot()
    def close(self):
        if self._closed:
            return
        self._closed = True
        self._generation += 1
        self._data_generation += 1
        if self._login_future is not None:
            self._login_future.cancel()
            self._login_future = None
        try:
            self._worker.submit(self._close_flow()).result(timeout=10)
        finally:
            self._worker.stop()
