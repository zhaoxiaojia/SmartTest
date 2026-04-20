from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock, Thread
import time
from typing import Any, Callable
from urllib.parse import quote

from PySide6.QtCore import QObject, Property, QCoreApplication, QT_TRANSLATE_NOOP, QStandardPaths, Signal, Slot
from PySide6.QtGui import QGuiApplication

from AI import AmlogicAIProvider, JiraAIAnalysisService
from jira import JiraBasicAuth, JiraClient, JiraClientConfig, JiraFieldMetadataCache, JiraIssueService
from jira.fields import FieldRegistry, FieldSpec
from example.bridge.AuthBridge import AuthBridge
from example.helper.TranslateHelper import TranslateHelper

JIRA_BASE_URL = os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
_MAX_DISPLAY_ISSUES = 50

_PROJECT_OPTION_IDS = (
    "all_supported_projects",
    "rk",
    "tv",
    "ott",
    "iptv",
    "gh",
    "sh",
)

_BOARD_OPTION_IDS = (
    "open_work",
    "ready_for_test",
    "closed_bugs",
)

_TIMEFRAME_OPTION_IDS = (
    "last_7_days",
    "last_30_days",
    "last_90_days",
    "this_year",
)

_STATUS_OPTION_IDS = (
    "open",
    "in_progress",
    "blocked",
    "ready_for_test",
    "verified",
    "resolved",
    "closed",
)

_PRIORITY_OPTION_IDS = (
    "highest",
    "critical",
    "high",
    "medium",
    "low",
)

_ISSUE_TYPE_OPTION_IDS = (
    "bug",
    "task",
    "story",
    "improvement",
)

# Register dynamic bridge strings so `pyside6-lupdate` can extract them even
# when they are stored first and translated later during rendering.
_JIRA_BRIDGE_TRANSLATION_MARKERS = (
    QT_TRANSLATE_NOOP("JiraBridge", "Ready"),
    QT_TRANSLATE_NOOP("JiraBridge", "Run a Jira query to get a live AI summary."),
    QT_TRANSLATE_NOOP(
        "JiraBridge",
        "Signed-in Jira access is ready. Ask in natural language to search issues and summarize risk.",
    ),
    QT_TRANSLATE_NOOP("JiraBridge", "Workspace ready"),
    QT_TRANSLATE_NOOP("JiraBridge", "Session cleared. Ask a new Jira question when ready."),
    QT_TRANSLATE_NOOP("JiraBridge", "Reset"),
    QT_TRANSLATE_NOOP("JiraBridge", "Jira request failed. Check the connection message above and sign in again if needed."),
    QT_TRANSLATE_NOOP("JiraBridge", "Error"),
    QT_TRANSLATE_NOOP("JiraBridge", "All Supported Projects"),
    QT_TRANSLATE_NOOP("JiraBridge", "Open Work"),
    QT_TRANSLATE_NOOP("JiraBridge", "Ready for Test"),
    QT_TRANSLATE_NOOP("JiraBridge", "Closed Bugs"),
    QT_TRANSLATE_NOOP("JiraBridge", "Last 7 Days"),
    QT_TRANSLATE_NOOP("JiraBridge", "Last 30 Days"),
    QT_TRANSLATE_NOOP("JiraBridge", "Last 90 Days"),
    QT_TRANSLATE_NOOP("JiraBridge", "This Year"),
    QT_TRANSLATE_NOOP("JiraBridge", "Open"),
    QT_TRANSLATE_NOOP("JiraBridge", "In Progress"),
    QT_TRANSLATE_NOOP("JiraBridge", "Verified"),
    QT_TRANSLATE_NOOP("JiraBridge", "Resolved"),
    QT_TRANSLATE_NOOP("JiraBridge", "Closed"),
    QT_TRANSLATE_NOOP("JiraBridge", "Highest"),
    QT_TRANSLATE_NOOP("JiraBridge", "Critical"),
    QT_TRANSLATE_NOOP("JiraBridge", "High"),
    QT_TRANSLATE_NOOP("JiraBridge", "Medium"),
    QT_TRANSLATE_NOOP("JiraBridge", "Low"),
    QT_TRANSLATE_NOOP("JiraBridge", "Bug"),
    QT_TRANSLATE_NOOP("JiraBridge", "Task"),
    QT_TRANSLATE_NOOP("JiraBridge", "Story"),
    QT_TRANSLATE_NOOP("JiraBridge", "Improvement"),
    QT_TRANSLATE_NOOP("JiraBridge", "Unassigned"),
    QT_TRANSLATE_NOOP("JiraBridge", "LDAP session is missing Jira credentials. Please sign in again."),
    QT_TRANSLATE_NOOP("JiraBridge", "Connected to {base_url} | loaded {loaded} of {total}"),
    QT_TRANSLATE_NOOP(
        "JiraBridge",
        "Loaded {loaded} of {total} issues for browsing. Select an issue or ask a question for deeper analysis.",
    ),
    QT_TRANSLATE_NOOP("JiraBridge", "Connected to {base_url} | analyzed {returned} of {total}"),
    QT_TRANSLATE_NOOP("JiraBridge", "Just now"),
    QT_TRANSLATE_NOOP("JiraBridge", "Sign in to load Jira data."),
    QT_TRANSLATE_NOOP("JiraBridge", "Sign in with LDAP first, then Jira results and AI analysis will load here."),
    QT_TRANSLATE_NOOP("JiraBridge", "Loading Jira results..."),
    QT_TRANSLATE_NOOP("JiraBridge", "Analyzing Jira request..."),
    QT_TRANSLATE_NOOP("JiraBridge", "Sign in again to restore Jira access."),
    QT_TRANSLATE_NOOP("JiraBridge", "Signed out"),
    QT_TRANSLATE_NOOP("JiraBridge", "Unknown Jira error"),
    QT_TRANSLATE_NOOP("JiraBridge", "Jira request failed: {message}"),
    QT_TRANSLATE_NOOP("JiraBridge", "Matched"),
    QT_TRANSLATE_NOOP("JiraBridge", "{displayed} displayed in the current view"),
    QT_TRANSLATE_NOOP("JiraBridge", "High Priority"),
    QT_TRANSLATE_NOOP("JiraBridge", "Highest, critical, or high in the current result set"),
    QT_TRANSLATE_NOOP("JiraBridge", "Blocked"),
    QT_TRANSLATE_NOOP("JiraBridge", "Blocked items from the displayed Jira scope"),
    QT_TRANSLATE_NOOP("JiraBridge", "Projects"),
    QT_TRANSLATE_NOOP("JiraBridge", "Workflow Preset"),
    QT_TRANSLATE_NOOP("JiraBridge", "Time Window"),
    QT_TRANSLATE_NOOP("JiraBridge", "Statuses"),
    QT_TRANSLATE_NOOP("JiraBridge", "Priorities"),
    QT_TRANSLATE_NOOP("JiraBridge", "Issue Types"),
    QT_TRANSLATE_NOOP("JiraBridge", "Keyword text"),
    QT_TRANSLATE_NOOP("JiraBridge", "Assignee"),
    QT_TRANSLATE_NOOP("JiraBridge", "Reporter"),
    QT_TRANSLATE_NOOP("JiraBridge", "Labels"),
    QT_TRANSLATE_NOOP("JiraBridge", "Not limited"),
    QT_TRANSLATE_NOOP("JiraBridge", "Current user"),
    QT_TRANSLATE_NOOP("JiraBridge", "JQL"),
    QT_TRANSLATE_NOOP("JiraBridge", "Useful candidates for the next regression batch"),
    QT_TRANSLATE_NOOP("JiraBridge", "My Filters"),
    QT_TRANSLATE_NOOP("JiraBridge", "Loading your Jira filters..."),
    QT_TRANSLATE_NOOP("JiraBridge", "No favourite filters were found for this account."),
    QT_TRANSLATE_NOOP("JiraBridge", "Click to apply this filter to the current JQL box."),
    QT_TRANSLATE_NOOP("JiraBridge", "Comments"),
    QT_TRANSLATE_NOOP("JiraBridge", "No Jira issues matched the current scope."),
    QT_TRANSLATE_NOOP(
        "JiraBridge",
        "{total} Jira issues matched the current scope. Top issue: {key} ({status}, {priority}) - {summary}",
    ),
)


class JiraBridge(QObject):
    stateChanged = Signal()
    loadingChanged = Signal()
    connectionChanged = Signal()
    _applyResult = Signal(object)
    _applyError = Signal(object)
    _applyDetailResult = Signal(object)
    _applyFiltersResult = Signal(object)

    def __init__(self, auth_bridge: AuthBridge):
        super().__init__(QGuiApplication.instance())
        self._auth_bridge = auth_bridge
        self._loading = False
        self._connected = False
        self._status_state = self._translated_state("Ready")
        self._analysis_summary_state = self._translated_state("Run a Jira query to get a live AI summary.")
        self._analysis_actions: list[str] = []
        self._issues: list[dict[str, Any]] = []
        self._saved_filters: list[dict[str, str]] = []
        self._filters_loading = False
        self._conversation = [self._workspace_ready_row()]
        self._selected_issue_index = 0
        self._displayed_total = 0
        self._worker_seq = 0
        self._detail_worker_seq = 0
        self._filters_worker_seq = 0
        self._can_load_more = False
        self._next_start_at = 0
        self._active_scope: dict[str, Any] = {}
        self._issue_service: JiraIssueService | None = None
        self._ai_service: JiraAIAnalysisService | None = None
        self._service_identity: tuple[str, str] | None = None
        self._state_lock = Lock()
        self._auth_bridge.authChanged.connect(self._handle_auth_changed)
        TranslateHelper().currentChanged.connect(self._handle_language_changed)
        self._applyResult.connect(self._on_worker_result)
        self._applyError.connect(self._on_worker_error)
        self._applyDetailResult.connect(self._on_detail_result)
        self._applyFiltersResult.connect(self._on_filters_result)

    def _trace(self, stage: str, **values: Any) -> None:
        details = " ".join(f"{key}={values[key]}" for key in sorted(values))
        print(f"[JIRA_UI] {stage} {details}".rstrip())

    def _t(self, text: str) -> str:
        return self.tr(text)

    def _translated_state(self, template: str, **values: Any) -> dict[str, Any]:
        return {"kind": "translated", "template": template, "values": dict(values)}

    @staticmethod
    def _raw_state(text: str) -> dict[str, Any]:
        return {"kind": "raw", "text": text}

    def _render_state_text(self, state: dict[str, Any]) -> str:
        if not state:
            return ""
        if state.get("kind") == "translated":
            template = str(state.get("template", "") or "")
            return self._t(template).format(**dict(state.get("values") or {}))
        return str(state.get("text", "") or "")

    def _system_row(
        self,
        *,
        message_template: str,
        timestamp_template: str,
        message_values: dict[str, Any] | None = None,
        timestamp_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "role": "assistant",
            "author": "SmartTest AI",
            "message_template": message_template,
            "message_values": dict(message_values or {}),
            "timestamp_template": timestamp_template,
            "timestamp_values": dict(timestamp_values or {}),
        }

    def _render_conversation_row(self, row: dict[str, Any]) -> dict[str, Any]:
        rendered = dict(row)
        if "message_template" in row:
            rendered["message"] = self._t(str(row.get("message_template", "") or "")).format(
                **dict(row.get("message_values") or {})
            )
        if "timestamp_template" in row:
            rendered["timestamp"] = self._t(str(row.get("timestamp_template", "") or "")).format(
                **dict(row.get("timestamp_values") or {})
            )
        return rendered

    def _workspace_ready_row(self) -> dict[str, Any]:
        return self._system_row(
            message_template="Signed-in Jira access is ready. Ask in natural language to search issues and summarize risk.",
            timestamp_template="Workspace ready",
        )

    def _clear_session_row(self) -> dict[str, Any]:
        return self._system_row(
            message_template="Session cleared. Ask a new Jira question when ready.",
            timestamp_template="Reset",
        )

    def _error_row(self) -> dict[str, Any]:
        return self._system_row(
            message_template="Jira request failed. Check the connection message above and sign in again if needed.",
            timestamp_template="Error",
        )

    def _project_label(self, option_id: str) -> str:
        labels = {
            "all_supported_projects": self._t("All Supported Projects"),
            "rk": "RK",
            "tv": "TV",
            "ott": "OTT",
            "iptv": "IPTV",
            "gh": "GH",
            "sh": "SH",
        }
        return labels.get(option_id, self._t("All Supported Projects"))

    def _board_label(self, option_id: str) -> str:
        labels = {
            "open_work": self._t("Open Work"),
            "ready_for_test": self._t("Ready for Test"),
            "closed_bugs": self._t("Closed Bugs"),
        }
        return labels.get(option_id, self._t("Open Work"))

    def _timeframe_label(self, option_id: str) -> str:
        labels = {
            "last_7_days": self._t("Last 7 Days"),
            "last_30_days": self._t("Last 30 Days"),
            "last_90_days": self._t("Last 90 Days"),
            "this_year": self._t("This Year"),
        }
        return labels.get(option_id, self._t("Last 30 Days"))

    def _status_label(self, option_id: str) -> str:
        labels = {
            "open": self._t("Open"),
            "in_progress": self._t("In Progress"),
            "blocked": self._t("Blocked"),
            "ready_for_test": self._t("Ready for Test"),
            "verified": self._t("Verified"),
            "resolved": self._t("Resolved"),
            "closed": self._t("Closed"),
        }
        return labels.get(option_id, self._t("Open"))

    def _priority_label(self, option_id: str) -> str:
        labels = {
            "highest": self._t("Highest"),
            "critical": self._t("Critical"),
            "high": self._t("High"),
            "medium": self._t("Medium"),
            "low": self._t("Low"),
        }
        return labels.get(option_id, self._t("Medium"))

    def _issue_type_label(self, option_id: str) -> str:
        labels = {
            "bug": self._t("Bug"),
            "task": self._t("Task"),
            "story": self._t("Story"),
            "improvement": self._t("Improvement"),
        }
        return labels.get(option_id, self._t("Bug"))

    def _summarize_option_ids(
        self,
        raw_value: str,
        *,
        valid_ids: tuple[str, ...],
        labeler: Callable[[str], str],
        default_label: str,
        collapse_all_id: str | None = None,
    ) -> str:
        option_ids = [option_id for option_id in self._parse_csv_ids(raw_value) if option_id in valid_ids]
        if collapse_all_id and collapse_all_id in option_ids:
            option_ids = [collapse_all_id]
        if not option_ids:
            return default_label
        return ", ".join(labeler(option_id) for option_id in option_ids)

    def _summarize_terms(self, raw_value: str, *, default_label: str) -> str:
        values = self._parse_csv_terms(raw_value)
        if not values:
            return default_label
        return ", ".join(values)

    def _active_scope_summary_text(self) -> str:
        if not self._active_scope:
            return ""
        raw_jql_text = str(self._active_scope.get("raw_jql_text", "") or "").strip()
        if raw_jql_text:
            return f"{self._t('JQL')}: {raw_jql_text}"

        not_limited = self._t("Not limited")
        all_projects = self._t("All Supported Projects")

        project_summary = self._summarize_option_ids(
            str(self._active_scope.get("project_ids_csv", "all_supported_projects") or ""),
            valid_ids=_PROJECT_OPTION_IDS,
            labeler=self._project_label,
            default_label=all_projects,
            collapse_all_id="all_supported_projects",
        )

        board_label = str(self._active_scope.get("board_label", "") or "").strip()
        timeframe_label = str(self._active_scope.get("timeframe_label", "") or "").strip()
        board_summary = board_label or self._board_label(_BOARD_OPTION_IDS[0])
        timeframe_summary = timeframe_label or self._timeframe_label(_TIMEFRAME_OPTION_IDS[1])

        status_summary = self._summarize_option_ids(
            str(self._active_scope.get("status_ids_csv", "") or ""),
            valid_ids=_STATUS_OPTION_IDS,
            labeler=self._status_label,
            default_label=not_limited,
        )
        priority_summary = self._summarize_option_ids(
            str(self._active_scope.get("priority_ids_csv", "") or ""),
            valid_ids=_PRIORITY_OPTION_IDS,
            labeler=self._priority_label,
            default_label=not_limited,
        )
        issue_type_summary = self._summarize_option_ids(
            str(self._active_scope.get("issue_type_ids_csv", "") or ""),
            valid_ids=_ISSUE_TYPE_OPTION_IDS,
            labeler=self._issue_type_label,
            default_label=not_limited,
        )
        keyword_summary = str(self._active_scope.get("keyword_text", "") or "").strip() or not_limited
        assignee_summary = (
            self._t("Current user")
            if bool(self._active_scope.get("only_mine", False))
            else self._summarize_terms(
                str(self._active_scope.get("assignee_text", "") or ""),
                default_label=not_limited,
            )
        )
        reporter_summary = self._summarize_terms(
            str(self._active_scope.get("reporter_text", "") or ""),
            default_label=not_limited,
        )
        labels_summary = self._summarize_terms(
            str(self._active_scope.get("labels_text", "") or ""),
            default_label=not_limited,
        )

        parts = [
            f"{self._t('Projects')}: {project_summary}",
            f"{self._t('Workflow Preset')}: {board_summary}",
            f"{self._t('Time Window')}: {timeframe_summary}",
            f"{self._t('Statuses')}: {status_summary}",
            f"{self._t('Priorities')}: {priority_summary}",
            f"{self._t('Issue Types')}: {issue_type_summary}",
            f"{self._t('Keyword text')}: {keyword_summary}",
            f"{self._t('Assignee')}: {assignee_summary}",
            f"{self._t('Reporter')}: {reporter_summary}",
            f"{self._t('Labels')}: {labels_summary}",
        ]
        return " | ".join(parts)

    def _resolve_option_id(self, option_type: str, label: str) -> str:
        clean_label = str(label or "").strip()
        mapping: dict[str, str] = {}
        if option_type == "project":
            for option_id in _PROJECT_OPTION_IDS:
                mapping[option_id] = option_id
                mapping[self._project_label(option_id)] = option_id
            return mapping.get(clean_label, _PROJECT_OPTION_IDS[0])
        if option_type == "board":
            for option_id in _BOARD_OPTION_IDS:
                mapping[option_id] = option_id
                mapping[self._board_label(option_id)] = option_id
            return mapping.get(clean_label, _BOARD_OPTION_IDS[0])
        for option_id in _TIMEFRAME_OPTION_IDS:
            mapping[option_id] = option_id
            mapping[self._timeframe_label(option_id)] = option_id
        return mapping.get(clean_label, _TIMEFRAME_OPTION_IDS[1])

    @staticmethod
    def _parse_csv_ids(raw_value: str) -> list[str]:
        values = []
        for item in str(raw_value or "").split(","):
            clean = item.strip()
            if clean and clean not in values:
                values.append(clean)
        return values

    @staticmethod
    def _parse_csv_terms(raw_value: str) -> list[str]:
        values = []
        normalized = str(raw_value or "").replace(";", ",")
        for item in normalized.split(","):
            clean = item.strip()
            if clean and clean not in values:
                values.append(clean)
        return values

    @staticmethod
    def _quote_jql_value(value: str) -> str:
        escaped = str(value or "").replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _render_issue_row(self, issue: dict[str, Any]) -> dict[str, Any]:
        rendered = dict(issue)
        assignee = str(rendered.get("assignee", "") or "").strip()
        rendered["assignee"] = assignee or self._t("Unassigned")
        return rendered

    def _handle_language_changed(self) -> None:
        self.connectionChanged.emit()
        self.stateChanged.emit()

    def _cache_dir(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "jira"

    def _set_loading(self, value: bool) -> None:
        if self._loading == value:
            return
        self._loading = value
        self.loadingChanged.emit()

    def _set_connection(
        self,
        *,
        connected: bool,
        status_state: dict[str, Any] | None = None,
        status_text: str | None = None,
    ) -> None:
        next_state = status_state if status_state is not None else self._raw_state(status_text or "")
        changed = self._connected != connected or self._status_state != next_state
        self._connected = connected
        self._status_state = next_state
        if changed:
            self.connectionChanged.emit()

    def _ensure_services(self) -> tuple[JiraIssueService, JiraAIAnalysisService]:
        username = self._auth_bridge.currentUsername()
        password = self._auth_bridge.currentPassword()
        if not username or not password:
            raise RuntimeError(self._t("LDAP session is missing Jira credentials. Please sign in again."))
        identity = (username, password)
        if self._issue_service is not None and self._ai_service is not None and self._service_identity == identity:
            self._trace("services_reuse", username=username)
            return self._issue_service, self._ai_service

        self._trace("services_create_start", username=username)
        started_at = time.monotonic()
        auth = JiraBasicAuth(username=username, password=password)
        client = JiraClient(
            JiraClientConfig(
                base_url=JIRA_BASE_URL,
                page_size=100,
                max_workers=6,
            ),
            auth,
        )
        metadata_cache = JiraFieldMetadataCache(self._cache_dir() / "field_metadata.db")
        jira_registry = FieldRegistry.bootstrap_from_client(
            client,
            metadata_cache=metadata_cache,
            ttl_seconds=3600,
        )
        issue_service = JiraIssueService(client, registry=jira_registry)
        ai_service = JiraAIAnalysisService(AmlogicAIProvider())
        self._issue_service = issue_service
        self._ai_service = ai_service
        self._service_identity = identity
        self._trace(
            "services_create_done",
            username=username,
            elapsed_ms=int((time.monotonic() - started_at) * 1000),
        )
        return issue_service, ai_service

    def _start_saved_filters_worker(self) -> None:
        if self._filters_loading:
            return
        if not self._auth_bridge.isAuthenticated() or not self._auth_bridge.hasCredential():
            return
        self._filters_worker_seq += 1
        worker_id = self._filters_worker_seq
        self._filters_loading = True
        self.stateChanged.emit()
        Thread(
            target=self._fetch_saved_filters,
            kwargs={"worker_id": worker_id},
            daemon=True,
        ).start()

    def _fetch_saved_filters(self, *, worker_id: int) -> None:
        started_at = time.monotonic()
        self._trace("filters_start", worker_id=worker_id)
        try:
            issue_service, _ = self._ensure_services()
            items = issue_service._client.fetch_favourite_filters()
            filters = self._normalize_saved_filters(items)
            self._trace(
                "filters_done",
                worker_id=worker_id,
                returned=len(filters),
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            self._applyFiltersResult.emit({"worker_id": worker_id, "filters": filters})
        except Exception:  # noqa: BLE001
            logging.exception("JiraBridge favourite filters load failed")
            self._applyFiltersResult.emit({"worker_id": worker_id, "filters": []})

    def _build_scope_context(
        self,
        *,
        raw_jql_text: str,
        project_ids_csv: str,
        board_label: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        include_comments: bool,
        include_links: bool,
        only_mine: bool,
    ) -> dict[str, Any]:
        return {
            "raw_jql_text": raw_jql_text,
            "project_ids_csv": project_ids_csv,
            "board_label": board_label,
            "timeframe_label": timeframe_label,
            "status_ids_csv": status_ids_csv,
            "priority_ids_csv": priority_ids_csv,
            "issue_type_ids_csv": issue_type_ids_csv,
            "keyword_text": keyword_text,
            "assignee_text": assignee_text,
            "reporter_text": reporter_text,
            "labels_text": labels_text,
            "include_comments": include_comments,
            "include_links": include_links,
            "only_mine": only_mine,
        }

    @staticmethod
    def _normalize_saved_filters(items: list[dict[str, Any]]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for item in items:
            filter_id = str(item.get("id", "") or "").strip()
            name = str(item.get("name", "") or "").strip()
            jql = str(item.get("jql", "") or "").strip()
            if not filter_id or not name or not jql or filter_id in seen_ids:
                continue
            seen_ids.add(filter_id)
            normalized.append({"id": filter_id, "name": name, "jql": jql})
        return normalized

    @staticmethod
    def _requires_full_dataset(prompt: str) -> bool:
        normalized = (prompt or "").strip().lower()
        if normalized == "":
            return False
        markers = (
            "all issues",
            "all matched",
            "full dataset",
            "entire dataset",
            "全部",
            "所有",
            "全量",
            "完整数据",
        )
        return any(marker in normalized for marker in markers)

    def _browse_specs(self) -> list[str | FieldSpec]:
        return [
            "key",
            "summary",
            "status",
            "assignee",
            "reporter",
            "priority",
            "labels",
            "updated",
            FieldSpec(name="project", path="fields.project.key", jira_fields=("project",)),
        ]

    def _build_specs(self, *, include_comments: bool, include_links: bool) -> list[str | FieldSpec]:
        specs: list[str | FieldSpec] = [
            "key",
            "summary",
            "status",
            "assignee",
            "reporter",
            "priority",
            "labels",
            "updated",
            FieldSpec(name="project", path="fields.project.key", jira_fields=("project",)),
            FieldSpec(name="issueType", path="fields.issuetype.name", jira_fields=("issuetype",)),
            FieldSpec(name="resolution", path="fields.resolution.name", jira_fields=("resolution",)),
            FieldSpec(name="components", path="fields.components[].name", jira_fields=("components",)),
            FieldSpec(name="description", path="fields.description", jira_fields=("description",)),
        ]
        if include_comments:
            specs.append(
                FieldSpec(
                    name="comments",
                    path="fields.comment.comments[].body",
                    jira_fields=("comment",),
                )
            )
        if include_links:
            specs.append(
                FieldSpec(
                    name="issuelinks",
                    path="fields.issuelinks[]",
                    jira_fields=("issuelinks",),
                )
            )
        return specs

    def _build_base_jql(
        self,
        *,
        raw_jql_text: str,
        project_ids_csv: str,
        board_label: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        only_mine: bool,
    ) -> str:
        if raw_jql_text.strip():
            return raw_jql_text.strip()
        clauses: list[str] = []
        project_ids = self._parse_csv_ids(project_ids_csv)
        board_id = self._resolve_option_id("board", board_label)
        timeframe_id = self._resolve_option_id("timeframe", timeframe_label)
        project_map = {
            "all_supported_projects": ("RK", "TV", "OTT", "IPTV", "GH", "SH"),
            "rk": ("RK",),
            "tv": ("TV",),
            "ott": ("OTT",),
            "iptv": ("IPTV",),
            "gh": ("GH",),
            "sh": ("SH",),
        }
        board_map = {
            "open_work": "statusCategory != Done",
            "ready_for_test": 'status in ("Ready for Test", Verified, Resolved)',
            "closed_bugs": "status in (Resolved, Closed, Verified)",
        }
        timeframe_map = {
            "last_7_days": "updated >= -7d",
            "last_30_days": "updated >= -30d",
            "last_90_days": "updated >= -90d",
            "this_year": "created >= startOfYear()",
        }
        status_map = {
            "open": "Open",
            "in_progress": "In Progress",
            "blocked": "Blocked",
            "ready_for_test": "Ready for Test",
            "verified": "Verified",
            "resolved": "Resolved",
            "closed": "Closed",
        }
        priority_map = {
            "highest": "Highest",
            "critical": "Critical",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }
        issue_type_map = {
            "bug": "Bug",
            "task": "Task",
            "story": "Story",
            "improvement": "Improvement",
        }

        selected_projects: list[str] = []
        for project_id in project_ids:
            selected_projects.extend(project_map.get(project_id, ()))
        if not selected_projects or "all_supported_projects" in project_ids:
            selected_projects = list(project_map["all_supported_projects"])
        clauses.append(f'project in ({", ".join(selected_projects)})')

        selected_issue_types = [
            issue_type_map[issue_type_id]
            for issue_type_id in self._parse_csv_ids(issue_type_ids_csv)
            if issue_type_id in issue_type_map
        ]
        if selected_issue_types:
            clauses.append(
                "issuetype in ("
                + ", ".join(self._quote_jql_value(issue_type) for issue_type in selected_issue_types)
                + ")"
            )

        selected_statuses = [
            status_map[status_id]
            for status_id in self._parse_csv_ids(status_ids_csv)
            if status_id in status_map
        ]
        if selected_statuses:
            clauses.append(
                "status in ("
                + ", ".join(self._quote_jql_value(status) for status in selected_statuses)
                + ")"
            )
        else:
            clauses.append(board_map.get(board_id, board_map["open_work"]))

        clauses.append(timeframe_map.get(timeframe_id, timeframe_map["last_30_days"]))

        if only_mine:
            clauses.append("assignee = currentUser()")
        else:
            assignees = self._parse_csv_terms(assignee_text)
            if assignees:
                clauses.append(
                    "assignee in ("
                    + ", ".join(self._quote_jql_value(assignee) for assignee in assignees)
                    + ")"
                )

        reporters = self._parse_csv_terms(reporter_text)
        if reporters:
            clauses.append(
                "reporter in ("
                + ", ".join(self._quote_jql_value(reporter) for reporter in reporters)
                + ")"
            )

        selected_priorities = [
            priority_map[priority_id]
            for priority_id in self._parse_csv_ids(priority_ids_csv)
            if priority_id in priority_map
        ]
        if selected_priorities:
            clauses.append(
                "priority in ("
                + ", ".join(self._quote_jql_value(priority) for priority in selected_priorities)
                + ")"
            )

        labels = self._parse_csv_terms(labels_text)
        if labels:
            clauses.append("labels in (" + ", ".join(self._quote_jql_value(label) for label in labels) + ")")

        if keyword_text.strip():
            escaped = keyword_text.strip().replace("\\", "\\\\").replace('"', '\\"')
            clauses.append(f'text ~ "{escaped}"')

        return " AND ".join(clauses) + " ORDER BY updated DESC"

    def _nl_clause(self, ai_service: JiraAIAnalysisService, prompt: str, *, project_label: str) -> str:
        clean_prompt = prompt.strip()
        if clean_prompt == "":
            return ""
        planning_prompt = (
            "Convert the user request into one extra Jira JQL clause.\n"
            'Return JSON only with this schema: {"jql_clause": string}.\n'
            "Rules:\n"
            "- Return only an additional clause, not a full query.\n"
            "- Use only Jira fields: summary, description, text, status, priority, assignee, reporter, labels, component, issuekey.\n"
            "- If the prompt is mainly analytical and adds no filter, return an empty string.\n"
            f"- Current project scope label: {project_label}.\n"
            f"- User prompt: {clean_prompt}"
        )
        try:
            response = ai_service.ask(planning_prompt, model=None, max_tokens=200, temperature=0.0)
            text = response.text or ""
            if text.strip() == "":
                return ""
            payload = json.loads(text)
        except Exception:  # noqa: BLE001
            return ""
        clause = str(payload.get("jql_clause", "") or "").strip()
        return clause

    def _browse_scope(
        self,
        *,
        raw_jql_text: str,
        project_ids_csv: str,
        board_label: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        include_comments: bool,
        include_links: bool,
        only_mine: bool,
        start_at: int,
        append: bool,
        worker_id: int,
    ) -> None:
        started_at = time.monotonic()
        self._trace(
            "browse_start",
            worker_id=worker_id,
            start_at=start_at,
            append=append,
            projects=project_ids_csv,
            board=board_label,
            timeframe=timeframe_label,
        )
        try:
            issue_service, _ = self._ensure_services()
            specs = self._browse_specs()
            plan = issue_service._registry.build_plan(specs, include_heavy=False)
            effective_jql = self._build_base_jql(
                raw_jql_text=raw_jql_text,
                project_ids_csv=project_ids_csv,
                board_label=board_label,
                timeframe_label=timeframe_label,
                status_ids_csv=status_ids_csv,
                priority_ids_csv=priority_ids_csv,
                issue_type_ids_csv=issue_type_ids_csv,
                keyword_text=keyword_text,
                assignee_text=assignee_text,
                reporter_text=reporter_text,
                labels_text=labels_text,
                only_mine=only_mine,
            )
            page = issue_service._client.search_page(
                effective_jql,
                start_at=start_at,
                max_results=min(_MAX_DISPLAY_ISSUES, 25),
                fields=list(plan.jira_fields),
                expand=list(plan.expand) or None,
            )
            records = [issue_service.project_issue(issue, list(plan.active_specs)) for issue in page.issues]
            issues = [_record_to_issue_row(record) for record in records]
            self._trace(
                "browse_done",
                worker_id=worker_id,
                returned=len(issues),
                total=page.total,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            self._applyResult.emit(
                {
                    "mode": "browse",
                    "worker_id": worker_id,
                    "connected": True,
                    "status_state": self._translated_state(
                        "Connected to {base_url} | loaded {loaded} of {total}",
                        base_url=JIRA_BASE_URL,
                        loaded=start_at + len(issues),
                        total=page.total,
                    ),
                    "issues": issues,
                    "selected_issue_index": 0 if not append else self._selected_issue_index,
                    "displayed_total": page.total,
                    "analysis_summary_state": self._translated_state(
                        "Loaded {loaded} of {total} issues for browsing. Select an issue or ask a question for deeper analysis.",
                        loaded=start_at + len(issues),
                        total=page.total,
                    ),
                    "analysis_actions": [],
                    "assistant_message": "",
                    "assistant_timestamp": "",
                    "append": append,
                    "next_start_at": page.start_at + len(page.issues),
                    "can_load_more": (page.start_at + len(page.issues)) < page.total,
                    "scope": self._build_scope_context(
                        raw_jql_text=raw_jql_text,
                        project_ids_csv=project_ids_csv,
                        board_label=board_label,
                        timeframe_label=timeframe_label,
                        status_ids_csv=status_ids_csv,
                        priority_ids_csv=priority_ids_csv,
                        issue_type_ids_csv=issue_type_ids_csv,
                        keyword_text=keyword_text,
                        assignee_text=assignee_text,
                        reporter_text=reporter_text,
                        labels_text=labels_text,
                        include_comments=include_comments,
                        include_links=include_links,
                        only_mine=only_mine,
                    ),
                }
            )
        except Exception as exc:  # noqa: BLE001
            logging.exception("JiraBridge browse failed")
            self._applyError.emit({"worker_id": worker_id, "message": f"{exc}"})

    def _fetch_issue_detail(
        self,
        *,
        issue_key: str,
        include_comments: bool,
        include_links: bool,
        worker_id: int,
    ) -> None:
        started_at = time.monotonic()
        self._trace(
            "detail_start",
            worker_id=worker_id,
            issue_key=issue_key,
            comments=include_comments,
            links=include_links,
        )
        try:
            issue_service, _ = self._ensure_services()
            record = issue_service.hydrate_issue(
                issue_key,
                specs=self._build_specs(include_comments=include_comments, include_links=include_links),
            )
            issue_row = _record_to_issue_row(record)
            self._trace(
                "detail_done",
                worker_id=worker_id,
                issue_key=issue_key,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            self._applyDetailResult.emit(
                {
                    "worker_id": worker_id,
                    "issue": issue_row,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logging.exception("JiraBridge issue detail failed")
            self._applyError.emit({"worker_id": self._worker_seq, "message": f"{exc}"})

    def _search_and_analyze(
        self,
        *,
        prompt: str,
        raw_jql_text: str,
        project_ids_csv: str,
        board_label: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        include_comments: bool,
        include_links: bool,
        only_mine: bool,
        include_user_message: bool,
        worker_id: int,
    ) -> None:
        started_at = time.monotonic()
        try:
            self._trace(
                "analyze_start",
                worker_id=worker_id,
                projects=project_ids_csv,
                board=board_label,
                timeframe=timeframe_label,
                full_dataset=self._requires_full_dataset(prompt),
            )
            issue_service, ai_service = self._ensure_services()
            specs = self._build_specs(include_comments=include_comments, include_links=include_links)
            base_jql = self._build_base_jql(
                raw_jql_text=raw_jql_text,
                project_ids_csv=project_ids_csv,
                board_label=board_label,
                timeframe_label=timeframe_label,
                status_ids_csv=status_ids_csv,
                priority_ids_csv=priority_ids_csv,
                issue_type_ids_csv=issue_type_ids_csv,
                keyword_text=keyword_text,
                assignee_text=assignee_text,
                reporter_text=reporter_text,
                labels_text=labels_text,
                only_mine=only_mine,
            )
            extra_clause = "" if raw_jql_text.strip() else self._nl_clause(ai_service, prompt, project_label=project_ids_csv)
            effective_jql = f"({base_jql}) AND ({extra_clause})" if extra_clause else base_jql
            full_dataset = self._requires_full_dataset(prompt)
            if full_dataset:
                records = issue_service.search_records(
                    effective_jql,
                    specs=specs,
                    include_heavy=False,
                    page_size=100,
                    max_workers=6,
                )
                total_count = len(records)
            else:
                plan = issue_service._registry.build_plan(specs, include_heavy=False)
                page = issue_service._client.search_page(
                    effective_jql,
                    max_results=_MAX_DISPLAY_ISSUES,
                    fields=list(plan.jira_fields),
                    expand=list(plan.expand) or None,
                )
                records = [issue_service.project_issue(issue, list(plan.active_specs)) for issue in page.issues]
                total_count = page.total
            issues = [_record_to_issue_row(record) for record in records]
            analysis_prompt = prompt.strip() or (
                f"Summarize the main Jira risks for {project_ids_csv} / {board_label} in {timeframe_label}."
            )
            analysis_response = ai_service.ask(
                analysis_prompt,
                jira_context={
                    "jql": effective_jql,
                    "returned_issue_count": len(issues),
                    "total_issue_count": total_count,
                    "issues": issues,
                },
                max_tokens=600,
                temperature=0.2,
            )
            analysis_text = (analysis_response.text or "").strip()
            if analysis_text == "":
                analysis_text = _fallback_analysis_text(issues, total_count)
            self._trace(
                "analyze_done",
                worker_id=worker_id,
                returned=len(issues),
                total=total_count,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            result = {
                "mode": "analyze",
                "worker_id": worker_id,
                "connected": True,
                "status_state": self._translated_state(
                    "Connected to {base_url} | analyzed {returned} of {total}",
                    base_url=JIRA_BASE_URL,
                    returned=len(issues),
                    total=total_count,
                ),
                "issues": issues,
                "selected_issue_index": 0,
                "displayed_total": total_count,
                "analysis_summary_state": self._raw_state(analysis_text),
                "analysis_actions": _extract_actions(analysis_text),
                "assistant_message": analysis_text,
                "assistant_timestamp": self._t("Just now"),
                "include_user_message": include_user_message,
                "prompt": prompt.strip(),
                "append": False,
                "next_start_at": len(issues),
                "can_load_more": (not full_dataset) and len(issues) < total_count,
                "scope": self._build_scope_context(
                    raw_jql_text=raw_jql_text,
                    project_ids_csv=project_ids_csv,
                    board_label=board_label,
                    timeframe_label=timeframe_label,
                    status_ids_csv=status_ids_csv,
                    priority_ids_csv=priority_ids_csv,
                    issue_type_ids_csv=issue_type_ids_csv,
                    keyword_text=keyword_text,
                    assignee_text=assignee_text,
                    reporter_text=reporter_text,
                    labels_text=labels_text,
                    include_comments=include_comments,
                    include_links=include_links,
                    only_mine=only_mine,
                ),
            }
            self._applyResult.emit(result)
        except Exception as exc:  # noqa: BLE001
            logging.exception("JiraBridge query failed")
            self._applyError.emit({"worker_id": worker_id, "message": f"{exc}"})

    @Slot()
    def bootstrap(self) -> None:
        if self._loading:
            return
        if not self._auth_bridge.isAuthenticated() or not self._auth_bridge.hasCredential():
            self._set_connection(
                connected=False,
                status_state=self._translated_state("Sign in to load Jira data."),
            )
            self._analysis_summary_state = self._translated_state(
                "Sign in with LDAP first, then Jira results and AI analysis will load here."
            )
            self.stateChanged.emit()
            return
        self._set_connection(
            connected=True,
            status_state=self._translated_state("Ready"),
        )
        self._analysis_summary_state = self._translated_state(
            "Run a Jira query to get a live AI summary."
        )
        if not self._saved_filters:
            self._start_saved_filters_worker()
        self.stateChanged.emit()

    @Slot(str, str, str, str, str, str, str, str, str, str, str, bool, bool, bool)
    def refreshScope(
        self,
        raw_jql_text: str,
        project_ids_csv: str,
        board_label: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        include_comments: bool,
        include_links: bool,
        only_mine: bool,
    ) -> None:
        self._start_browse_worker(
            raw_jql_text=raw_jql_text,
            project_ids_csv=project_ids_csv,
            board_label=board_label,
            timeframe_label=timeframe_label,
            status_ids_csv=status_ids_csv,
            priority_ids_csv=priority_ids_csv,
            issue_type_ids_csv=issue_type_ids_csv,
            keyword_text=keyword_text,
            assignee_text=assignee_text,
            reporter_text=reporter_text,
            labels_text=labels_text,
            include_comments=include_comments,
            include_links=include_links,
            only_mine=only_mine,
            start_at=0,
            append=False,
        )

    @Slot(str, str, str, str, str, str, str, str, str, str, str, str, bool, bool, bool)
    def submitPrompt(
        self,
        prompt: str,
        raw_jql_text: str,
        project_ids_csv: str,
        board_label: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        include_comments: bool,
        include_links: bool,
        only_mine: bool,
    ) -> None:
        clean_prompt = prompt.strip()
        if clean_prompt == "":
            return
        with self._state_lock:
            self._conversation.append(
                {
                    "role": "user",
                    "author": self._auth_bridge.currentUsername(),
                    "message": clean_prompt,
                    "timestamp": self._t("Just now"),
                }
            )
        self.stateChanged.emit()
        self._start_analysis_worker(
            prompt=clean_prompt,
            raw_jql_text=raw_jql_text,
            project_ids_csv=project_ids_csv,
            board_label=board_label,
            timeframe_label=timeframe_label,
            status_ids_csv=status_ids_csv,
            priority_ids_csv=priority_ids_csv,
            issue_type_ids_csv=issue_type_ids_csv,
            keyword_text=keyword_text,
            assignee_text=assignee_text,
            reporter_text=reporter_text,
            labels_text=labels_text,
            include_comments=include_comments,
            include_links=include_links,
            only_mine=only_mine,
            include_user_message=True,
        )

    def _start_browse_worker(
        self,
        *,
        raw_jql_text: str,
        project_ids_csv: str,
        board_label: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        include_comments: bool,
        include_links: bool,
        only_mine: bool,
        start_at: int,
        append: bool,
    ) -> None:
        self._worker_seq += 1
        worker_id = self._worker_seq
        self._set_loading(True)
        self._set_connection(
            connected=self._connected,
            status_state=self._translated_state("Loading Jira results..."),
        )
        Thread(
            target=self._browse_scope,
            kwargs={
                "raw_jql_text": raw_jql_text,
                "project_ids_csv": project_ids_csv,
                "board_label": board_label,
                "timeframe_label": timeframe_label,
                "status_ids_csv": status_ids_csv,
                "priority_ids_csv": priority_ids_csv,
                "issue_type_ids_csv": issue_type_ids_csv,
                "keyword_text": keyword_text,
                "assignee_text": assignee_text,
                "reporter_text": reporter_text,
                "labels_text": labels_text,
                "include_comments": include_comments,
                "include_links": include_links,
                "only_mine": only_mine,
                "start_at": start_at,
                "append": append,
                "worker_id": worker_id,
            },
            daemon=True,
        ).start()

    def _start_analysis_worker(
        self,
        *,
        prompt: str,
        raw_jql_text: str,
        project_ids_csv: str,
        board_label: str,
        timeframe_label: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        include_comments: bool,
        include_links: bool,
        only_mine: bool,
        include_user_message: bool,
    ) -> None:
        self._worker_seq += 1
        worker_id = self._worker_seq
        self._set_loading(True)
        self._set_connection(
            connected=self._connected,
            status_state=self._translated_state("Analyzing Jira request..."),
        )
        Thread(
            target=self._search_and_analyze,
            kwargs={
                "prompt": prompt,
                "raw_jql_text": raw_jql_text,
                "project_ids_csv": project_ids_csv,
                "board_label": board_label,
                "timeframe_label": timeframe_label,
                "status_ids_csv": status_ids_csv,
                "priority_ids_csv": priority_ids_csv,
                "issue_type_ids_csv": issue_type_ids_csv,
                "keyword_text": keyword_text,
                "assignee_text": assignee_text,
                "reporter_text": reporter_text,
                "labels_text": labels_text,
                "include_comments": include_comments,
                "include_links": include_links,
                "only_mine": only_mine,
                "include_user_message": include_user_message,
                "worker_id": worker_id,
            },
            daemon=True,
        ).start()

    @Slot(int, bool, bool)
    def selectIssue(self, index: int, include_comments: bool, include_links: bool) -> None:
        if index < 0 or index >= len(self._issues):
            return
        self._selected_issue_index = index
        self.stateChanged.emit()
        issue_key = str((self._issues[index] or {}).get("keyId", "")).strip()
        if not issue_key:
            return
        self._detail_worker_seq += 1
        worker_id = self._detail_worker_seq
        Thread(
            target=self._fetch_issue_detail,
            kwargs={
                "issue_key": issue_key,
                "include_comments": include_comments,
                "include_links": include_links,
                "worker_id": worker_id,
            },
            daemon=True,
        ).start()

    @Slot()
    def loadMore(self) -> None:
        if self._loading or not self._can_load_more or not self._active_scope:
            return
        self._trace("load_more_request", next_start_at=self._next_start_at)
        self._start_browse_worker(
            raw_jql_text=str(self._active_scope.get("raw_jql_text", "")),
            project_ids_csv=str(self._active_scope.get("project_ids_csv", "all_supported_projects")),
            board_label=str(self._active_scope.get("board_label", self._board_label(_BOARD_OPTION_IDS[0]))),
            timeframe_label=str(
                self._active_scope.get("timeframe_label", self._timeframe_label(_TIMEFRAME_OPTION_IDS[1]))
            ),
            status_ids_csv=str(self._active_scope.get("status_ids_csv", "")),
            priority_ids_csv=str(self._active_scope.get("priority_ids_csv", "")),
            issue_type_ids_csv=str(self._active_scope.get("issue_type_ids_csv", "bug")),
            keyword_text=str(self._active_scope.get("keyword_text", "")),
            assignee_text=str(self._active_scope.get("assignee_text", "")),
            reporter_text=str(self._active_scope.get("reporter_text", "")),
            labels_text=str(self._active_scope.get("labels_text", "")),
            include_comments=bool(self._active_scope.get("include_comments", False)),
            include_links=bool(self._active_scope.get("include_links", False)),
            only_mine=bool(self._active_scope.get("only_mine", False)),
            start_at=self._next_start_at,
            append=True,
        )

    @Slot()
    def clearConversation(self) -> None:
        self._conversation = [self._clear_session_row()]
        self.stateChanged.emit()

    def _handle_auth_changed(self) -> None:
        if self._auth_bridge.isAuthenticated() and self._auth_bridge.hasCredential():
            if not self._saved_filters:
                self._start_saved_filters_worker()
            return
        self._issues = []
        self._saved_filters = []
        self._filters_loading = False
        self._filters_worker_seq += 1
        self._displayed_total = 0
        self._selected_issue_index = 0
        self._analysis_summary_state = self._translated_state("Sign in again to restore Jira access.")
        self._analysis_actions = []
        self._can_load_more = False
        self._next_start_at = 0
        self._active_scope = {}
        self._issue_service = None
        self._ai_service = None
        self._service_identity = None
        self._set_connection(connected=False, status_state=self._translated_state("Signed out"))
        self.stateChanged.emit()

    @Slot(object)
    def _on_worker_result(self, payload: dict[str, Any]) -> None:
        worker_id = int(payload.get("worker_id", 0))
        if worker_id != self._worker_seq:
            return
        incoming_issues = list(payload.get("issues") or [])
        if bool(payload.get("append", False)):
            self._issues.extend(incoming_issues)
        else:
            self._issues = incoming_issues
        self._selected_issue_index = int(payload.get("selected_issue_index", 0))
        self._displayed_total = int(payload.get("displayed_total", len(self._issues)))
        summary_state = payload.get("analysis_summary_state")
        if isinstance(summary_state, dict):
            self._analysis_summary_state = summary_state
        else:
            self._analysis_summary_state = self._raw_state(str(payload.get("analysis_summary", "") or ""))
        self._analysis_actions = list(payload.get("analysis_actions") or [])
        self._next_start_at = int(payload.get("next_start_at", len(self._issues)))
        self._can_load_more = bool(payload.get("can_load_more", False))
        self._active_scope = dict(payload.get("scope") or {})
        assistant_message = str(payload.get("assistant_message", "") or "").strip()
        if assistant_message:
            self._conversation.append(
                {
                    "role": "assistant",
                    "author": "SmartTest AI",
                    "message": assistant_message,
                    "timestamp": str(payload.get("assistant_timestamp", self._t("Just now"))),
                }
            )
        status_state = payload.get("status_state")
        self._set_connection(
            connected=bool(payload.get("connected", False)),
            status_state=status_state if isinstance(status_state, dict) else None,
            status_text=str(payload.get("status_text", "Ready")),
        )
        self._set_loading(False)
        self.stateChanged.emit()

    @Slot(object)
    def _on_filters_result(self, payload: dict[str, Any]) -> None:
        worker_id = int(payload.get("worker_id", 0))
        if worker_id != self._filters_worker_seq:
            return
        self._saved_filters = list(payload.get("filters") or [])
        self._filters_loading = False
        self.stateChanged.emit()

    @Slot(object)
    def _on_detail_result(self, payload: dict[str, Any]) -> None:
        worker_id = int((payload or {}).get("worker_id", 0))
        if worker_id != self._detail_worker_seq:
            return
        issue = dict((payload or {}).get("issue") or {})
        issue_key = str(issue.get("keyId", "")).strip()
        if not issue_key:
            return
        for index, existing in enumerate(self._issues):
            if str(existing.get("keyId", "")).strip() == issue_key:
                self._issues[index] = issue
                break
        if self._issues and 0 <= self._selected_issue_index < len(self._issues):
            if str(self._issues[self._selected_issue_index].get("keyId", "")).strip() == issue_key:
                self.stateChanged.emit()

    @Slot(object)
    def _on_worker_error(self, payload: dict[str, Any]) -> None:
        worker_id = int((payload or {}).get("worker_id", 0))
        if worker_id != self._worker_seq:
            return
        message = str((payload or {}).get("message", "") or self._t("Unknown Jira error"))
        self._set_connection(
            connected=False,
            status_state=self._translated_state("Jira request failed: {message}", message=message),
        )
        self._analysis_summary_state = self._translated_state(
            "Jira request failed. Check the connection message above and sign in again if needed."
        )
        self._analysis_actions = []
        self._conversation.append(self._error_row())
        self._set_loading(False)
        self.stateChanged.emit()

    @Slot(result="QVariantList")
    def projectFilterOptions(self):
        return [{"id": option_id, "label": self._project_label(option_id)} for option_id in _PROJECT_OPTION_IDS]

    @Slot(result="QVariantList")
    def boardOptions(self):
        return [self._board_label(option_id) for option_id in _BOARD_OPTION_IDS]

    @Slot(result="QVariantList")
    def timeframeOptions(self):
        return [self._timeframe_label(option_id) for option_id in _TIMEFRAME_OPTION_IDS]

    @Slot(result="QVariantList")
    def statusFilterOptions(self):
        return [{"id": option_id, "label": self._status_label(option_id)} for option_id in _STATUS_OPTION_IDS]

    @Slot(result="QVariantList")
    def priorityFilterOptions(self):
        return [{"id": option_id, "label": self._priority_label(option_id)} for option_id in _PRIORITY_OPTION_IDS]

    @Slot(result="QVariantList")
    def issueTypeFilterOptions(self):
        return [{"id": option_id, "label": self._issue_type_label(option_id)} for option_id in _ISSUE_TYPE_OPTION_IDS]

    @Slot(result="QVariantList")
    def savedFilters(self):
        return list(self._saved_filters)

    @Slot(result="QVariantList")
    def conversationRows(self):
        return [self._render_conversation_row(row) for row in self._conversation]

    @Slot(result="QVariantList")
    def issueRows(self):
        return [self._render_issue_row(issue) for issue in self._issues]

    @Slot(result="QVariantMap")
    def selectedIssue(self):
        if not self._issues:
            return {}
        safe_index = max(0, min(self._selected_issue_index, len(self._issues) - 1))
        return self._render_issue_row(self._issues[safe_index])

    @Slot(str, result=str)
    def issueBrowseUrl(self, issue_key: str) -> str:
        clean_key = str(issue_key or "").strip()
        if not clean_key:
            return ""
        return f"{JIRA_BASE_URL.rstrip('/')}/browse/{quote(clean_key)}"

    @Slot(result="QVariantList")
    def quickStats(self):
        total_display = len(self._issues)
        blocked = sum(1 for issue in self._issues if str(issue.get("status", "")).lower() == "blocked")
        high_priority = sum(
            1
            for issue in self._issues
            if str(issue.get("priority", "")).lower() in {"highest", "critical", "high"}
        )
        ready_for_test = sum(
            1
            for issue in self._issues
            if str(issue.get("status", "")).lower() in {"ready for test", "verified", "resolved"}
        )
        return [
            {
                "label": self._t("Matched"),
                "value": str(self._displayed_total),
                "detail": self._t("{displayed} displayed in the current view").format(displayed=total_display),
            },
            {
                "label": self._t("High Priority"),
                "value": str(high_priority),
                "detail": self._t("Highest, critical, or high in the current result set"),
            },
            {
                "label": self._t("Blocked"),
                "value": str(blocked),
                "detail": self._t("Blocked items from the displayed Jira scope"),
            },
            {
                "label": self._t("Ready for Test"),
                "value": str(ready_for_test),
                "detail": self._t("Useful candidates for the next regression batch"),
            },
        ]

    @Slot(result=str)
    def analysisSummary(self) -> str:
        return self._render_state_text(self._analysis_summary_state)

    @Slot(result="QVariantList")
    def analysisActions(self):
        return list(self._analysis_actions)

    @Slot(result=bool)
    def canLoadMore(self) -> bool:
        return self._can_load_more

    def _get_loading(self) -> bool:
        return self._loading

    def _get_connected(self) -> bool:
        return self._connected

    def _get_status_text(self) -> str:
        return self._render_state_text(self._status_state)

    def _get_active_scope_summary(self) -> str:
        return self._active_scope_summary_text()

    def _get_filters_loading(self) -> bool:
        return self._filters_loading

    loading = Property(bool, _get_loading, notify=loadingChanged)
    connected = Property(bool, _get_connected, notify=connectionChanged)
    statusText = Property(str, _get_status_text, notify=connectionChanged)
    activeScopeSummary = Property(str, _get_active_scope_summary, notify=stateChanged)
    filtersLoading = Property(bool, _get_filters_loading, notify=stateChanged)


def _record_to_issue_row(record) -> dict[str, Any]:
    comments = record.fields.get("comments") or []
    links = record.fields.get("issuelinks") or []
    description = _normalize_text(record.fields.get("description"))
    if not description:
        description = record.fields.get("summary") or ""
    normalized_comments = [_normalize_text(item) for item in comments if _normalize_text(item)]
    return {
        "keyId": record.key,
        "summary": str(record.fields.get("summary", "") or ""),
        "status": str(record.fields.get("status", "") or ""),
        "priority": str(record.fields.get("priority", "") or ""),
        "assignee": str(record.fields.get("assignee", "") or ""),
        "reporter": str(record.fields.get("reporter", "") or ""),
        "labels": list(record.fields.get("labels") or []),
        "components": list(record.fields.get("components") or []),
        "project": str(record.fields.get("project", "") or ""),
        "updatedAt": str(record.fields.get("updated", "") or ""),
        "detail": description.strip(),
        "comments": normalized_comments,
        "commentCount": len(normalized_comments),
        "linkCount": len(links) if isinstance(links, list) else 0,
        "issueType": str(record.fields.get("issueType", "") or ""),
        "resolution": str(record.fields.get("resolution", "") or ""),
    }


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if "content" in value:
            return _normalize_text(value.get("content"))
        fragments: list[str] = []
        for key in ("text", "value", "name"):
            if value.get(key):
                fragments.append(str(value.get(key)))
        if fragments:
            return " ".join(fragment.strip() for fragment in fragments if fragment).strip()
        return _normalize_text(list(value.values()))
    if isinstance(value, list):
        fragments = [_normalize_text(item) for item in value]
        return "\n".join(fragment for fragment in fragments if fragment).strip()
    return str(value).strip() if value is not None else ""


def _extract_actions(text: str) -> list[str]:
    actions: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith(("-", "*", "1.", "2.", "3.")):
            actions.append(clean.lstrip("-*1234567890. ").strip())
    return actions[:5]


def _fallback_analysis_text(issues: list[dict[str, Any]], total: int) -> str:
    if not issues:
        return QCoreApplication.translate("JiraBridge", "No Jira issues matched the current scope.")
    top_issue = issues[0]
    return QCoreApplication.translate(
        "JiraBridge",
        "{total} Jira issues matched the current scope. Top issue: {key} ({status}, {priority}) - {summary}",
    ).format(
        total=total,
        key=top_issue["keyId"],
        status=top_issue["status"],
        priority=top_issue["priority"],
        summary=top_issue["summary"],
    )
