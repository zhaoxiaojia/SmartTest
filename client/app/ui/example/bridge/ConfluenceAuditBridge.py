from __future__ import annotations
import hashlib
import os
from collections import deque
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock, Thread
from zoneinfo import ZoneInfo

from PySide6.QtCore import QObject, Property, QStandardPaths, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from core.tools.common.project_weekly_audit.discovery import (
    PRODUCT_LINES, UNIFIED_SOURCE, ProjectCollectionDiscoveryError,
    discover_project_collection,
)
from core.tools.common.project_weekly_audit.models import (
    AuditExecutionContext, AuditPeriod, ConfluenceProject, ProductLine, ProjectCollection,
    ProjectCollectionFilter,
)
from core.tools.common.project_weekly_audit.project_collection import (
    default_project_filter, filter_projects,
)
from core.tools.common.project_weekly_audit.plans import AuditPlan, AuditPlanStore
from core.tools.common.project_weekly_audit.report import (
    export_project_audit_xlsx,
    export_project_audit_xlsx_by_product_line,
)
from core.tools.common.project_weekly_audit.scheduler import (
    TASK_PREFIX, WindowsAuditScheduler, resolve_audit_launch_command,
)
from core.tools.common.project_weekly_audit.service import ConfluenceAuditService
from support.confluence_integration import (
    ConfluenceClient, ConfluenceClientConfig, ConfluenceDependencyError,
)
from support.logging import smart_log
from support.windows_credentials import WindowsCredentialStore
from support.account_snapshot_cache import AccountScopedSnapshotCache
from support.account_dynamic_source import (
    AccountDynamicSource, DynamicSourceEvent, RefreshState,
)

BUSY = {"discovering", "reviewing"}
PROJECT_SPACE_URL = UNIFIED_SOURCE
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _log_account_id(username):
    normalized = str(username or "").strip().casefold()
    digest = hashlib.sha256(
        ("smarttest-confluence-account:" + normalized).encode("utf-8"),
    ).hexdigest()
    return "acct_" + digest[:12]


def _period_view(period):
    return {
        "start": period.start.isoformat(),
        "end": period.end.isoformat(),
        "displayEnd": period.end.date().isoformat(),
    }

class ConfluenceAuditBridge(QObject):
    viewStateChanged = Signal()
    scheduleRowsChanged = Signal()
    _workerProgress = Signal(object)
    _workerFinished = Signal(object)
    _workerFailed = Signal(object)
    _plansFinished = Signal(object)
    _catalogEvent = Signal(object)
    _filterFinished = Signal(object)
    _filterFailed = Signal(object)
    collectionFilterApplied = Signal(object)

    def __init__(
        self, auth_bridge, *, service_factory=None, history_root=None,
        collection_factory=None, plan_store=None, credential_store=None,
        scheduler=None, executable=None, now_factory=None,
        snapshot_cache=None, dynamic_submit=None,
        filter_submit=None,
    ):
        super().__init__(auth_bridge)
        self._auth = auth_bridge
        self._generation = 0
        self._batch = None
        base = Path(history_root) if history_root else Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)) / "confluence_audit"
        self._service_factory = service_factory or self._make_service
        self._collection_factory = collection_factory or self._discover_collection
        self._plan_store = plan_store or AuditPlanStore(base / "plans")
        self._credentials = credential_store
        self._scheduler = scheduler
        self._launch_command = (
            resolve_audit_launch_command(executable=Path(executable))
            if executable is not None else None
        )
        self._now = now_factory or (lambda: datetime.now().astimezone())
        local_today = self._now().astimezone(SHANGHAI_TZ).date()
        self._manual_start_date = local_today - timedelta(days=local_today.weekday())
        self._manual_end_date = local_today
        cache_root = (
            Path(history_root) / "cache"
            if history_root is not None
            else Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)) / "cache"
        )
        self._snapshot_cache = snapshot_cache or AccountScopedSnapshotCache(cache_root)
        self._dynamic_source = AccountDynamicSource(
            self._snapshot_cache, "confluence", PROJECT_SPACE_URL,
            self._collection_payload, self._collection_from_payload,
            ttl=timedelta(minutes=15), now=lambda: self._now().astimezone(timezone.utc),
            submit=dynamic_submit or self._submit_dynamic,
        )
        self._plan_lock = Lock()
        self._plan_generation = 0
        self._plan_mutations = deque()
        self._plan_worker_running = False
        self._catalog = None
        self._catalog_has_product_lines = False
        self._catalog_account_hash = ""
        self._catalog_refresh_in_flight = False
        self._auth_account_hash = self._snapshot_cache.identity(
            self._current_account_key()
        )
        self._filter_generation = 0
        self._pending_filter = None
        self._pending_audit = False
        self._filter_submit = filter_submit or self._submit_dynamic
        self._schedule_rows = []
        criteria = default_project_filter(self._now(), PROJECT_SPACE_URL)
        self._view = {"state": "idle", "statusText": self.tr("Ready to audit all Confluence projects."),
                      "period": {}, "progress": {"processed": 0, "total": 0}, "summary": {},
                      "manualAuditPeriod": self._manual_period_view(),
                      "projects": [], "selectedProject": "", "findings": [],
                      "sourceLabel": UNIFIED_SOURCE,
                      "exportPath": "",
                      "filter": self._filter_view(criteria),
                      "availableFilterValues": {
                          "years": list(criteria.years),
                          "supportModes": list(criteria.support_modes),
                          "projectStatuses": list(criteria.project_statuses),
                      },
                      "candidateProjects": [], "selectedProjectIds": [],
                      "productLines": self._product_line_rows(PRODUCT_LINES),
                      "selectedProductLineKeys": [],
                      "candidateSections": [], "exportPaths": [],
                      "collectionSummary": {},
                      "catalogStatus": "idle", "catalogStatusText": "",
                      "filterApplying": False,
                      "canStart": True, "canExport": False}
        self._workerProgress.connect(self._on_worker_progress)
        self._workerFinished.connect(self._on_worker_finished)
        self._workerFailed.connect(self._on_worker_failed)
        self._plansFinished.connect(self._on_plans_finished)
        self._catalogEvent.connect(self._on_catalog_event)
        self._filterFinished.connect(self._on_filter_finished)
        self._filterFailed.connect(self._on_filter_failed)
        if hasattr(auth_bridge, "authChanged"):
            auth_bridge.authChanged.connect(self._on_auth_changed)
        if hasattr(auth_bridge, "runtimeCredentialSupplied"):
            auth_bridge.runtimeCredentialSupplied.connect(
                self._on_runtime_credential_supplied,
            )
        if hasattr(auth_bridge, "runtimeCredentialSupplyCancelled"):
            auth_bridge.runtimeCredentialSupplyCancelled.connect(
                self._cancel_pending_filter,
            )
        self.destroyed.connect(lambda *_: self._dynamic_source.close())

    @staticmethod
    def _submit_dynamic(callable_):
        Thread(target=callable_, args=(), daemon=True).start()

    def _make_service(self, username, password):
        base_url = os.getenv("SMARTTEST_CONFLUENCE_BASE_URL", "https://confluence.amlogic.com")
        client = ConfluenceClient(ConfluenceClientConfig(base_url), username, password)
        return ConfluenceAuditService(client)

    def _discover_collection(self, username, password, criteria, progress):
        base_url = os.getenv("SMARTTEST_CONFLUENCE_BASE_URL", "https://confluence.amlogic.com")
        client = ConfluenceClient(ConfluenceClientConfig(base_url), username, password)
        return discover_project_collection(client, criteria, progress)

    @staticmethod
    def _filter_view(criteria):
        return {
            "years": list(criteria.years),
            "supportModes": list(criteria.support_modes),
            "projectStatuses": list(criteria.project_statuses),
        }

    def _criteria(self):
        value = self._view["filter"]
        return ProjectCollectionFilter(
            source_url=UNIFIED_SOURCE,
            years=tuple(int(year) for year in value.get("years", ())),
            support_modes=tuple(str(item) for item in value.get("supportModes", ())),
            project_statuses=tuple(str(item) for item in value.get("projectStatuses", ())),
            included_project_ids=tuple(self._view["selectedProjectIds"]),
            product_line_keys=tuple(self._view["selectedProductLineKeys"]),
        )

    @Slot(object)
    def setFilter(self, filter_value):
        if self._view["state"] in BUSY or not isinstance(filter_value, dict):
            return
        current = self._view["filter"]
        merged = {**current, **filter_value}
        try:
            criteria = ProjectCollectionFilter(
                source_url=UNIFIED_SOURCE,
                years=tuple(dict.fromkeys(int(year) for year in merged.get("years", ()))),
                support_modes=tuple(dict.fromkeys(str(value) for value in merged.get("supportModes", ()))),
                project_statuses=tuple(dict.fromkeys(str(value) for value in merged.get("projectStatuses", ()))),
            )
        except (TypeError, ValueError):
            self._set(statusText=self.tr("Invalid Confluence project filter."))
            return
        self._replace_filter(criteria)

    def _replace_filter(self, criteria, **changes):
        self._set(
            filter=self._filter_view(criteria),
            selectedProjectIds=[],
            candidateProjects=[],
            candidateSections=[],
            collectionSummary={},
            **changes,
        )

    @Slot(object)
    def setSelectedProjects(self, project_ids):
        if self._view["state"] in BUSY:
            return
        values = [] if project_ids is None else list(project_ids)
        selected = list(dict.fromkeys(str(value) for value in values if str(value)))
        self._set(selectedProjectIds=selected)

    @Slot(str, str)
    @Slot(str, int)
    def toggleFilterValue(self, group, value):
        if self._view["state"] in BUSY:
            return
        keys = {
            "years": "years",
            "supportModes": "supportModes",
            "projectStatuses": "projectStatuses",
        }
        key = keys.get(str(group))
        if key is None:
            return
        try:
            normalized = int(value) if key == "years" else str(value)
        except (TypeError, ValueError):
            return
        current = list(self._view["filter"].get(key, ()))
        if normalized in current:
            current.remove(normalized)
        else:
            current.append(normalized)
        self.setFilter({key: current})

    @Slot(str)
    def toggleProject(self, project_id):
        if self._view["state"] in BUSY:
            return
        value = str(project_id)
        candidates = {
            str(row.get("projectIdentity"))
            for row in self._view["candidateProjects"]
        }
        if value not in candidates:
            return
        selected = list(self._view["selectedProjectIds"])
        if value in selected:
            selected.remove(value)
        else:
            selected.append(value)
        self._set(selectedProjectIds=selected)

    @Slot()
    def selectAllProjects(self):
        if self._view["state"] in BUSY:
            return
        self._set(selectedProjectIds=list(dict.fromkeys(
            str(row.get("projectIdentity"))
            for row in self._view["candidateProjects"]
            if row.get("projectIdentity")
        )))

    @Slot()
    def clearSelectedProjects(self):
        if self._view["state"] not in BUSY:
            self._set(selectedProjectIds=[])

    @Slot(str)
    def toggleProductLine(self, product_line_key):
        if self._view["state"] in BUSY:
            return
        key = str(product_line_key)
        available = {str(row.get("key")) for row in self._view["productLines"]}
        if key not in available:
            return
        selected = list(self._view["selectedProductLineKeys"])
        if key in selected:
            selected.remove(key)
        else:
            selected.append(key)
        self._set(
            selectedProductLineKeys=selected,
            **self._candidate_state(selected),
        )

    def _manual_period_view(self):
        return {
            "startDate": self._manual_start_date.isoformat(),
            "endDate": self._manual_end_date.isoformat(),
        }

    @Slot(str)
    def setManualAuditStartDate(self, value):
        self._manual_start_date = datetime.fromisoformat(value).date()
        self._set(manualAuditPeriod=self._manual_period_view())

    @Slot(str)
    def setManualAuditEndDate(self, value):
        self._manual_end_date = datetime.fromisoformat(value).date()
        self._set(manualAuditPeriod=self._manual_period_view())

    def _manual_audit_period(self, now):
        local_now = now.astimezone(SHANGHAI_TZ)
        start = datetime.combine(
            self._manual_start_date, datetime.min.time(), SHANGHAI_TZ,
        )
        end = (
            local_now
            if self._manual_end_date == local_now.date()
            else datetime.combine(
                self._manual_end_date + timedelta(days=1),
                datetime.min.time(), SHANGHAI_TZ,
            )
        )
        return AuditPeriod(start, end)

    @Slot(str)
    def selectAllProjectsForLine(self, product_line_key):
        if self._view["state"] in BUSY:
            return
        key = str(product_line_key)
        line_ids = [
            str(row["projectIdentity"])
            for section in self._view["candidateSections"]
            if str(section.get("key")) == key
            for row in section.get("projects", ())
        ]
        self._set(selectedProjectIds=list(dict.fromkeys(
            [*self._view["selectedProjectIds"], *line_ids]
        )))

    @Slot(str)
    def clearSelectedProjectsForLine(self, product_line_key):
        if self._view["state"] in BUSY:
            return
        prefix = str(product_line_key).casefold() + ":"
        self._set(selectedProjectIds=[
            value for value in self._view["selectedProjectIds"]
            if not str(value).casefold().startswith(prefix)
        ])

    @Slot()
    def initializeCollection(self):
        account = self._current_account_key()
        if not account:
            return
        cached = self._snapshot_cache.load(
            "confluence", self._dynamic_source.source, account,
        )
        if cached is None:
            return
        try:
            collection = self._collection_from_payload(cached.payload)
        except (KeyError, TypeError, ValueError):
            return
        self._on_catalog_event(DynamicSourceEvent(
            RefreshState.CACHED,
            collection,
            0,
            self._snapshot_cache.identity(account),
        ))

    @Slot("QVariantMap")
    def restoreCollectionState(self, saved_state):
        self.initializeCollection()
        if (
            not isinstance(saved_state, dict)
            or not saved_state.get("hasAppliedFilters")
            or self._catalog is None
        ):
            return
        try:
            criteria = ProjectCollectionFilter(
                source_url=UNIFIED_SOURCE,
                years=tuple(int(value) for value in saved_state.get("years", ())),
                support_modes=tuple(
                    str(value) for value in saved_state.get("supportModes", ())
                ),
                project_statuses=tuple(
                    str(value) for value in saved_state.get("projectStatuses", ())
                ),
                product_line_keys=tuple(
                    str(value)
                    for value in saved_state.get("selectedProductLineKeys", ())
                ),
            )
        except (TypeError, ValueError):
            return
        available_lines = {line.key for line in PRODUCT_LINES}
        selected_lines = tuple(
            key for key in criteria.product_line_keys if key in available_lines
        )
        criteria = replace(criteria, product_line_keys=selected_lines)
        candidate_state = self._candidate_state(
            selected_lines, catalog=self._catalog, criteria=criteria,
        )
        candidate_state["selectedProjectIds"] = []
        self._set(
            filter=self._filter_view(criteria),
            selectedProductLineKeys=list(selected_lines),
            **candidate_state,
        )

    @Slot()
    def refreshCollection(self):
        self._open_dynamic_collection(True)

    def _open_dynamic_collection(self, force):
        if self._view["state"] in BUSY:
            return
        if force and self._catalog_refresh_in_flight:
            return
        credentials = self._transient_credentials()
        if credentials is None:
            return
        if force:
            self._catalog_refresh_in_flight = True
            self._catalog = None
            self._catalog_account_hash = ""
            self._set(
                availableFilterValues={
                    "years": [], "supportModes": [], "projectStatuses": [],
                },
            )
        catalog_criteria = ProjectCollectionFilter(
            source_url=UNIFIED_SOURCE, years=(),
        )
        smart_log(
            "Project catalog discovery started",
            domain="confluence", source="ConfluenceAuditBridge",
            extra={
                "account_id": _log_account_id(credentials[0]),
                "requested_years": [],
            },
        )
        username, password = credentials
        self._dynamic_source.open(
            username,
            lambda: self._collection_factory(
                username, password, catalog_criteria, lambda *_: None,
            ),
            self._catalogEvent.emit, force=bool(force),
        )

    @Slot(object)
    def _on_catalog_event(self, event):
        current_hash = self._snapshot_cache.identity(self._current_account_key())
        if event.account_hash != current_hash:
            return
        state = event.state
        if state in {RefreshState.UPDATED, RefreshState.REFRESH_FAILED}:
            self._catalog_refresh_in_flight = False
        status_text = {
            RefreshState.CACHED: self.tr("Cached Project Space data is ready."),
            RefreshState.FIRST_LOADING: self.tr("Loading Project Space for the first time."),
            RefreshState.REFRESHING: self.tr("Refreshing Project Space in the background."),
            RefreshState.UPDATED: self.tr("Project Space updated."),
            RefreshState.REFRESH_FAILED: (
                self.tr("Refresh failed; using cached Project Space data.")
                if event.snapshot is not None
                else self.tr("Project Space could not be loaded. Check the current account password and network access, then retry.")
            ),
        }[state]
        if state is RefreshState.REFRESH_FAILED and event.error_kind == "dependency":
            status_text = self.tr(
                "Confluence support is unavailable. Install project dependencies in the project .venv.",
            )
        self._set(
            catalogStatus=state.value,
            catalogStatusText=status_text,
        )
        if (
            state is RefreshState.REFRESH_FAILED
            and event.snapshot is None
            and self._view["state"] not in BUSY
        ):
            self._set(state="failed", statusText=status_text, canStart=True)
        if (
            event.snapshot is not None
            and state in {RefreshState.CACHED, RefreshState.UPDATED}
            and not (
                state is RefreshState.CACHED
                and self._catalog_refresh_in_flight
            )
        ):
            self._on_collection_finished({
                "collection": event.snapshot,
                "accountHash": event.account_hash,
                "showCandidates": False,
            })

    @Slot(object)
    def _on_collection_finished(self, payload):
        collection = payload["collection"]
        account_hash = str(payload.get("accountHash") or "")
        if account_hash != self._snapshot_cache.identity(self._current_account_key()):
            return
        had_catalog = self._catalog is not None
        self._catalog_has_product_lines = bool(
            collection.product_lines
            or any(project.space_key for project in collection.projects)
        )
        collection = replace(collection, product_lines=PRODUCT_LINES)
        self._catalog = collection
        self._catalog_account_hash = account_hash
        projects = list(collection.projects)
        smart_log(
            "Project catalog discovery completed",
            domain="confluence", source="ConfluenceAuditBridge",
            extra={
                "account_id": _log_account_id(self._current_account_key()),
                "catalog_count": len(projects),
                "year_count": len({
                    year for row in projects
                    for year in (row.matching_years or (row.year,))
                }),
            },
        )
        project_years = sorted({
            year for row in projects
            for year in (row.matching_years or (row.year,))
        })
        options = {
            "years": list(collection.visible_years) or project_years,
            "supportModes": self._canonical_options(row.support_mode for row in projects),
            "projectStatuses": self._canonical_options(row.project_status for row in projects),
        }
        current = self._view["filter"]
        refreshed_filter = {
            "years": self._available_selection(current["years"], options["years"]),
            "supportModes": self._available_selection(
                current["supportModes"], options["supportModes"],
            ),
            "projectStatuses": self._available_selection(
                current["projectStatuses"], options["projectStatuses"],
            ),
        }
        product_lines = self._product_line_rows(PRODUCT_LINES)
        available_line_keys = {line["key"] for line in product_lines}
        selected_line_keys = [
            value for value in self._view["selectedProductLineKeys"]
            if value in available_line_keys
        ]
        if not had_catalog and not selected_line_keys:
            selected_line_keys = [line["key"] for line in product_lines]
        visible = filter_projects(projects, ProjectCollectionFilter(
            UNIFIED_SOURCE, tuple(refreshed_filter["years"]),
            tuple(refreshed_filter["supportModes"]),
            tuple(refreshed_filter["projectStatuses"]),
            product_line_keys=tuple(selected_line_keys),
        ))
        if not selected_line_keys:
            visible = replace(visible, projects=())
        candidate_rows = (
            self._candidate_rows(visible.projects)
            if bool(payload.get("showCandidates"))
            else []
        )
        candidate_ids = {row["projectIdentity"] for row in candidate_rows}
        selected = [
            value for value in self._view["selectedProjectIds"]
            if value in candidate_ids
        ]
        error_count = sum(collection.discovery_errors.values())
        changes = dict(
            statusText=(
                self.tr(
                    "Project Space options refreshed with {count} inaccessible or unreadable project pages.",
                ).format(count=error_count)
                if error_count else self.tr("Project Space filter options refreshed.")
            ),
            filter=refreshed_filter,
            productLines=product_lines,
            selectedProductLineKeys=selected_line_keys,
            availableFilterValues=options,
        )
        if bool(payload.get("showCandidates")):
            changes.update(
                candidateProjects=candidate_rows,
                selectedProjectIds=selected,
                candidateSections=self._candidate_sections(
                    visible.projects,
                    tuple(
                        line for line in PRODUCT_LINES
                        if line.key in selected_line_keys
                    ),
                ),
                collectionSummary={
                    "candidateCount": len(candidate_rows),
                    "excludedCounts": dict(visible.excluded_counts),
                },
            )
        self._set(**changes)

    @Slot()
    def applyCollectionFilter(self):
        if self._view["state"] in BUSY or self._view["filterApplying"]:
            return
        if self._pending_filter is not None:
            return
        account_hash = self._snapshot_cache.identity(self._current_account_key())
        criteria = self._criteria()
        if not criteria.product_line_keys:
            self._set(statusText=self.tr("Select at least one product line."))
            return
        self._pending_filter = {
            "accountHash": account_hash,
            "criteria": criteria,
        }
        acquisition = self._auth.acquireRuntimeCredential()
        status = str(acquisition.get("status") or "")
        if status != "ready":
            self._set(statusText=(
                self.tr("Enter the current account password to continue applying filters.")
                if status in {"password_required", "pending"}
                else self.tr("Sign in to continue applying filters.")
            ))
            return
        self._start_pending_filter()

    def _start_pending_filter(self):
        pending = self._pending_filter
        credentials = self._transient_credentials()
        if pending is None or credentials is None:
            self._pending_filter = None
            return
        if pending["accountHash"] != self._snapshot_cache.identity(
            self._current_account_key()
        ):
            self._pending_filter = None
            return
        self._pending_filter = None
        account_hash = pending["accountHash"]
        criteria = pending["criteria"]
        self._filter_generation += 1
        generation = self._filter_generation
        self._set(filterApplying=True)
        username, password = credentials
        self._filter_submit(lambda: self._discover_for_filter(
            generation, account_hash, username, password, criteria,
        ))

    @Slot()
    def _on_runtime_credential_supplied(self):
        if self._pending_filter is not None:
            self._start_pending_filter()
            return
        if self._pending_audit:
            self._pending_audit = False
            self.startAudit()

    @Slot()
    def _cancel_pending_filter(self):
        self._pending_filter = None
        self._pending_audit = False
        self._set(filterApplying=False)

    def _discover_for_filter(
        self, generation, account_hash, username, password, criteria,
    ):
        try:
            collection = self._collection_factory(
                username, password, criteria, lambda *_: None,
            )
        except Exception as exc:
            self._filterFailed.emit({
                "generation": generation,
                "accountHash": account_hash,
                "kind": self._failure_kind(exc),
                "detail": (
                    str(exc) if isinstance(exc, ProjectCollectionDiscoveryError) else ""
                ),
            })
            return
        self._filterFinished.emit({
            "generation": generation,
            "accountHash": account_hash,
            "criteria": criteria,
            "collection": collection,
        })

    @Slot(object)
    def _on_filter_finished(self, payload):
        if not self._active_filter_payload(payload):
            return
        criteria = payload["criteria"]
        collection = payload["collection"]
        try:
            state = self._candidate_state(
                criteria.product_line_keys, catalog=collection, criteria=criteria,
            )
            smart_log(
                "Project catalog filter applied",
                domain="confluence", source="ConfluenceAuditBridge",
                extra={
                    "account_id": _log_account_id(self._current_account_key()),
                    "source_url": criteria.source_url,
                    "catalog_count": len(collection.projects),
                    "years": list(criteria.years),
                    "support_modes": list(criteria.support_modes),
                    "project_statuses": list(criteria.project_statuses),
                    "filtered_project_count": state["collectionSummary"]["candidateCount"],
                    "candidate_count": state["collectionSummary"]["candidateCount"],
                    "excluded_counts": state["collectionSummary"]["excludedCounts"],
                },
            )
            self._set(**state, statusText=self.tr("Project filters applied."))
            self.collectionFilterApplied.emit({
                "selectedProductLineKeys": list(criteria.product_line_keys),
                "years": list(criteria.years),
                "supportModes": list(criteria.support_modes),
                "projectStatuses": list(criteria.project_statuses),
            })
        finally:
            self._set(filterApplying=False)

    @Slot(object)
    def _on_filter_failed(self, payload):
        if not self._active_filter_payload(payload):
            return
        smart_log(
            "Confluence project filter failed",
            domain="confluence", source="ConfluenceAuditBridge",
            level="warning",
            extra={
                "account_id": _log_account_id(self._current_account_key()),
                "error_kind": str(payload.get("kind") or "audit"),
            },
        )
        messages = {
            "auth": self.tr("Confluence authentication failed. Check the current account password."),
            "network": self.tr("Confluence network access failed. Check the network or VPN, then try again."),
            "dependency": self.tr(
                "Confluence support is missing. Start SmartTest with the project .venv "
                "or run support/scripts/script-init-venv.py.",
            ),
            "audit": self.tr("Confluence project refresh failed. Review the application log, then try again."),
        }
        self._set(
            filterApplying=False,
            statusText=(
                str(payload.get("detail") or "")
                if payload.get("kind") == "audit" and payload.get("detail")
                else messages.get(payload.get("kind"), messages["audit"])
            ),
        )

    def _active_filter_payload(self, payload):
        return (
            int(payload.get("generation", -1)) == self._filter_generation
            and str(payload.get("accountHash") or "")
            == self._snapshot_cache.identity(self._current_account_key())
        )

    def _candidate_state(self, selected_line_keys, *, catalog=None, criteria=None):
        catalog = catalog if catalog is not None else self._catalog
        already_filtered = criteria is not None
        selected_keys = tuple(dict.fromkeys(str(key) for key in selected_line_keys))
        has_product_lines = bool(
            catalog and (
                catalog.product_lines
                or any(project.space_key for project in catalog.projects)
            )
        )
        if catalog is None or (catalog.product_lines and not selected_keys):
            return {
                "candidateProjects": [], "candidateSections": [],
                "selectedProjectIds": [],
                "collectionSummary": {"candidateCount": 0, "excludedCounts": {}},
            }
        if criteria is None:
            value = self._view["filter"]
            criteria = ProjectCollectionFilter(
                UNIFIED_SOURCE,
                tuple(int(year) for year in value.get("years", ())),
                tuple(str(item) for item in value.get("supportModes", ())),
                tuple(str(item) for item in value.get("projectStatuses", ())),
                product_line_keys=(
                    selected_keys if has_product_lines else ()
                ),
            )
        effective_criteria = replace(
            criteria,
            product_line_keys=(selected_keys if has_product_lines else ()),
        )
        collection = filter_projects(catalog.projects, effective_criteria)
        if already_filtered:
            excluded = dict(catalog.excluded_counts)
            for key, count in collection.excluded_counts.items():
                excluded[key] = excluded.get(key, 0) + count
            collection = replace(
                collection,
                discovery_errors=dict(catalog.discovery_errors),
                excluded_counts=excluded,
            )
        candidate_rows = self._candidate_rows(collection.projects)
        valid_ids = {row["projectIdentity"] for row in candidate_rows}
        selected_projects = [
            value for value in self._view["selectedProjectIds"]
            if value in valid_ids
        ]
        selected_set = set(selected_keys)
        selected_lines = (
            tuple(line for line in PRODUCT_LINES if line.key in selected_set)
            if has_product_lines else ()
        )
        return {
            "candidateProjects": candidate_rows,
            "candidateSections": self._candidate_sections(
                collection.projects, selected_lines,
            ),
            "selectedProjectIds": selected_projects,
            "collectionSummary": {
                "candidateCount": len(candidate_rows),
                "excludedCounts": dict(collection.excluded_counts),
            },
        }

    @staticmethod
    def _candidate_rows(projects):
        return [{
            "projectId": row.project_id,
            "projectIdentity": row.project_identity,
            "name": row.name,
            "displayName": row.display_name or row.name,
            "year": row.year,
            "supportMode": row.support_mode, "projectStatus": row.project_status,
            "projectOwner": row.project_owner, "url": row.status_url,
            "matchingYears": list(row.matching_years or (row.year,)),
        } for row in projects]

    @classmethod
    def _candidate_sections(cls, projects, product_lines):
        rows = cls._candidate_rows(projects)
        return [{
            "key": line.key,
            "displayName": line.display_name,
            "projects": [
                row for row in rows
                if str(row["projectIdentity"]).casefold().startswith(
                    line.key.casefold() + ":"
                )
            ],
        } for line in product_lines]

    @staticmethod
    def _product_line_rows(product_lines):
        return [{
            "key": line.key,
            "displayName": line.display_name,
        } for line in product_lines]

    @staticmethod
    def _collection_payload(collection):
        return {
            "adapterVersion": 5,
            "collectionId": collection.collection_id,
            "name": collection.name,
            "discoveredAt": collection.discovered_at.isoformat(),
            "filter": {
                "sourceUrl": collection.filter.source_url,
                "years": list(collection.filter.years),
                "supportModes": list(collection.filter.support_modes),
                "projectStatuses": list(collection.filter.project_statuses),
                "currentStages": list(collection.filter.current_stages),
                "includedProjectIds": list(collection.filter.included_project_ids),
                "productLineKeys": list(collection.filter.product_line_keys),
            },
            "visibleYears": list(collection.visible_years),
            "discoveryErrors": dict(collection.discovery_errors),
            "excludedCounts": dict(collection.excluded_counts),
            "projects": [{
                "year": row.year, "project_id": row.project_id, "name": row.name,
                "status_page_id": row.status_page_id, "status_url": row.status_url,
                "home_url": row.home_url, "project_status": row.project_status,
                "current_stage": row.current_stage, "support_mode": row.support_mode,
                "project_owner": row.project_owner, "attributes": dict(row.attributes),
                "display_name": row.display_name,
                "matching_years": list(row.matching_years),
                "space_key": row.space_key,
                "page_identity": row.page_identity,
            } for row in collection.projects],
            "productLines": [{
                "key": line.key, "source_url": line.source_url,
                "display_name": line.display_name,
            } for line in collection.product_lines],
        }

    @staticmethod
    def _collection_from_payload(value):
        if not isinstance(value, dict) or value.get("adapterVersion") != 5:
            raise ValueError("Unsupported Confluence collection snapshot")
        filter_value = value["filter"]
        discovered_at = datetime.fromisoformat(value["discoveredAt"])
        if discovered_at.tzinfo is None:
            raise ValueError("Collection discovery timestamp must be timezone-aware")
        criteria = ProjectCollectionFilter(
            UNIFIED_SOURCE, tuple(filter_value["years"]),
            tuple(filter_value["supportModes"]), tuple(filter_value["projectStatuses"]),
            tuple(filter_value["currentStages"]),
            tuple(filter_value["includedProjectIds"]),
            tuple(filter_value.get("productLineKeys", ())),
        )
        return ProjectCollection(
            str(value["collectionId"]), str(value["name"]), criteria,
            discovered_at,
            tuple(ConfluenceProject(
                **{
                    **row,
                    "matching_years": tuple(row.get("matching_years", ())),
                },
            ) for row in value["projects"]),
            dict(value["excludedCounts"]),
            tuple(value["visibleYears"]), dict(value.get("discoveryErrors", {})),
            tuple(ProductLine(**row) for row in value.get("productLines", ())),
        )

    @staticmethod
    def _available_selection(selected, available):
        available_values = {str(value) for value in available}
        return [
            value for value in selected if str(value) in available_values
        ]

    @staticmethod
    def _canonical_options(values):
        canonical = {}
        for value in values:
            clean = str(value or "").strip()
            if clean:
                canonical.setdefault(clean.casefold(), clean.upper())
        return sorted(canonical.values())

    @staticmethod
    def _account_key(username):
        return str(username or "").strip().casefold()

    def _current_account_key(self):
        return self._account_key(self._auth.currentUsername())

    def _transient_credentials(self):
        username, password = self._auth.transientCredential()
        if not (
            self._auth.isAuthenticated()
            and username and password
        ):
            self._set(
                state="failed",
                statusText=self.tr("Enter the current account password to audit Confluence projects."),
            )
            return None
        return str(username), str(password)

    @Slot()
    def startAudit(self):
        if self._view["state"] in BUSY:
            return
        if not self._view["selectedProductLineKeys"]:
            self._set(statusText=self.tr("Select at least one product line before starting the audit."))
            return
        if (
            self._view["candidateProjects"]
            and not self._view["selectedProjectIds"]
        ):
            self._set(statusText=self.tr("Select at least one project before starting the audit."))
            return
        acquisition = self._auth.acquireRuntimeCredential()
        status = str(acquisition.get("status") or "")
        if status != "ready":
            self._pending_audit = True
            self._set(statusText=(
                self.tr("Enter the current account password to audit Confluence projects.")
                if status in {"password_required", "pending"}
                else self.tr("Sign in to audit Confluence projects.")
            ))
            return
        self._pending_audit = False
        credentials = self._transient_credentials()
        if credentials is None:
            return
        username, password = credentials
        period = self._manual_audit_period(self._now())
        if period.start >= period.end:
            self._set(statusText=self.tr(
                "The audit start time must be earlier than the end time."
            ))
            return
        self._generation += 1
        generation = self._generation
        self._batch = None
        self._set(state="discovering", statusText=self.tr("Discovering all A-level development projects..."),
                  period=_period_view(period),
                  progress={"processed": 0, "total": 0}, summary={}, projects=[], findings=[], exportPath="")
        smart_log(
            "Project weekly audit started",
            domain="confluence",
            source="ConfluenceAuditBridge",
        )
        Thread(target=self._run, args=(generation, str(username), str(password), period), daemon=True).start()

    def _run(self, generation, username, password, period):
        try:
            service = self._service_factory(username, password)
            criteria = self._criteria()
            batch = service.run(
                criteria,
                period,
                AuditExecutionContext("manual"),
                lambda stage, done, total: self._workerProgress.emit(
                    (generation, stage, done, total),
                ),
            )
            self._workerFinished.emit({"generation": generation, "batch": batch})
        except Exception as exc:
            kind = self._failure_kind(exc)
            smart_log(
                "Project weekly audit failed (kind=%s)",
                kind,
                level="error",
                domain="confluence",
                source="ConfluenceAuditBridge",
            )
            self._workerFailed.emit({"generation": generation, "kind": kind})

    @Slot(str)
    def selectProject(self, project_id):
        self._set(selectedProject=str(project_id), findings=self._finding_rows(str(project_id)))

    @Slot()
    def exportReport(self):
        if not self._batch:
            return
        try:
            root = Path(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) or Path.home() / "Downloads")
            if self._batch.product_lines:
                paths = export_project_audit_xlsx_by_product_line(
                    self._batch, root,
                )
            else:
                paths = [export_project_audit_xlsx(
                    self._batch,
                    root / f"project_weekly_audit_{self._batch.id}.xlsx",
                )]
            path = paths[0]
            self._set(
                exportPath=str(path),
                exportPaths=[str(item) for item in paths],
                statusText=self.tr("Confluence audit Excel workbook exported."),
            )
        except Exception:
            self._set(
                statusText=self.tr(
                    "Failed to export the Confluence audit Excel workbook.",
                ),
            )

    @Slot()
    def exportExcel(self):
        self.exportReport()

    @Slot(result=bool)
    def openReportDirectory(self):
        report = Path(str(self._view.get("exportPath") or ""))
        if not report.is_file():
            self._set(statusText=self.tr("Exported report file was not found."))
            return False
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(report.parent)))
        if not opened:
            self._set(statusText=self.tr("Failed to open the report directory."))
        return bool(opened)

    def _credential_store(self):
        if self._credentials is None:
            self._credentials = WindowsCredentialStore()
        return self._credentials

    def _scheduler_owner(self):
        if self._scheduler is None:
            self._scheduler = WindowsAuditScheduler(
                launch_command=self._launch_command,
            )
        return self._scheduler

    @Slot(str, str)
    def saveWeeklyPlan(self, plan_id, name):
        credentials = self._transient_credentials()
        if credentials is None:
            return
        criteria = self._criteria()
        generation = self._next_plan_generation()
        self._enqueue_plan_mutation((
            generation, "save",
            (str(plan_id), str(name), credentials[0], credentials[1], criteria),
        ))

    @Slot()
    def enableWeeklyPlan(self):
        if not self._view["collectionSummary"].get("candidateCount"):
            self._set(statusText=self.tr("Apply project filters before enabling the weekly plan."))
            return
        if not self._view["selectedProjectIds"]:
            self._set(statusText=self.tr("Select at least one project before enabling the weekly plan."))
            return
        self.saveWeeklyPlan("confluence-weekly-audit", self.tr("Confluence weekly project audit"))

    def _save_weekly_plan(
        self, generation, plan_id, name, username, password, criteria,
    ):
        try:
            now = self._now()
            try:
                previous = self._plan_store.load(plan_id)
            except FileNotFoundError:
                previous = None
            plan = AuditPlan(
                plan_id=plan_id,
                name=name,
                collection_filter=criteria,
                enabled=True,
                credential_ref=plan_id,
                task_name=TASK_PREFIX + plan_id,
                created_at=now if previous is None else previous.created_at,
                updated_at=now,
                last_run_at=None if previous is None else previous.last_run_at,
                last_status="" if previous is None else previous.last_status,
                last_report_path="" if previous is None else previous.last_report_path,
            )
            self._credential_store().write(plan_id, username, password)
            self._plan_store.save(plan)
            self._scheduler_owner().upsert(plan)
            self._emit_plan_rows(generation)
        except Exception:
            self._plansFinished.emit({"generation": generation, "kind": "failed"})

    @Slot(str, bool)
    def setPlanEnabled(self, plan_id, enabled):
        generation = self._next_plan_generation()
        self._enqueue_plan_mutation((
            generation, "enable", (str(plan_id), bool(enabled)),
        ))

    def _set_plan_enabled(self, generation, plan_id, enabled):
        try:
            plan = self._plan_store.load(plan_id)
            updated = replace(plan, enabled=enabled, updated_at=self._now())
            self._plan_store.save(updated)
            self._scheduler_owner().set_enabled(plan_id, enabled)
            self._emit_plan_rows(generation)
        except Exception:
            self._plansFinished.emit({"generation": generation, "kind": "failed"})

    @Slot()
    def refreshPlans(self):
        generation = self._next_plan_generation()
        self._enqueue_plan_mutation((generation, "refresh", ()))

    def _refresh_plans(self, generation):
        try:
            self._emit_plan_rows(generation)
        except Exception:
            self._plansFinished.emit({"generation": generation, "kind": "failed"})

    def _next_plan_generation(self):
        with self._plan_lock:
            self._plan_generation += 1
            return self._plan_generation

    def _enqueue_plan_mutation(self, operation):
        start_worker = False
        with self._plan_lock:
            self._plan_mutations.append(operation)
            if not self._plan_worker_running:
                self._plan_worker_running = True
                start_worker = True
        if start_worker:
            Thread(
                target=self._drain_plan_mutations, args=(), daemon=True,
            ).start()

    def _drain_plan_mutations(self):
        while True:
            with self._plan_lock:
                if not self._plan_mutations:
                    self._plan_worker_running = False
                    return
                generation, kind, arguments = self._plan_mutations.popleft()
            if kind == "save":
                self._save_weekly_plan(generation, *arguments)
            elif kind == "enable":
                self._set_plan_enabled(generation, *arguments)
            else:
                self._refresh_plans(generation)

    def _emit_plan_rows(self, generation):
        plans = self._plan_store.list()
        states = self._scheduler_owner().list(plans)
        state_by_id = {row.plan_id: row for row in states}
        configured_ids = {plan.plan_id for plan in plans}
        rows = [
            self._plan_row(plan, state_by_id.get(plan.plan_id))
            for plan in plans
        ]
        rows.extend(
            self._plan_row(None, machine)
            for machine in states
            if machine.plan_id not in configured_ids
        )
        self._plansFinished.emit({
            "generation": generation, "kind": "refreshed", "plans": rows,
        })

    def _plan_row(self, plan, machine):
        return {
            "provider": "confluence",
            "planId": plan.plan_id if plan else machine.plan_id,
            "businessTitle": self.tr("Project Weekly Audit"),
            "title": (
                plan.name if plan else self.tr("Confluence weekly project audit")
            ),
            "collectionSummary": (
                self._plan_collection_summary(plan.collection_filter)
                if plan else ""
            ),
            "enabled": bool(machine.enabled) if machine else False,
            "registered": bool(machine.registered) if machine else False,
            "reconciliation": machine.reconciliation if machine else "task_missing",
            "nextRunAt": (
                machine.next_run_at.isoformat()
                if machine and machine.next_run_at else ""
            ),
            "lastRunAt": (
                machine.last_run_at.isoformat()
                if machine and machine.last_run_at else
                plan.last_run_at.isoformat() if plan and plan.last_run_at else ""
            ),
            "lastResultCode": (
                machine.last_result_code
                if machine and machine.last_result_code is not None else None
            ),
            "lastStatus": plan.last_status if plan else "",
            "lastReportPath": plan.last_report_path if plan else "",
            "targetToolId": "confluence_audit",
        }

    @Property("QVariantList", notify=scheduleRowsChanged)
    def scheduleRows(self):
        return list(self._schedule_rows)

    def _plan_collection_summary(self, criteria):
        any_value = self.tr("Any")
        template = self.tr(
            "Years: {years}; support modes: {support_modes}; "
            "project statuses: {project_statuses}; "
            "selected projects: {selected_count}",
        )
        return template.format(
            years=", ".join(str(value) for value in criteria.years) or any_value,
            support_modes=", ".join(criteria.support_modes) or any_value,
            project_statuses=", ".join(criteria.project_statuses) or any_value,
            selected_count=len(criteria.included_project_ids),
        )

    @Slot(object)
    def _on_plans_finished(self, payload):
        if int(payload.get("generation", -1)) != self._plan_generation:
            return
        kind = payload.get("kind")
        if kind == "refreshed":
            self._schedule_rows = list(payload["plans"])
            self.scheduleRowsChanged.emit()
        else:
            self._set(statusText=self.tr("Failed to update weekly audit plans."))

    @Slot(object)
    def _on_worker_progress(self, payload):
        generation, stage, done, total = payload
        if generation == self._generation:
            discovering = stage == "discovering"
            state = "discovering" if discovering else "reviewing"
            self._set(state=state,
                      statusText=(self.tr("Discovering project pages...")
                                  if discovering else self.tr("Auditing Confluence project content...")),
                      progress={"processed": int(done), "total": int(total)})
            if discovering and total and done == total:
                smart_log(
                    "Project weekly audit candidates hydrated (count=%s)",
                    int(total),
                    domain="confluence",
                    source="ConfluenceAuditBridge",
                )

    @Slot(object)
    def _on_worker_finished(self, payload):
        if int(payload.get("generation", -1)) != self._generation:
            return
        self._batch = payload["batch"]
        smart_log(
            "Project weekly audit completed (eligible=%s)",
            len(self._batch.projects),
            domain="confluence",
            source="ConfluenceAuditBridge",
        )
        self._apply_batch(self._batch)

    def _apply_batch(self, batch):
        actionable = {"not_updated", "invalid_format"}
        projects = [
            {
                "projectId": row.project.project_id,
                "name": row.project.name,
                "status": row.status.value,
                "findingCount": sum(finding.status.value in actionable for finding in row.findings),
            }
            for row in batch.projects
            if any(finding.status.value in actionable for finding in row.findings)
        ]
        selected = projects[0]["projectId"] if projects else ""
        no_reviewed = not batch.projects
        no_follow_up = bool(batch.projects) and not projects
        status_text = (
            self.tr("No eligible A-level development projects were found.")
            if no_reviewed else
            self.tr("Review completed. No projects require follow-up.")
            if no_follow_up else
            self.tr("Confluence audit completed.")
        )
        self._set(state="empty" if no_reviewed else "completed",
                  statusText=status_text,
                  period=_period_view(batch.period),
                  progress={"processed": len(batch.projects), "total": len(batch.projects)},
                  summary={"reviewedCount": len(batch.projects),
                           "followUpCount": len(projects),
                           "invalidFormatCount": sum(row["status"] == "invalid_format" for row in projects),
                           "notUpdatedCount": sum(row["status"] == "not_updated" for row in projects),
                           "updatedCount": sum(row.status.value == "updated" for row in batch.projects)},
                  projects=projects, selectedProject=selected,
                  findings=self._finding_rows(selected, batch))

    def _finding_rows(self, project_id, batch=None):
        current = batch or self._batch
        if not current:
            return []
        result = []
        for row in current.projects:
            if row.project.project_id != project_id:
                continue
            for finding in row.findings:
                if finding.status.value not in {"not_updated", "invalid_format"}:
                    continue
                result.append({
                    "pageTitle": finding.page_title, "ruleId": finding.rule_id,
                    "status": finding.status.value, "reason": finding.reason,
                    "explanation": finding.explanation,
                    "url": finding.page_url,
                })
        return result

    @Slot(object)
    def _on_worker_failed(self, payload):
        if int(payload.get("generation", -1)) == self._generation:
            kind = str(payload.get("kind") or "audit")
            messages = {
                "auth": self.tr("Confluence authentication failed. Check the current account password."),
                "network": self.tr("Confluence network access failed. Check the network or VPN, then try again."),
                "dependency": self.tr(
                    "Confluence support is missing. Start SmartTest with the project .venv "
                    "or run support/scripts/script-init-venv.py.",
                ),
                "audit": self.tr("Confluence audit failed. Review the application log, then try again."),
            }
            self._set(state="failed", statusText=messages.get(kind, messages["audit"]))

    @staticmethod
    def _failure_kind(exc):
        if isinstance(exc, ConfluenceDependencyError):
            return "dependency"
        if isinstance(exc, PermissionError):
            return "auth"
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in {401, 403}:
            return "auth"
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return "network"
        return "audit"

    @Slot()
    def _on_auth_changed(self):
        next_hash = self._snapshot_cache.identity(self._current_account_key())
        if self._auth.isAuthenticated() and next_hash == self._auth_account_hash:
            return
        self._auth_account_hash = next_hash
        self._dynamic_source.invalidate()
        self._catalog_refresh_in_flight = False
        self._filter_generation += 1
        if self._pending_filter and (
            not self._auth.isAuthenticated()
            or self._pending_filter["accountHash"]
            != self._snapshot_cache.identity(self._current_account_key())
        ):
            self._pending_filter = None
        self._generation += 1
        self._batch = None
        self._catalog = None
        self._catalog_has_product_lines = False
        self._catalog_account_hash = ""
        criteria = default_project_filter(self._now(), PROJECT_SPACE_URL)
        self._set(
            state="idle",
            statusText=self.tr(
                "The login changed. Click Refresh filter options to update Project Space data.",
            ),
            filter=self._filter_view(criteria),
            availableFilterValues={
                "years": list(criteria.years),
                "supportModes": list(criteria.support_modes),
                "projectStatuses": list(criteria.project_statuses),
            },
            candidateProjects=[], selectedProjectIds=[],
            candidateSections=[],
            productLines=self._product_line_rows(PRODUCT_LINES),
            selectedProductLineKeys=[],
            collectionSummary={}, summary={}, projects=[], findings=[],
            filterApplying=False, canExport=False,
        )
        if self._auth.isAuthenticated() and self._auth.hasCredential():
            self.initializeCollection()

    def _set(self, **changes):
        state = str(changes.get("state", self._view["state"]))
        self._view = {**self._view, **changes, "canStart": state not in BUSY,
                      "canExport": self._batch is not None and state == "completed"}
        self.viewStateChanged.emit()
    viewState = Property("QVariantMap", lambda self: self._view, notify=viewStateChanged)
