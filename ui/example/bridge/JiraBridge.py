from __future__ import annotations

import logging
import json
import os
from pathlib import Path
from threading import Lock, Thread
import time
import uuid
from datetime import datetime
from typing import Any, Callable
from urllib.parse import quote

from PySide6.QtCore import QObject, Property, QT_TRANSLATE_NOOP, QStandardPaths, Signal, Slot
from PySide6.QtGui import QGuiApplication

from jira_tool import (
    JiraWorkspaceService,
    create_jira_workspace_service,
    parse_csv_ids,
    parse_csv_terms,
)
from example.bridge.AuthBridge import AuthBridge
from example.helper.TranslateHelper import TranslateHelper
from example.helper.UiText import raw_text, render_template, render_text, translated_text

JIRA_BASE_URL = os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
_MAX_DISPLAY_ISSUES = 50

def _trace_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

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
    QT_TRANSLATE_NOOP("JiraBridge", "Jira AI Conversation"),
    QT_TRANSLATE_NOOP("JiraBridge", "Analyzing request: preparing search scope..."),
    QT_TRANSLATE_NOOP("JiraBridge", "Analyzing request: retrieving Jira issues..."),
    QT_TRANSLATE_NOOP("JiraBridge", "Analyzing request: generating response..."),
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
    _applyProgress = Signal(object)

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
        self._conversation_history = self._load_conversation_history()
        self._current_conversation_id = uuid.uuid4().hex
        self._selected_issue_index = 0
        self._displayed_total = 0
        self._worker_seq = 0
        self._detail_worker_seq = 0
        self._filters_worker_seq = 0
        self._can_load_more = False
        self._next_start_at = 0
        self._active_scope: dict[str, Any] = {}
        self._workspace_service: JiraWorkspaceService | None = None
        self._service_identity: tuple[str, str] | None = None
        self._state_lock = Lock()
        self._auth_bridge.authChanged.connect(self._handle_auth_changed)
        TranslateHelper().currentChanged.connect(self._handle_language_changed)
        self._applyResult.connect(self._on_worker_result)
        self._applyError.connect(self._on_worker_error)
        self._applyDetailResult.connect(self._on_detail_result)
        self._applyFiltersResult.connect(self._on_filters_result)
        self._applyProgress.connect(self._on_progress_update)

    def _trace(self, stage: str, **values: Any) -> None:
        details = " ".join(f"{key}={values[key]}" for key in sorted(values))
        print(f"{_trace_timestamp()} [JIRA_UI] {stage} {details}".rstrip())

    def _t(self, text: str) -> str:
        return self.tr(text)

    def _translated_state(self, template: str, **values: Any) -> dict[str, Any]:
        return translated_text(template, **values)

    @staticmethod
    def _raw_state(text: str) -> dict[str, Any]:
        return raw_text(text)

    def _render_state_text(self, state: dict[str, Any]) -> str:
        return render_text(self, state)

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
            rendered["message"] = render_template(
                self,
                str(row.get("message_template", "") or ""),
                row.get("message_values"),
            )
        if "timestamp_template" in row:
            rendered["timestamp"] = render_template(
                self,
                str(row.get("timestamp_template", "") or ""),
                row.get("timestamp_values"),
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

    def _history_path(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "Jira" / "ai_conversation_history.json"

    def _load_conversation_history(self) -> list[dict[str, Any]]:
        path = self._history_path()
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        rows = payload.get("conversations") if isinstance(payload, dict) else None
        return rows if isinstance(rows, list) else []

    def _save_conversation_history(self) -> None:
        path = self._history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump({"conversations": self._conversation_history[:50]}, handle, ensure_ascii=False, indent=2)

    def _current_history_title(self) -> str:
        for row in self._conversation:
            if row.get("role") == "user":
                message = str(row.get("message", "") or "").strip()
                if message:
                    return message[:60]
        return self._t("Jira AI Conversation")

    def _current_history_preview(self) -> str:
        for row in reversed(self._conversation):
            message = str(row.get("message", "") or "").strip()
            if message:
                return " ".join(message.split())[:100]
        return ""

    def _persist_current_conversation(self) -> None:
        messages = [dict(row) for row in self._conversation if str(row.get("message", "") or "").strip()]
        if not messages:
            return
        now = int(time.time())
        entry = {
            "id": self._current_conversation_id,
            "title": self._current_history_title(),
            "preview": self._current_history_preview(),
            "updated_at": now,
            "messages": messages,
        }
        self._conversation_history = [
            item for item in self._conversation_history if item.get("id") != self._current_conversation_id
        ]
        self._conversation_history.insert(0, entry)
        self._save_conversation_history()

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
        option_ids = [option_id for option_id in parse_csv_ids(raw_value) if option_id in valid_ids]
        if collapse_all_id and collapse_all_id in option_ids:
            option_ids = [collapse_all_id]
        if not option_ids:
            return default_label
        return ", ".join(labeler(option_id) for option_id in option_ids)

    def _summarize_terms(self, raw_value: str, *, default_label: str) -> str:
        values = parse_csv_terms(raw_value)
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

    def _set_progress_message(self, message: str) -> None:
        clean = str(message or "").strip()
        if not clean:
            return
        if self._conversation and self._conversation[-1].get("is_progress") is True:
            self._conversation[-1]["message"] = clean
            self._conversation[-1]["timestamp"] = self._t("Just now")
            return
        self._conversation.append(
            {
                "role": "assistant",
                "author": "SmartTest AI",
                "message": clean,
                "timestamp": self._t("Just now"),
                "is_progress": True,
            }
        )

    def _clear_progress_message(self) -> None:
        self._conversation = [row for row in self._conversation if row.get("is_progress") is not True]

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

    def _ensure_workspace_service(self) -> JiraWorkspaceService:
        username = self._auth_bridge.currentUsername()
        password = self._auth_bridge.currentPassword()
        if not username or not password:
            raise RuntimeError(self._t("LDAP session is missing Jira credentials. Please sign in again."))
        identity = (username, password)
        if self._workspace_service is not None and self._service_identity == identity:
            self._trace("services_reuse", username=username)
            return self._workspace_service

        self._trace("services_create_start", username=username)
        started_at = time.monotonic()
        workspace_service = create_jira_workspace_service(
            base_url=JIRA_BASE_URL,
            username=username,
            password=password,
            cache_dir=self._cache_dir(),
            page_size=100,
            max_workers=6,
            metadata_ttl_seconds=3600,
        )
        self._workspace_service = workspace_service
        self._service_identity = identity
        self._trace(
            "services_create_done",
            username=username,
            elapsed_ms=int((time.monotonic() - started_at) * 1000),
        )
        return workspace_service

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
            filters = self._ensure_workspace_service().fetch_saved_filters()
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
            result = self._ensure_workspace_service().browse(
                worker_id=worker_id,
                selected_issue_index=self._selected_issue_index,
                raw_jql_text=raw_jql_text,
                project_ids_csv=project_ids_csv,
                board_id=self._resolve_option_id("board", board_label),
                board_label=board_label,
                timeframe_id=self._resolve_option_id("timeframe", timeframe_label),
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
                start_at=start_at,
                append=append,
                translated_state=self._translated_state,
            )
            self._trace(
                "browse_done",
                worker_id=worker_id,
                returned=len(result.get("issues") or []),
                total=int(result.get("displayed_total", 0)),
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            self._applyResult.emit(result)
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
            result = self._ensure_workspace_service().fetch_issue_detail(
                worker_id=worker_id,
                issue_key=issue_key,
                include_comments=include_comments,
                include_links=include_links,
            )
            self._trace(
                "detail_done",
                worker_id=worker_id,
                issue_key=issue_key,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            self._applyDetailResult.emit(result)
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
            self._applyProgress.emit({"worker_id": worker_id, "message": self._t("Analyzing request: preparing search scope...")})
            self._trace(
                "analyze_start",
                worker_id=worker_id,
                projects=project_ids_csv,
                board=board_label,
                timeframe=timeframe_label,
                full_dataset=self._ensure_workspace_service().requires_full_dataset(prompt),
            )
            self._applyProgress.emit({"worker_id": worker_id, "message": self._t("Analyzing request: retrieving Jira issues...")})
            result = self._ensure_workspace_service().analyze(
                worker_id=worker_id,
                raw_jql_text=raw_jql_text,
                project_ids_csv=project_ids_csv,
                board_id=self._resolve_option_id("board", board_label),
                board_label=board_label,
                timeframe_id=self._resolve_option_id("timeframe", timeframe_label),
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
                include_user_message=include_user_message,
                prompt=prompt,
                translated_state=self._translated_state,
                raw_state=self._raw_state,
                assistant_timestamp=self._t("Just now"),
            )
            self._applyProgress.emit({"worker_id": worker_id, "message": self._t("Analyzing request: generating response...")})
            self._trace(
                "analyze_done",
                worker_id=worker_id,
                returned=len(result.get("issues") or []),
                total=int(result.get("displayed_total", 0)),
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            self._applyResult.emit(result)
        except Exception as exc:  # noqa: BLE001
            self._trace(
                "analyze_error",
                worker_id=worker_id,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
                error=str(exc),
            )
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

    @Slot(str)
    def copyText(self, text: str) -> None:
        QGuiApplication.clipboard().setText(str(text or ""))

    @Slot(str)
    def retryPrompt(self, prompt: str) -> None:
        clean_prompt = str(prompt or "").strip()
        if clean_prompt == "" or self._loading:
            return
        scope = dict(self._active_scope or {})
        self._start_analysis_worker(
            prompt=clean_prompt,
            raw_jql_text=str(scope.get("raw_jql_text", "")),
            project_ids_csv=str(scope.get("project_ids_csv", "all_supported_projects")),
            board_label=str(scope.get("board_label", "open_work")),
            timeframe_label=str(scope.get("timeframe_label", "last_30_days")),
            status_ids_csv=str(scope.get("status_ids_csv", "")),
            priority_ids_csv=str(scope.get("priority_ids_csv", "")),
            issue_type_ids_csv=str(scope.get("issue_type_ids_csv", "bug")),
            keyword_text=str(scope.get("keyword_text", "")),
            assignee_text=str(scope.get("assignee_text", "")),
            reporter_text=str(scope.get("reporter_text", "")),
            labels_text=str(scope.get("labels_text", "")),
            include_comments=bool(scope.get("include_comments", False)),
            include_links=bool(scope.get("include_links", False)),
            only_mine=bool(scope.get("only_mine", False)),
            include_user_message=False,
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
        self._set_progress_message(self._t("Searching Jira issues from your request..."))
        self.stateChanged.emit()
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
        self._persist_current_conversation()
        self._current_conversation_id = uuid.uuid4().hex
        self._conversation = [self._clear_session_row()]
        self.stateChanged.emit()

    @Slot(str)
    def restoreConversation(self, conversation_id: str) -> None:
        for entry in self._conversation_history:
            if entry.get("id") == conversation_id:
                self._current_conversation_id = str(entry.get("id", "") or uuid.uuid4().hex)
                self._conversation = [dict(row) for row in list(entry.get("messages") or [])]
                self.stateChanged.emit()
                return

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
        self._workspace_service = None
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
        self._clear_progress_message()
        if assistant_message:
            self._conversation.append(
                {
                    "role": "assistant",
                    "author": "SmartTest AI",
                    "message": assistant_message,
                    "timestamp": str(payload.get("assistant_timestamp", self._t("Just now"))),
                }
            )
        self._persist_current_conversation()
        status_state = payload.get("status_state")
        self._set_connection(
            connected=bool(payload.get("connected", False)),
            status_state=status_state if isinstance(status_state, dict) else None,
            status_text=str(payload.get("status_text", "Ready")),
        )
        self._set_loading(False)
        self.stateChanged.emit()

    @Slot(object)
    def _on_progress_update(self, payload: dict[str, Any]) -> None:
        worker_id = int((payload or {}).get("worker_id", 0))
        if worker_id != self._worker_seq:
            return
        message = str((payload or {}).get("message", "") or "").strip()
        if not message:
            return
        self._set_progress_message(message)
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
        self._clear_progress_message()
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
    def conversationHistoryRows(self):
        rows = []
        for entry in self._conversation_history:
            updated_at = int(entry.get("updated_at", 0) or 0)
            rows.append(
                {
                    "id": str(entry.get("id", "")),
                    "title": str(entry.get("title", "") or self._t("Jira AI Conversation")),
                    "preview": str(entry.get("preview", "")),
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M", time.localtime(updated_at)) if updated_at else "",
                    "messageCount": len(list(entry.get("messages") or [])),
                }
            )
        return rows

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
