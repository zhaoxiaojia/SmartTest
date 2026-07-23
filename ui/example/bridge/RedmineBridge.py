from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from concurrent.futures import Future
from threading import Event, Thread

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from support.browser_automation import BrowserRuntime
from support.jira_integration.auth.basic import JiraBasicAuth
from support.jira_integration.core.models import (
    CreateIssueAttachment,
    CreateIssueResult,
    ExistingIssue,
)
from support.jira_integration.services.create_issue_service import CreateIssueService
from support.jira_integration.services.create_schema_service import JiraCreateSchemaService
from support.jira_integration.core.description import render_notes_description
from support.jira_integration.transport.client import JiraClient, JiraClientConfig
from support.logging import smart_log
from tool.SmartHome.redmine.auth import RedmineAuthService
from tool.SmartHome.redmine.clone_draft import CloneDraft, RedmineCloneDraftService
from tool.SmartHome.redmine.collector import RedmineContextCollector, project_options
from tool.SmartHome.redmine.issue_controller import RedmineIssueController
from tool.SmartHome.redmine.issue_analysis_loader import IssueAnalysisLoader, analysis_work_count, consolidate_context
from tool.SmartHome.redmine.mapping import redmine_tracker_to_jira_type
from tool.SmartHome.redmine.overdue import load_redmine_people
from tool.SmartHome.redmine.query import RedmineQuery, parse_terms
from tool.SmartHome.redmine import context_store
from tool.SmartHome.redmine.models import AuthResult, AuthState, Credential
from ui.example.bridge.ToolBridge import amlogic_employees, employee_department, load_tool_access


async def _native_query(collector, filters):
    tracker = str(filters.get("type", "") or "").strip()
    if tracker and not tracker.isdecimal():
        metadata = await collector.collect_filter_metadata(project=str(filters.get("project", "") or ""))
        matches = [value for label, value in metadata.items() if label.casefold() == tracker.casefold()]
        if len(matches) != 1:
            raise ValueError(f"Redmine tracker option is unavailable: {tracker}")
        tracker = matches[0]
    return RedmineQuery(
        project=str(filters.get("project", "") or ""),
        status=str(filters.get("status", "") or ""),
        tracker=tracker,
        subject=str(filters.get("subject", "") or ""),
        text=str(filters.get("text", "") or ""),
    )


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
    projectsReady = Signal(int, object)
    cloneReady = Signal(int, int, str, object)

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
        self._data_future = None
        self._projects_future = None
        self._data_operation_kind = ""
        self._pending_detail_issue_id = ""
        self._pending_filters = None
        self._refresh_after_search = False
        self._active_search_filter_requested = False
        self._generation = 0
        self._data_generation = 0
        self._projects_generation = 0
        self._closed = False
        self._state = AuthState.IDLE
        self._status = self.tr("Ready to sign in to Redmine.")
        self._account = ""
        self._auth_account = str(getattr(auth_bridge, "username", "") or "").strip()
        self._issue_controller = RedmineIssueController(
            all_projects=self.tr("All projects"),
            all_statuses=self.tr("All statuses"),
            all_types=self.tr("All types"),
        )
        self._opened_urls: set[str] = set()
        self._data_status = self.tr("Redmine data is not loaded.")
        self._data_loading = False
        self._data_loaded = 0
        self._data_total = 0
        self._progress_loaded = 0
        self._progress_total = 0
        self._project_options = []
        self._projects_loading = False
        self._projects_ready = False
        self._projects_status = self.tr("Projects are not loaded.")
        self._watched_issue_text = ""
        self._watched_issue_error = ""
        self._clone_generation = 0
        self._clone_future = None
        self._clone_batch_state = "idle"
        self._clone_selected_ids = []
        self._clone_draft_records = []
        self._clone_batch_loaded = 0
        self._clone_batch_total = 0
        self._clone_batch_error = ""
        self._first_invalid_issue_id = ""
        self._first_invalid_field_id = ""
        self._clone_user_options = {}
        self._jira_client = None
        self._jira_create_service = None
        self._jira_schema_service = None
        self._draft_service = RedmineCloneDraftService()
        self.resultReady.connect(self._apply)
        self.dataReady.connect(self._apply_data)
        self.dataProgressReady.connect(self._apply_data_progress)
        self.projectsReady.connect(self._apply_projects)
        self.cloneReady.connect(self._apply_clone_result)
        auth_bridge.authChanged.connect(self._on_auth_changed)

    @Slot()
    def _on_auth_changed(self):
        next_account = str(getattr(self._auth, "username", "") or "").strip()
        if next_account == self._auth_account:
            return
        old_account = self._account or self._auth_account
        self._auth_account = next_account
        self._generation += 1
        self._data_generation += 1
        self._projects_generation += 1
        if self._login_future is not None:
            self._login_future.cancel()
            self._login_future = None
        if self._data_future is not None:
            self._data_future.cancel()
            self._data_future = None
        for name in ("_projects_future",):
            future = getattr(self, name)
            if future is not None:
                future.cancel()
                setattr(self, name, None)
        service, self._service = self._service, None
        if service is not None or old_account:
            self._worker.submit(self._close_account_flow(service, old_account))
        self._clone_checker = None
        self._jira_client = None
        self._jira_create_service = None
        self._jira_schema_service = None
        self._reset_clone_batch(cancel_future=True)
        self._pending_filters = None
        self._pending_detail_issue_id = ""
        self._refresh_after_search = False
        self._active_search_filter_requested = False
        self._state = AuthState.IDLE
        self._account = ""
        self._issue_controller.reset()
        self._data_status = self.tr("Redmine data is not loaded.")
        self._data_loading = False
        self._data_loaded = 0
        self._data_total = 0
        self._progress_loaded = 0
        self._progress_total = 0
        self._project_options = []
        self._projects_loading = False
        self._projects_ready = False
        self._projects_status = self.tr("Projects are not loaded.")
        self.changed.emit()

    async def _close_account_flow(self, service, account):
        if service is not None:
            try:
                await service.close()
            except Exception:
                pass
        if account:
            try:
                await self._runtime.close_context("amlogic_redmine", account)
            except Exception:
                pass

    state = Property(str, lambda self: self._state.value, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    account = Property(str, lambda self: self._account, notify=changed)
    loading = Property(bool, lambda self: self._state is AuthState.SIGNING_IN, notify=changed)
    dataLoading = Property(bool, lambda self: self._data_loading, notify=changed)
    dataStatusText = Property(str, lambda self: self._data_status, notify=changed)
    dataLoaded = Property(int, lambda self: self._data_loaded, notify=changed)
    dataTotal = Property(int, lambda self: self._data_total, notify=changed)
    quickViews = Property("QVariantList", lambda self: [
        {"id": "my_assigned", "label": self.tr("Issues assigned to me")},
        {"id": "watched", "label": self.tr("Watched issues")},
    ], notify=changed)
    activeQuickViewId = Property(str, lambda self: self._issue_controller.active_view_id, notify=changed)
    watchedIssueText = Property(str, lambda self: self._watched_issue_text, notify=changed)
    watchedIssueError = Property(str, lambda self: self._watched_issue_error, notify=changed)
    projectOptions = Property(
        "QVariantList",
        lambda self: [{"id": "", "label": self.tr("All projects")}, *list(self._project_options)],
        notify=changed,
    )
    projectsLoading = Property(bool, lambda self: self._projects_loading, notify=changed)
    projectsReadyState = Property(bool, lambda self: self._projects_ready, notify=changed)
    projectsStatusText = Property(str, lambda self: self._projects_status, notify=changed)
    searchLoading = Property(bool, lambda self: self._data_loading and self._data_operation_kind == "search", notify=changed)
    searchCanCancel = Property(bool, lambda self: self._data_loading and self._data_operation_kind == "search" and self._data_future is not None, notify=changed)
    redmineContext = Property("QVariantMap", lambda self: self._issue_controller.snapshot.context_payload, notify=changed)
    projectFilterLabels = Property("QVariantList", lambda self: list(self._issue_controller.snapshot.project_filter_labels), notify=changed)
    statusFilterLabels = Property("QVariantList", lambda self: list(self._issue_controller.snapshot.status_filter_labels), notify=changed)
    typeFilterLabels = Property("QVariantList", lambda self: list(self._issue_controller.snapshot.type_filter_labels), notify=changed)
    filters = Property("QVariantMap", lambda self: self._issue_controller.snapshot.filters, notify=changed)
    issueRows = Property("QVariantList", lambda self: list(self._issue_controller.snapshot.issue_rows), notify=changed)
    selectedIssue = Property("QVariantMap", lambda self: self._issue_controller.snapshot.selected_issue, notify=changed)
    actionableIssues = Property("QVariantList", lambda self: list(self._issue_controller.snapshot.actionable_issues), notify=changed)
    cloneSelectionMode = Property(bool, lambda self: self._clone_batch_state == "selecting", notify=changed)
    cloneSelectedIds = Property("QVariantList", lambda self: list(self._clone_selected_ids), notify=changed)
    cloneDrafts = Property("QVariantList", lambda self: [self._clone_record_payload(item) for item in self._clone_draft_records], notify=changed)
    cloneBatchState = Property(str, lambda self: self._clone_batch_state, notify=changed)
    cloneBatchLoaded = Property(int, lambda self: self._clone_batch_loaded, notify=changed)
    cloneBatchTotal = Property(int, lambda self: self._clone_batch_total, notify=changed)
    cloneBatchError = Property(str, lambda self: self._clone_batch_error, notify=changed)
    firstInvalidIssueId = Property(str, lambda self: self._first_invalid_issue_id, notify=changed)
    firstInvalidFieldId = Property(str, lambda self: self._first_invalid_field_id, notify=changed)

    def _load_cached_view(self):
        self._issue_controller.set_account(self._account)
        self._issue_controller.activate_view("")
        if not self._issue_controller.load_cached():
            return
        self._data_status = self.tr("Redmine data loaded.")
        self.changed.emit()

    def _checker(self):
        if self._clone_checker is not None:
            return self._clone_checker
        _client, create_service, _schema_service = self._jira_dependencies()
        if create_service is None:
            return None
        self._clone_checker = _RedmineCloneChecker(create_service)
        return self._clone_checker

    def _jira_dependencies(self):
        if self._jira_client is not None:
            return self._jira_client, self._jira_create_service, self._jira_schema_service
        username, password = self._auth.transientCredential()
        if not username or not password:
            return None, None, None
        base_url = os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
        self._jira_client = JiraClient(
            JiraClientConfig(base_url=base_url),
            JiraBasicAuth(username=username, password=password),
        )
        self._jira_create_service = CreateIssueService(
            self._jira_client,
            browse_base_url=base_url,
        )
        self._jira_schema_service = JiraCreateSchemaService(self._jira_client)
        return self._jira_client, self._jira_create_service, self._jira_schema_service

    def _check_clone_status(self, rows, *, progress_base: int = 0, progress_total: int | None = None, emit_progress: bool = True):
        checker = self._checker()
        if checker is None:
            smart_log("[REDMINE_LOAD] clone finished", domain="tool", source="RedmineBridge", level="info", extra={"checked": 0, "total": len(rows), "skipped": True})
            return None
        def on_progress(loaded, total, _label):
            self._emit_data_progress(loaded, total, "clone")
            smart_log("[REDMINE_LOAD] clone progress", domain="tool", source="RedmineBridge", level="debug", extra={"loaded": loaded, "total": total})
        try:
            result = checker.check_many(rows, progress_callback=on_progress if emit_progress else None, progress_base=progress_base, progress_total=progress_total)
            smart_log("[REDMINE_LOAD] clone finished", domain="tool", source="RedmineBridge", level="info", extra={"checked": len(rows), "total": progress_total or progress_base + len(rows), "matches": len(result)})
            return result
        except Exception as exc:
            smart_log("[REDMINE_LOAD] clone failure", domain="tool", source="RedmineBridge", level="warning", extra={"checked": 0, "total": len(rows), "error_type": type(exc).__name__})
            return None

    async def _service_for(self, account):
        if self._service is None:
            if self._service_factory:
                self._service = self._service_factory(account)
            else:
                session = await self._runtime.context("amlogic_redmine", account)
                self._service = RedmineAuthService(session)
        return self._service

    @asynccontextmanager
    async def _operation_page(self, service):
        operation_page = getattr(service, "operation_page", None)
        if operation_page is not None:
            async with operation_page() as page:
                yield page
            return
        yield service.page

    async def _enrich_issue_context(self, page, context, filters, *, progress=True):
        context = consolidate_context(context)
        analysis_total = analysis_work_count(context)
        planned_clone_rows = list(
            self._issue_controller.enrichment_projection(
                context, filters
            ).issue_rows
        )
        total_work = analysis_total + len(planned_clone_rows)
        if progress:
            self._emit_data_progress(0, total_work, "analysis")
        aml_names, _departments = load_redmine_people(Path(__file__).resolve().parents[3] / "config" / "personnel.json")
        loader = IssueAnalysisLoader(
            page,
            max_concurrency=int(os.getenv("SMARTTEST_REDMINE_DETAIL_CONCURRENCY", "6")),
            progress_callback=(lambda done, _total, _label: self._emit_data_progress(done, total_work, "analysis")) if progress else None,
        )
        context = await loader.analyze(context, aml_names=aml_names)
        selected = self._issue_controller.enrichment_projection(
            context, filters
        ).source
        if progress:
            self._emit_data_progress(analysis_total, total_work, "clone")
        clone_status = self._check_clone_status(planned_clone_rows, progress_base=analysis_total, progress_total=total_work, emit_progress=progress)
        return context, selected.project.identifier if selected.project and selected.item else "", selected.detail, filters, clone_status

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
            except Exception as exc:
                result = AuthResult(AuthState.FAILED, username=self._account, reason="operation_exception")
                smart_log(
                    "[REDMINE_AUTH] login failure",
                    domain="tool",
                    source="RedmineBridge",
                    level="warning",
                    extra={"state": "failed", "reason": result.reason, "error_type": type(exc).__name__},
                )
            self.resultReady.emit(generation, result)

        future.add_done_callback(finished)

    @Slot(int, object)
    def _apply(self, generation, result):
        if self._closed or generation != self._generation:
            return
        self._login_future = None
        self._state = result.state
        self._account = result.username or self._account
        self._issue_controller.set_account(self._account)
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
        if result.state is AuthState.FAILED and result.reason != "operation_exception":
            smart_log(
                "[REDMINE_AUTH] login failure",
                domain="tool",
                source="RedmineBridge",
                level="warning",
                extra={"state": result.state.value, "reason": result.reason, "error_type": ""},
            )
        self.changed.emit()
        if result.state is AuthState.CREDENTIALS_REQUIRED:
            self.credentialsRequired.emit()
        elif result.state is AuthState.VERIFICATION_REQUIRED:
            self.verificationRequired.emit()
        elif result.state is AuthState.AUTHENTICATED:
            self.activateQuickView("my_assigned")
            self.refreshProjects()

    def _load_quick_view_cache(self, quick_view_id):
        self._issue_controller.set_account(self._account)
        self._issue_controller.activate_view(quick_view_id)
        if not self._issue_controller.load_cached():
            return False
        self._data_status = self.tr("Issues assigned to me loaded.")
        self.changed.emit()
        return True

    @Slot()
    def refreshProjects(self):
        if self._state is not AuthState.AUTHENTICATED or self._projects_loading:
            return
        cached = context_store.load_project_options(self._account)
        if cached:
            self._project_options = cached
        self._projects_generation += 1
        generation = self._projects_generation
        self._projects_loading = True
        self._projects_ready = False
        self._projects_status = self.tr("Loading Redmine projects...")
        self.changed.emit()
        async def operation():
            service = await self._service_for(self._account)
            async with self._operation_page(service) as page:
                projects = await RedmineContextCollector(page, account=self._account).collect_projects()
                return project_options(projects)
        future = self._worker.submit(operation()); self._projects_future = future
        def finished(done):
            try:
                result = done.result()
            except Exception as exc:
                result = exc
            self.projectsReady.emit(generation, result)
        future.add_done_callback(finished)

    @Slot(int, object)
    def _apply_projects(self, generation, result):
        if self._closed or generation != self._projects_generation:
            return
        self._projects_future = None; self._projects_loading = False
        if isinstance(result, Exception):
            self._projects_status = self.tr("Redmine project loading failed.")
        elif result:
            self._project_options = list(result)
            context_store.save_project_options(self._account, self._project_options)
            self._projects_ready = True
            self._projects_status = self.tr("Redmine projects loaded.")
            if self._issue_controller.active_view_id == "my_assigned":
                self._issue_controller.apply_project_options(self._project_options)
        else:
            self._projects_status = self.tr("No Redmine projects were loaded. Retry project loading.")
        self.changed.emit()

    @Slot(str)
    def activateQuickView(self, quick_view_id):
        if self._state is not AuthState.AUTHENTICATED or self._data_loading or quick_view_id not in ("my_assigned", "watched"):
            return
        self._issue_controller.activate_view(quick_view_id)
        self._load_quick_view_cache(quick_view_id)
        if quick_view_id == "watched":
            issue_ids = context_store.load_watched_issue_ids(self._account)
            self._watched_issue_text = " ".join(issue_ids)
            if issue_ids:
                self._launch_watched_query(issue_ids, validate=False)
            else:
                self.changed.emit()
            return
        async def operation():
            service = await self._service_for(self._account)
            async with self._operation_page(service) as page:
                self._emit_data_progress(0, 0, "my_assigned")
                rows = await RedmineContextCollector(page, account=self._account).collect_my_page_assigned()
                if not rows:
                    return "quick_view_empty",
                metadata = list(self._project_options)
                metadata.extend(self._issue_controller.context_project_options())
                context = self._issue_controller.assigned_context(rows, metadata)
                return await self._enrich_issue_context(page, context, {}, progress=True)
        self._launch_data_load(operation, status=self.tr("Loading issues assigned to me..."), kind="my_assigned")

    def _launch_data_load(self, operation, *, status, kind="detail"):
        if self._closed:
            return
        self._data_generation += 1
        generation = self._data_generation
        self._data_loading = True
        self._data_operation_kind = kind
        self._data_loaded = 0
        self._data_total = 0
        self._progress_loaded = 0
        self._progress_total = 0
        self._data_status = status
        self.changed.emit()
        future = self._worker.submit(operation())
        self._data_future = future

        def finished(future):
            try:
                result = future.result()
            except Exception as exc:
                result = exc
            smart_log("[REDMINE_LOAD] data failure" if isinstance(result, Exception) else "[REDMINE_LOAD] data finished", domain="tool", source="RedmineBridge", level="warning" if isinstance(result, Exception) else "info", extra={"kind": kind, "generation": generation, "error_type": type(result).__name__ if isinstance(result, Exception) else ""})
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
        if not self._projects_ready:
            return
        if self._data_loading:
            self._refresh_after_search = True
            return
        filter_requested = self._pending_filters is not None
        if not filter_requested:
            self._load_cached_view()
        saved_filters = self._issue_controller.filters_for_search(
            self._pending_filters if filter_requested else None
        )
        self._pending_filters = None
        self._active_search_filter_requested = filter_requested
        self._issue_controller.activate_view("")
        project_metadata = list(self._project_options)

        async def operation():
            service = await self._service_for(self._account)
            smart_log("[REDMINE_LOAD] discovery", domain="tool", source="RedmineBridge", level="debug", extra={"phase": "discovery"})
            self._emit_data_progress(0, 0, "discovery")
            async with self._operation_page(service) as page:
                collector = RedmineContextCollector(page, account=self._account, progress_callback=lambda _loaded, _total, _label: self._emit_data_progress(0, 0, "discovery"))
                effective_filters = saved_filters
                context = await collector.collect_query(await _native_query(collector, saved_filters))
                context = self._issue_controller.reconcile_project_ids(
                    context, project_metadata
                )
                enriched = await self._enrich_issue_context(page, context, effective_filters, progress=True)
            project_count = sum(bool(project.project_id) for project in context.projects)
            collected_rows = sum(len(project.issues) for project in context.projects)
            unique_issues = sum(len(project.issues) for project in enriched[0].projects)
            filtered_rows = len(
                self._issue_controller.enrichment_projection(
                    enriched[0], effective_filters
                ).issue_rows
            )
            smart_log("[REDMINE_LOAD] plan", domain="tool", source="RedmineBridge", level="info", extra={"projects": project_count, "collected_rows": collected_rows, "unique_issues": unique_issues, "filtered_rows": filtered_rows})
            return enriched

        self._launch_data_load(operation, status=self.tr("Loading Redmine data..."), kind="search")

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
        if label == "discovery":
            self._data_status = self.tr("Discovering Redmine projects and issues...")
        elif label == "my_assigned":
            self._data_status = self.tr("Loading issues assigned to me...")
        elif label == "analysis":
            self._data_status = self.tr("Analyzing Redmine issue activity... {loaded}/{total}").format(loaded=loaded, total=total)
        elif label == "clone":
            self._data_status = self.tr("Checking cloned Jira issues... {loaded}/{total}").format(loaded=loaded, total=total)
        elif total > 0:
            self._data_status = self.tr("Loading Redmine data... {loaded}/{total}").format(loaded=loaded, total=total)
        else:
            self._data_status = self.tr("Loading Redmine data...")
        self.changed.emit()

    def _launch_watched_query(self, issue_ids, *, validate, submitted_terms=None):
        submitted = tuple(issue_ids)
        terms = tuple(submitted_terms or submitted)
        project_metadata = list(self._project_options)
        async def operation():
            service = await self._service_for(self._account)
            async with self._operation_page(service) as page:
                context = await RedmineContextCollector(page, account=self._account).collect_query(
                    RedmineQuery(issue_ids=submitted)
                )
                context = self._issue_controller.reconcile_project_ids(
                    context, project_metadata
                )
                enriched = await self._enrich_issue_context(page, context, {}, progress=True)
                return (*enriched, submitted, terms, validate)
        self._launch_data_load(operation, status=self.tr("Loading watched issues..."), kind="watched")

    @Slot(str)
    def saveWatchedIssueIds(self, text):
        terms = parse_terms(text)
        submitted = tuple(term for term in terms if term.isdecimal())
        invalid_syntax = tuple(term for term in terms if not term.isdecimal())
        self._watched_issue_text = str(text or "")
        self._watched_issue_error = ""
        self._issue_controller.activate_view("watched")
        if not terms:
            context_store.save_watched_issue_ids(self._account, [])
            self._watched_issue_text = ""
            self._issue_controller.clear_watched_view()
            self.changed.emit()
            return
        if not submitted:
            self._watched_issue_error = self.tr("Invalid issue IDs: %1").replace("%1", ", ".join(invalid_syntax))
            self.changed.emit()
            return
        self._load_quick_view_cache("watched")
        self._launch_watched_query(submitted, validate=True, submitted_terms=terms)

    @Slot(dict)
    @Slot(object)
    def applyFilters(self, filters):
        if not self._projects_ready:
            return
        filters = dict(filters or {})
        project = "" if filters.get("project") == self.tr("All projects") else filters.get("project", "")
        status = "" if filters.get("status") == self.tr("All statuses") else filters.get("status", "")
        issue_type = "" if filters.get("type") in ("", self.tr("All types")) else filters.get("type", "")
        self._pending_filters = {"project": project, "status": status, "type": issue_type, "subject": str(filters.get("subject", "") or ""), "text": str(filters.get("text", "") or "")}
        smart_log("[REDMINE_FILTER] refresh requested", domain="tool", source="RedmineBridge", level="info", extra={"project": bool(project), "status": status, "type": issue_type, "text_present": bool(self._pending_filters["text"])})
        if self._data_loading:
            self._refresh_after_search = True
            return
        self.refreshData()

    @Slot()
    def cancelSearch(self):
        if self._data_future is None or self._data_operation_kind != "search":
            return
        self._data_generation += 1
        self._data_future.cancel()
        self._data_future = None
        self._data_loading = False
        self._data_operation_kind = ""
        self._data_status = self.tr("Search cancelled.")
        self.changed.emit()

    @Slot(str)
    def selectIssue(self, issue_id):
        issue_id = str(issue_id or "").strip()
        if not issue_id or self._state is not AuthState.AUTHENTICATED:
            return
        selection = self._issue_controller.select_issue(issue_id)
        if selection.issue is None or selection.project is None or selection.item is None:
            return
        if not selection.needs_detail:
            self.changed.emit()
            return

        if self._data_loading and self._data_operation_kind == "search":
            self._pending_detail_issue_id = issue_id
            self.changed.emit()
            return

        async def operation():
            service = await self._service_for(self._account)
            async with self._operation_page(service) as page:
                collector = RedmineContextCollector(page, account=self._account)
                return "detail", issue_id, await collector.collect_issue_detail(
                    selection.item, project=selection.project
                )

        self._launch_data_load(operation, status=self.tr("Refreshing Redmine issue detail..."), kind="detail")

    @Slot(int, object)
    def _apply_data(self, generation, result):
        if self._closed or generation != self._data_generation:
            return
        operation_kind = self._data_operation_kind
        self._issue_controller.set_account(self._account)
        self._data_loading = False
        self._data_operation_kind = ""
        self._data_future = None
        if self._refresh_after_search:
            self._refresh_after_search = False
            self.refreshData()
            return
        if isinstance(result, Exception):
            smart_log(
                "Redmine data load failed",
                domain="ui",
                source="RedmineBridge",
                level="warning",
                exc_info=(type(result), result, result.__traceback__),
            )
            if operation_kind == "my_assigned":
                smart_log("[REDMINE_MY_ASSIGNED] refresh failed", domain="tool", source="RedmineBridge", level="warning", extra={"error_type": type(result).__name__})
                self._data_status = self.tr("Issues assigned to me loading failed.")
            else:
                self._data_status = self.tr("Redmine data load failed.")
            self.changed.emit()
            return
        if operation_kind == "my_assigned" and result == ("quick_view_empty",):
            self._issue_controller.activate_view("my_assigned")
            self._issue_controller.clear_active_view()
            self._data_status = self.tr("Issues assigned to me loaded.")
            self.changed.emit()
            return
        if isinstance(result, tuple) and len(result) == 3 and result[0] == "detail":
            _kind, issue_id, detail = result
            if not self._issue_controller.apply_selected_detail(issue_id, detail):
                return
            self._data_status = self.tr("Redmine issue detail refreshed.")
            self.changed.emit()
            return
        watched_submission = ()
        watched_terms = ()
        watched_validate = False
        if operation_kind == "watched":
            context, _project_identifier, detail, filters, clone_status, watched_submission, watched_terms, watched_validate = result
        else:
            context, _project_identifier, detail, filters, clone_status = result
        if operation_kind == "search" and not self._active_search_filter_requested:
            wanted_id = self._issue_controller.snapshot.selected_id
            detail = next((item for item in context.issues if item.id == wanted_id), detail if not wanted_id else None)
        self._data_loaded = sum(len(project.issues) for project in context.projects)
        self._data_total = self._data_loaded
        self._data_status = self.tr("Issues assigned to me loaded.") if operation_kind == "my_assigned" else self.tr("Redmine data loaded.")
        if operation_kind == "watched":
            valid_ids = {issue.id for project in context.projects for issue in project.issues}
            valid = [issue_id for issue_id in watched_submission if issue_id in valid_ids]
            invalid = [term for term in watched_terms if term not in valid_ids]
            if watched_validate and not valid:
                self._watched_issue_error = self.tr("No valid watched issue IDs were found: %1").replace("%1", ", ".join(invalid))
                if self._load_quick_view_cache("watched"):
                    self.changed.emit()
                    return
            else:
                if watched_validate:
                    context_store.save_watched_issue_ids(self._account, valid)
                    self._watched_issue_text = " ".join(valid)
                self._watched_issue_error = self.tr("Invalid issue IDs: %1").replace("%1", ", ".join(invalid)) if invalid else ""
        self._issue_controller.replace_result(
            context,
            filters=filters,
            selected_detail=detail,
            clone_status=clone_status,
        )
        if operation_kind == "search" and self._active_search_filter_requested:
            snapshot = self._issue_controller.snapshot
            smart_log("[REDMINE_FILTER] refresh applied", domain="tool", source="RedmineBridge", level="info", extra={"project": bool(filters.get("project")), "status": filters.get("status", ""), "type": filters.get("type", ""), "text_present": bool(filters.get("text")), "result_count": len(snapshot.issue_rows), "actionable_count": len(snapshot.actionable_issues)})
            self._active_search_filter_requested = False
        self.changed.emit()
        pending_issue_id, self._pending_detail_issue_id = self._pending_detail_issue_id, ""
        selected_issue_id = self._issue_controller.snapshot.selected_id
        detail_issue_id = pending_issue_id or selected_issue_id
        if operation_kind == "search" and detail_issue_id and detail_issue_id == selected_issue_id and not any(item.id == detail_issue_id for item in context.issues):
            self.selectIssue(detail_issue_id)

    def _reset_clone_batch(self, *, cancel_future=False):
        self._clone_generation += 1
        if cancel_future and self._clone_future is not None:
            self._clone_future.cancel()
        self._clone_future = None
        self._clone_batch_state = "idle"
        self._clone_selected_ids = []
        self._clone_draft_records = []
        self._clone_batch_loaded = 0
        self._clone_batch_total = 0
        self._clone_batch_error = ""
        self._first_invalid_issue_id = ""
        self._first_invalid_field_id = ""
        self._clone_user_options = {}

    @Slot()
    def beginCloneSelection(self):
        if self._clone_batch_state != "idle":
            return
        self._clone_batch_state = "selecting"
        self._clone_selected_ids = []
        self._clone_batch_error = ""
        self.changed.emit()

    @Slot(str, bool)
    def toggleCloneSelection(self, issue_id, selected):
        if self._clone_batch_state != "selecting":
            return
        issue_id = str(issue_id or "").strip()
        rows = self._issue_controller.snapshot.issue_rows
        row = next(
            (
                item
                for item in rows
                if str(item.get("id") or item.get("key") or "") == issue_id
            ),
            None,
        )
        if row is None or row.get("cloneStatus") == "cloned":
            return
        selected_ids = set(self._clone_selected_ids)
        if selected:
            selected_ids.add(issue_id)
        else:
            selected_ids.discard(issue_id)
        self._clone_selected_ids = [
            str(item.get("id") or item.get("key") or "")
            for item in rows
            if str(item.get("id") or item.get("key") or "") in selected_ids
        ]
        self.changed.emit()

    @Slot()
    def cancelCloneSelection(self):
        if self._clone_batch_state != "selecting":
            return
        self._reset_clone_batch()
        self.changed.emit()

    def _launch_clone(self, kind, operation):
        self._clone_generation += 1
        clone_generation = self._clone_generation
        account_generation = self._generation
        future = self._worker.submit(operation())
        self._clone_future = future

        def finished(done):
            try:
                result = done.result()
            except Exception as exc:
                result = exc
            self.cloneReady.emit(clone_generation, account_generation, kind, result)

        future.add_done_callback(finished)

    @Slot()
    def prepareCloneDrafts(self):
        if self._clone_batch_state not in ("selecting", "prepare_failed") or not self._clone_selected_ids:
            return
        self._clone_batch_state = "loading"
        self._clone_draft_records = []
        self._clone_batch_loaded = 0
        self._clone_batch_total = len(self._clone_selected_ids)
        self._clone_batch_error = ""
        self.changed.emit()

        async def operation():
            jira_client, _create_service, schema_service = self._jira_dependencies()
            if jira_client is None or schema_service is None:
                raise RuntimeError("Jira credentials are unavailable")
            account = str(getattr(self._auth, "username", "") or "").strip()
            current_user = jira_client.current_user()
            reporter = str(current_user.get("account") or "").strip()
            if not reporter:
                raise RuntimeError("Current Jira reporter identity is unavailable")
            personnel = load_tool_access(
                Path(__file__).resolve().parents[3] / "config" / "personnel.json"
            )
            department = employee_department(personnel, account)
            display_names = {
                str(employee.get("account") or "").strip(): str(employee.get("display_name") or "").strip()
                for employee in amlogic_employees(personnel)
                if str(employee.get("account") or "").strip()
            }
            if str(current_user.get("display_name") or "").strip():
                display_names[reporter] = str(current_user.get("display_name") or "").strip()
            records = []
            schemas = {}
            for issue_id in self._clone_selected_ids:
                source = self._issue_controller.source_for_issue(issue_id)
                project, item, detail = source.project, source.item, source.detail
                if project is None or item is None:
                    raise RuntimeError(f"Redmine issue {issue_id} is unavailable")
                if detail is None:
                    service = await self._service_for(self._account)
                    async with self._operation_page(service) as page:
                        detail = await RedmineContextCollector(
                            page,
                            account=self._account,
                        ).collect_issue_detail(item, project=project)
                issue_type = redmine_tracker_to_jira_type(detail.tracker)
                if issue_type not in schemas:
                    schemas[issue_type] = schema_service.schema("SH", issue_type)
                    attachment_fields = [
                        field for field in schemas[issue_type]
                        if str(field.name or "").strip().casefold() == "attachment links"
                    ]
                    if len(attachment_fields) != 1:
                        raise RuntimeError("Jira create schema must contain exactly one Attachment links field")
                draft = self._draft_service.build(
                    issue=detail,
                    project=project,
                    schema=schemas[issue_type],
                    account=reporter,
                    department=department,
                    prepared_description=render_notes_description(detail.description),
                )
                records.append(
                    {
                        "draft": draft,
                        "state": "editing",
                        "key": "",
                        "url": "",
                        "error": "",
                        "errorFieldId": "",
                    }
                )
            return records, display_names

        self._launch_clone("prepare", operation)

    @Slot(str, str, "QVariant")
    def updateCloneDraft(self, issue_id, field_id, value):
        if self._clone_batch_state != "editing":
            return
        record = self._clone_record(issue_id)
        if record is None:
            return
        try:
            record["draft"].update(str(field_id or ""), value)
        except (KeyError, TypeError, ValueError) as exc:
            record["error"] = str(exc)
            record["errorFieldId"] = str(field_id or "")
        else:
            record["error"] = ""
            record["errorFieldId"] = ""
        self._first_invalid_issue_id = ""
        self._first_invalid_field_id = ""
        self.changed.emit()

    @Slot()
    def submitCloneBatch(self):
        if self._clone_batch_state != "editing":
            return
        self._clone_batch_state = "validating"
        self._first_invalid_issue_id = ""
        self._first_invalid_field_id = ""
        for record in self._clone_draft_records:
            if record["error"]:
                self._first_invalid_issue_id = record["draft"].source_id
                self._first_invalid_field_id = record["errorFieldId"]
                self._clone_batch_state = "editing"
                self.changed.emit()
                return
            errors = record["draft"].errors
            if errors:
                self._first_invalid_issue_id = record["draft"].source_id
                self._first_invalid_field_id = errors[0].field_id
                self._clone_batch_state = "editing"
                self.changed.emit()
                return
        self._submit_clone_records(self._clone_draft_records)

    def _submit_clone_records(self, records):
        self._clone_batch_state = "submitting"
        self._clone_batch_loaded = 0
        self._clone_batch_total = len(records)
        self._clone_batch_error = ""
        self.changed.emit()

        async def operation():
            _client, create_service, _schema_service = self._jira_dependencies()
            if create_service is None:
                raise RuntimeError("Jira credentials are unavailable")
            results = []
            for record in records:
                draft = record["draft"]
                try:
                    request = draft.to_request()
                    if draft.source_attachments:
                        service = await self._service_for(self._account)
                        async with self._operation_page(service) as page:
                            attachments = await _download_redmine_attachments(
                                page, draft.source_attachments
                            )
                        request = replace(request, attachments=attachments)
                    existing = create_service.check_issue_by_external_url(
                        project_key="SH",
                        external_url=draft.source_url,
                    )
                    if existing:
                        errors = create_service.sync_attachments(
                            existing.key, request.attachments
                        )
                        payload = CreateIssueResult(
                            created=False,
                            existing_key=existing.key,
                            issue_url=existing.web_url,
                            raw=existing.raw,
                            attachment_errors=errors,
                        )
                        state = "failed" if errors else "duplicate"
                        results.append(
                            (draft.source_id, state, payload, "; ".join(errors))
                        )
                        continue
                    created = create_service.create_issue(request)
                    state = (
                        "failed"
                        if created.attachment_errors
                        else ("created" if created.created else "duplicate")
                    )
                    results.append(
                        (
                            draft.source_id,
                            state,
                            created,
                            "; ".join(created.attachment_errors),
                        )
                    )
                except Exception as exc:
                    results.append((draft.source_id, "failed", None, str(exc)))
            return results

        self._launch_clone("submit", operation)

    @Slot()
    def retryFailedClones(self):
        if self._clone_batch_state != "partial_failed":
            return
        failed = [item for item in self._clone_draft_records if item["state"] == "failed"]
        if failed:
            self._submit_clone_records(failed)

    @Slot()
    def closeCloneBatch(self):
        if self._clone_batch_state == "submitting":
            return
        if self._clone_batch_state == "completed":
            self._reset_clone_batch(cancel_future=True)
        else:
            selected_ids = list(self._clone_selected_ids)
            self._reset_clone_batch(cancel_future=True)
            self._clone_batch_state = "selecting"
            self._clone_selected_ids = selected_ids
        self.changed.emit()

    @Slot(str, str, str)
    def searchCloneUsers(self, issue_id, field_id, query):
        if self._clone_batch_state != "editing" or self._clone_record(issue_id) is None:
            return

        async def operation():
            jira_client, _create_service, _schema_service = self._jira_dependencies()
            if jira_client is None:
                return issue_id, field_id, []
            return issue_id, field_id, jira_client.search_users(query, project_key="SH")

        self._launch_clone("users", operation)

    @Slot(int, int, str, object)
    def _apply_clone_result(self, clone_generation, account_generation, kind, result):
        if (
            self._closed
            or clone_generation != self._clone_generation
            or account_generation != self._generation
        ):
            return
        self._clone_future = None
        if isinstance(result, Exception):
            self._clone_batch_error = str(result)
            if kind == "prepare":
                self._clone_draft_records = []
                self._clone_batch_loaded = 0
                self._clone_batch_state = "prepare_failed"
            elif kind == "submit":
                self._clone_batch_state = "partial_failed"
            self.changed.emit()
            return
        if kind == "prepare":
            records, display_names = result
            self._clone_draft_records = list(records)
            for record in self._clone_draft_records:
                draft = record["draft"]
                for field in draft.fields:
                    account = str(field.value or "") if field.schema.control.value == "user" else ""
                    if account:
                        self._clone_user_options[(draft.source_id, field.field_id)] = [{
                            "value": account,
                            "label": display_names.get(account, account),
                            "avatarUrl": "",
                            "children": [],
                        }]
            self._clone_batch_loaded = len(self._clone_draft_records)
            self._clone_batch_state = "editing"
        elif kind == "users":
            issue_id, field_id, users = result
            existing = self._clone_user_options.get((issue_id, field_id), [])
            fetched = [
                {
                    "value": str(item.get("account") or ""),
                    "label": str(item.get("display_name") or ""),
                    "avatarUrl": str(item.get("avatar_url") or ""),
                    "children": [],
                }
                for item in users
            ]
            fetched_values = {str(item.get("value") or "") for item in fetched}
            self._clone_user_options[(issue_id, field_id)] = fetched + [
                item for item in existing if str(item.get("value") or "") not in fetched_values
            ]
        elif kind == "submit":
            resolved = {}
            for issue_id, state, payload, error in result:
                record = self._clone_record(issue_id)
                if record is None:
                    continue
                record["state"] = state
                record["error"] = error
                if isinstance(payload, CreateIssueResult):
                    record["key"] = payload.issue_key or payload.existing_key
                    record["url"] = payload.issue_url
                if state == "created" and isinstance(payload, CreateIssueResult):
                    resolved[issue_id] = ExistingIssue(
                        key=payload.issue_key,
                        web_url=payload.issue_url,
                    )
                elif state == "duplicate":
                    key = getattr(payload, "existing_key", "") or getattr(payload, "key", "")
                    url = getattr(payload, "issue_url", "") or getattr(payload, "web_url", "")
                    record["key"] = key
                    record["url"] = url
                    resolved[issue_id] = ExistingIssue(key=key, web_url=url)
            if resolved:
                self._issue_controller.record_clone_results(resolved)
            self._clone_batch_loaded = len(result)
            self._clone_batch_state = (
                "partial_failed"
                if any(item["state"] == "failed" for item in self._clone_draft_records)
                else "completed"
            )
        self.changed.emit()

    def _clone_record(self, issue_id):
        issue_id = str(issue_id or "")
        return next(
            (
                item
                for item in self._clone_draft_records
                if item["draft"].source_id == issue_id
            ),
            None,
        )

    def _clone_record_payload(self, record):
        draft = record["draft"]
        fields = []
        for field in draft.fields:
            if (
                not field.schema.required
                and field.field_id != "priority"
                and str(field.schema.name or "").strip().casefold() != "attachment links"
            ):
                continue
            options = self._clone_user_options.get(
                (draft.source_id, field.field_id),
                [_clone_option_payload(item) for item in field.schema.options],
            )
            fields.append(
                {
                    "fieldId": field.field_id,
                    "name": field.schema.name,
                    "required": field.schema.required,
                    "control": field.schema.control.value,
                    "options": options,
                    "value": field.value,
                    "displayValue": next(
                        (str(item.get("label") or item.get("value") or "") for item in options if str(item.get("value") or "") == str(field.value or "")),
                        str(field.value or ""),
                    ),
                    "error": field.error,
                }
            )
        return {
            "issueId": draft.source_id,
            "sourceUrl": draft.source_url,
            "fields": fields,
            "errors": [
                {"fieldId": item.field_id, "message": item.message, "blocking": item.blocking}
                for item in draft.errors
            ],
            "state": record["state"],
            "key": record["key"],
            "url": record["url"],
            "error": record["error"],
        }
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
        self._projects_generation += 1
        self._reset_clone_batch(cancel_future=True)
        if self._login_future is not None:
            self._login_future.cancel()
            self._login_future = None
        if self._data_future is not None:
            self._data_future.cancel()
            self._data_future = None
        for name in ("_projects_future",):
            future = getattr(self, name)
            if future is not None:
                future.cancel()
                setattr(self, name, None)
        self._worker.submit(self._close_flow())
        self._state = AuthState.IDLE
        self._status = self.tr("Redmine sign-in cancelled.")
        self._data_loading = False
        self._projects_loading = False
        self.changed.emit()

    @Slot()
    def close(self):
        if self._closed:
            return
        self._closed = True
        self._generation += 1
        self._data_generation += 1
        self._projects_generation += 1
        self._reset_clone_batch(cancel_future=True)
        if self._login_future is not None:
            self._login_future.cancel()
            self._login_future = None
        if self._data_future is not None:
            self._data_future.cancel()
            self._data_future = None
        for name in ("_projects_future",):
            future = getattr(self, name)
            if future is not None:
                future.cancel()
                setattr(self, name, None)
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


def _clone_option_payload(option):
    return {
        "value": option.value,
        "label": option.label,
        "children": [_clone_option_payload(item) for item in option.children],
    }


async def _download_redmine_attachments(page, attachments):
    downloaded = []
    for attachment in attachments:
        url = str(attachment.download_url or attachment.detail_url or "").strip()
        if not url:
            raise RuntimeError(f"Redmine attachment URL is unavailable: {attachment.filename}")
        response = await page.request.get(url)
        if not response.ok:
            raise RuntimeError(
                f"Redmine attachment download failed: {attachment.filename} "
                f"(HTTP {response.status})"
            )
        downloaded.append(
            CreateIssueAttachment(
                filename=attachment.filename,
                data=await response.body(),
            )
        )
    return tuple(downloaded)


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
