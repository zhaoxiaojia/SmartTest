from __future__ import annotations

import asyncio
import os
from concurrent.futures import Future
from threading import Event, Thread

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from support.browser_automation import BrowserRuntime
from support.jira_integration.auth.basic import JiraBasicAuth
from support.jira_integration.services.create_issue_service import CreateIssueService
from support.jira_integration.transport.client import JiraClient, JiraClientConfig
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
    dataProgressReady = Signal(int, int, str)

    def __init__(
        self,
        auth_bridge,
        *,
        runtime=None,
        service_factory=None,
        clone_checker=None,
        worker=None,
    ):
        super().__init__()
        self._auth = auth_bridge
        self._runtime = runtime or BrowserRuntime()
        self._service_factory = service_factory
        self._clone_checker = clone_checker
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
        self._clone_status: dict[str, object] = {}
        self._opened_urls: set[str] = set()
        self._data_status = self.tr("Redmine data is not loaded.")
        self._data_loading = False
        self._data_loaded = 0
        self._data_total = 0
        self._progress_loaded = 0
        self._progress_total = 0
        self.resultReady.connect(self._apply)
        self.dataReady.connect(self._apply_data)
        self.dataProgressReady.connect(self._apply_data_progress)

    state = Property(str, lambda self: self._state.value, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    account = Property(str, lambda self: self._account, notify=changed)
    loading = Property(bool, lambda self: self._state is AuthState.SIGNING_IN, notify=changed)
    dataLoading = Property(bool, lambda self: self._data_loading, notify=changed)
    dataStatusText = Property(str, lambda self: self._data_status, notify=changed)
    dataLoaded = Property(int, lambda self: self._data_loaded, notify=changed)
    dataTotal = Property(int, lambda self: self._data_total, notify=changed)
    redmineContext = Property("QVariantMap", lambda self: dict(self._view.get("context_payload", {})), notify=changed)
    projectFilterLabels = Property("QVariantList", lambda self: list(self._view.get("projectFilterLabels", [])), notify=changed)
    statusFilterLabels = Property("QVariantList", lambda self: list(self._view.get("statusFilterLabels", [])), notify=changed)
    typeFilterLabels = Property("QVariantList", lambda self: list(self._view.get("typeFilterLabels", [])), notify=changed)
    filters = Property("QVariantMap", lambda self: dict(self._view.get("filters", {})), notify=changed)
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
        self._apply_clone_status({})
        self._data_status = self.tr("Redmine data loaded.")
        self.changed.emit()

    def _checker(self):
        if self._clone_checker is not None:
            return self._clone_checker
        username, password = self._auth.transientCredential()
        if not username or not password:
            return None
        base_url = os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
        client = JiraClient(JiraClientConfig(base_url=base_url), JiraBasicAuth(username=username, password=password))
        self._clone_checker = _RedmineCloneChecker(CreateIssueService(client, browse_base_url=base_url))
        return self._clone_checker

    def _check_clone_status(self, rows, *, progress_base: int = 0, progress_total: int | None = None):
        checker = self._checker()
        if checker is None:
            return {}
        try:
            return checker.check_many(rows, progress_callback=self._emit_data_progress, progress_base=progress_base, progress_total=progress_total)
        except Exception:
            return {}

    def _apply_clone_status(self, clone_status=None):
        if clone_status:
            self._clone_status.update(clone_status)
        rows = [dict(row) for row in self._view.get("issueRows", [])]
        if not rows:
            return
        for row in rows:
            existing = self._clone_status.get(str(row.get("id") or row.get("key") or ""))
            if existing:
                row["cloneStatus"] = "cloned"
                row["clonedIssueKey"] = getattr(existing, "key", "")
                row["clonedIssueUrl"] = getattr(existing, "web_url", "")
            else:
                row["cloneStatus"] = "not_cloned"
        selected_id = str((self._view.get("selectedIssue") or {}).get("id") or (self._view.get("selectedIssue") or {}).get("key") or "")
        selected = dict(self._view.get("selectedIssue") or {})
        if selected_id:
            selected.update(next((row for row in rows if str(row.get("id") or row.get("key") or "") == selected_id), {}))
        self._view = {**self._view, "issueRows": rows, "selectedIssue": selected}

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
        self._data_loaded = 0
        self._data_total = 0
        self._progress_loaded = 0
        self._progress_total = 0
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
        saved_filters = context_store.load_filters(self._account)

        async def operation():
            service = await self._service_for(self._account)
            collector = RedmineContextCollector(service.page, account=self._account, progress_callback=self._emit_data_progress)
            context = await collector.collect_context()
            list_loaded = self._progress_loaded
            list_total = self._progress_total
            filtered_view = view(
                context,
                all_projects=self.tr("All projects"),
                all_statuses=self.tr("All statuses"),
                filters=saved_filters,
            )
            filtered_rows = filtered_view.get("issueRows", [])
            detail_total = 1 if filtered_rows else 0
            clone_total = len(filtered_rows)
            total_work = list_total + detail_total + clone_total
            self._emit_data_progress(list_loaded, total_work, "Redmine list loaded")
            first_issue_id = str((filtered_view.get("selectedIssue") or {}).get("id") or "")
            first_project, first_issue = context.item_for_issue(first_issue_id)
            if first_issue:
                self._emit_data_progress(list_loaded, total_work, "Loading Redmine issue detail")
                detail = await collector.collect_issue_detail(first_issue, project=first_project)
                self._emit_data_progress(list_loaded + 1, total_work, "Redmine issue detail loaded")
                context_for_view = replace_detail(context, detail)
                rows = view(
                    context_for_view,
                    all_projects=self.tr("All projects"),
                    all_statuses=self.tr("All statuses"),
                    filters=saved_filters,
                    selected_detail=detail,
                ).get("issueRows", [])
                return context, first_project.identifier if first_project else "", detail, saved_filters, self._check_clone_status(rows, progress_base=list_loaded + 1, progress_total=total_work)
            rows = filtered_rows
            return context, "", None, saved_filters, self._check_clone_status(rows, progress_base=list_loaded, progress_total=total_work)

        self._launch_data_load(operation, status=self.tr("Loading Redmine data..."))

    def _emit_data_progress(self, loaded: int, total: int, label: str) -> None:
        self._progress_loaded = int(loaded)
        self._progress_total = int(total)
        self.dataProgressReady.emit(int(loaded), int(total), str(label or ""))

    @Slot(int, int, str)
    def _apply_data_progress(self, loaded: int, total: int, label: str):
        if not self._data_loading:
            return
        self._data_loaded = loaded
        self._data_total = total
        if total > 0:
            self._data_status = self.tr("Loading Redmine data... {loaded}/{total}").format(loaded=loaded, total=total)
        else:
            self._data_status = self.tr("Loading Redmine data...")
        self.changed.emit()

    @Slot(dict)
    @Slot(object)
    def applyFilters(self, filters):
        filters = dict(filters or {})
        project = "" if filters.get("project") == self.tr("All projects") else filters.get("project", "")
        status = "" if filters.get("status") == self.tr("All statuses") else filters.get("status", "")
        issue_type = "" if filters.get("type") in ("", self.tr("All types")) else filters.get("type", "")
        self._view = view(
            self._view["context"],
            all_projects=self.tr("All projects"),
            all_statuses=self.tr("All statuses"),
            filters={"project": project, "status": status, "type": issue_type, "text": str(filters.get("text", "") or "")},
        )
        self._apply_clone_status({})
        self._data_status = self.tr("Redmine data loaded.")
        context_store.save_view(self._account, self._view)
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
        self._apply_clone_status({})

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
            self._apply_clone_status({})
            self._data_status = self.tr("Redmine issue detail refreshed.")
            context_store.save_view(self._account, self._view)
            self.changed.emit()
            return
        context, _project_identifier, detail, filters, clone_status = result
        if detail:
            context = replace_detail(context, detail)
        self._view = view(context, all_projects=self.tr("All projects"), all_statuses=self.tr("All statuses"), filters=filters, selected_detail=detail)
        self._apply_clone_status(clone_status)
        self._data_loaded = sum(len(project.issues) for project in context.projects)
        self._data_total = self._data_loaded
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

    @Slot(str)
    def openWebUrl(self, url):
        clean_url = str(url or "").strip()
        if not clean_url or clean_url in self._opened_urls:
            return
        self._opened_urls.add(clean_url)
        QDesktopServices.openUrl(QUrl(clean_url))


class _RedmineCloneChecker:
    def __init__(self, service: CreateIssueService, *, project_key: str | None = None):
        self._service = service
        self._project_key = project_key or os.getenv("SMARTTEST_REDMINE_JIRA_PROJECT_KEY", "SH")

    def check_many(self, rows, *, progress_callback=None, progress_base: int = 0, progress_total: int | None = None):
        result = {}
        total = len(rows)
        expected_total = progress_total if progress_total is not None else progress_base + total
        for index, row in enumerate(rows, start=1):
            issue_id = str(row.get("id") or row.get("key") or "")
            web_url = str(row.get("webUrl") or "")
            existing = self._service.check_issue_by_external_url(project_key=self._project_key, external_url=web_url)
            if issue_id and existing:
                result[issue_id] = existing
            if progress_callback:
                progress_callback(progress_base + index, expected_total, "Checking cloned Jira issues")
        return result
