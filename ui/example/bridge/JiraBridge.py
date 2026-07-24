from __future__ import annotations

import copy
import os
from pathlib import Path
from threading import Lock, Thread
import time
from typing import Any
from urllib.parse import quote

from PySide6.QtCore import QObject, Property, QT_TRANSLATE_NOOP, Signal, Slot
from PySide6.QtGui import QGuiApplication

from jira import (
    JiraConversationController,
    JiraWorkspaceService,
    create_jira_workspace_service,
    validate_workspace_result,
)
from example.bridge.AuthBridge import AuthBridge
from example.helper.TranslateHelper import TranslateHelper
from support.logging import smart_log

try:
    from example.helper.AppPaths import app_data_dir
except ImportError:  # pragma: no cover - direct unit-test imports may use the ui.example package path
    from ui.example.helper.AppPaths import app_data_dir

JIRA_BASE_URL = os.getenv("SMARTTEST_JIRA_BASE_URL", "https://jira.amlogic.com")
_OPTION_IDS = {
    "project": ("all_supported_projects", "rk", "tv", "ott", "iptv", "gh", "sh"),
    "board": ("open_work", "ready_for_test", "closed_bugs"),
    "timeframe": ("last_7_days", "last_30_days", "last_90_days", "this_year"),
    "status": ("open", "in_progress", "blocked", "ready_for_test", "verified", "resolved", "closed"),
    "priority": ("highest", "critical", "high", "medium", "low"),
    "issue_type": ("bug", "task", "story", "improvement"),
}
_SCOPE_DEFAULTS = {
    "raw_jql_text": "",
    "project_ids_csv": "all_supported_projects",
    "board_id": "",
    "board_label": "",
    "timeframe_id": "",
    "timeframe_label": "",
    "status_ids_csv": "",
    "priority_ids_csv": "",
    "issue_type_ids_csv": "bug",
    "keyword_text": "",
    "assignee_text": "",
    "reporter_text": "",
    "labels_text": "",
    "include_comments": False,
    "include_links": False,
    "only_mine": False,
}


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
    _applyDetailError = Signal(object)
    _applyFiltersResult = Signal(object)
    _applyProgress = Signal(object)

    def __init__(
        self,
        auth_bridge: AuthBridge,
        *,
        workspace_service: JiraWorkspaceService | None = None,
    ):
        super().__init__(QGuiApplication.instance())
        self._auth_bridge = auth_bridge
        self._loading = False
        self._detail_loading = False
        self._connected = False
        self._status_state = self._translated_state("Ready")
        self._analysis_summary_state = self._translated_state("Run a Jira query to get a live AI summary.")
        self._analysis_actions: list[str] = []
        self._issues: list[dict[str, Any]] = []
        self._saved_filters: list[dict[str, str]] = []
        self._selected_issue_index = 0
        self._displayed_total = 0
        self._can_load_more = False
        self._next_start_at = 0
        self._active_scope: dict[str, Any] = {}
        self._filters_loading = False
        self._conversation_controller = JiraConversationController(
            app_data_dir() / "Jira" / "ai_conversation_history.json",
            initial_row=JiraConversationController.system_row(
                message_template="Signed-in Jira access is ready. Ask in natural language to search issues and summarize risk.",
                timestamp_template="Workspace ready",
            ),
        )
        self._worker_seq = 0
        self._detail_worker_seq = 0
        self._filters_worker_seq = 0
        self._workspace_service = workspace_service
        self._workspace_service_injected = workspace_service is not None
        self._service_identity: tuple[str, str] | None = None
        self._state_lock = Lock()
        self._auth_bridge.authChanged.connect(self._handle_auth_changed)
        TranslateHelper().currentChanged.connect(self._handle_language_changed)
        self._applyResult.connect(self._on_worker_result)
        self._applyError.connect(self._on_worker_error)
        self._applyDetailResult.connect(self._on_detail_result)
        self._applyDetailError.connect(self._on_detail_error)
        self._applyFiltersResult.connect(self._on_filters_result)
        self._applyProgress.connect(self._on_progress_update)

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
            return self.tr(template).format(**dict(state.get("values") or {}))
        return str(state.get("text", "") or "")

    def _render_template(self, template: str, values: dict[str, Any] | None = None) -> str:
        return self.tr(str(template or "")).format(**dict(values or {}))

    def _render_conversation_row(self, row: dict[str, Any]) -> dict[str, Any]:
        rendered = dict(row)
        if "message_template" in row:
            rendered["message"] = self._render_template(
                str(row.get("message_template", "") or ""),
                row.get("message_values"),
            )
        if "timestamp_template" in row:
            rendered["timestamp"] = self._render_template(
                str(row.get("timestamp_template", "") or ""),
                row.get("timestamp_values"),
            )
        return rendered

    def _browse_option_label(self, kind: str, option_id: str) -> str:
        labels = {
            "project": {
                "all_supported_projects": self._t("All Supported Projects"),
                "rk": "RK",
                "tv": "TV",
                "ott": "OTT",
                "iptv": "IPTV",
                "gh": "GH",
                "sh": "SH",
            },
            "board": {
                "open_work": self._t("Open Work"),
                "ready_for_test": self._t("Ready for Test"),
                "closed_bugs": self._t("Closed Bugs"),
            },
            "timeframe": {
                "last_7_days": self._t("Last 7 Days"),
                "last_30_days": self._t("Last 30 Days"),
                "last_90_days": self._t("Last 90 Days"),
                "this_year": self._t("This Year"),
            },
            "status": {
                "open": self._t("Open"),
                "in_progress": self._t("In Progress"),
                "blocked": self._t("Blocked"),
                "ready_for_test": self._t("Ready for Test"),
                "verified": self._t("Verified"),
                "resolved": self._t("Resolved"),
                "closed": self._t("Closed"),
            },
            "priority": {
                "highest": self._t("Highest"),
                "critical": self._t("Critical"),
                "high": self._t("High"),
                "medium": self._t("Medium"),
                "low": self._t("Low"),
            },
            "issue_type": {
                "bug": self._t("Bug"),
                "task": self._t("Task"),
                "story": self._t("Story"),
                "improvement": self._t("Improvement"),
            },
        }
        return labels.get(kind, {}).get(option_id, str(option_id or ""))

    @staticmethod
    def _values(raw_value: Any) -> list[str]:
        values: list[str] = []
        for item in str(raw_value or "").replace(";", ",").split(","):
            clean = item.strip()
            if clean and clean not in values:
                values.append(clean)
        return values

    def _option_id(self, kind: str, value: Any) -> str:
        clean = str(value or "").strip()
        for option_id in _OPTION_IDS[kind]:
            if clean in {option_id, self._browse_option_label(kind, option_id)}:
                return option_id
        return _OPTION_IDS[kind][1 if kind == "timeframe" else 0]

    def _normalize_scope(self, scope: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            key: scope.get(key, default)
            for key, default in _SCOPE_DEFAULTS.items()
        }
        for key in ("include_comments", "include_links", "only_mine"):
            normalized[key] = bool(normalized[key])
        for kind, key in (
            ("project", "project_ids_csv"),
            ("status", "status_ids_csv"),
            ("priority", "priority_ids_csv"),
            ("issue_type", "issue_type_ids_csv"),
        ):
            normalized[key] = ",".join(
                value.lower()
                for value in self._values(normalized[key])
                if value.lower() in _OPTION_IDS[kind]
            )
        board_id = str(normalized["board_id"] or "").lower()
        if board_id not in _OPTION_IDS["board"]:
            board_id = self._option_id("board", normalized["board_label"])
        timeframe_id = str(normalized["timeframe_id"] or "").lower()
        if timeframe_id not in _OPTION_IDS["timeframe"]:
            timeframe_id = self._option_id("timeframe", normalized["timeframe_label"])
        normalized.update(
            board_id=board_id,
            board_label=self._browse_option_label("board", board_id),
            timeframe_id=timeframe_id,
            timeframe_label=self._browse_option_label("timeframe", timeframe_id),
        )
        return normalized

    def _request(
        self,
        scope: dict[str, Any],
        *,
        start_at: int = 0,
        append: bool = False,
    ) -> dict[str, Any]:
        request = self._normalize_scope(scope)
        request.update(
            selected_issue_index=self._selected_issue_index,
            start_at=start_at,
            append=append,
        )
        return request

    @staticmethod
    def _issue_key(issue: dict[str, Any]) -> str:
        return str(issue.get("keyId", "") or "").strip()

    def _apply_browse_result(self, payload: dict[str, Any]) -> None:
        incoming: list[dict[str, Any]] = []
        positions: dict[str, int] = {}
        for issue in payload["issues"]:
            row = copy.deepcopy(issue)
            key = self._issue_key(row)
            if key in positions:
                incoming[positions[key]] = row
            else:
                positions[key] = len(incoming)
                incoming.append(row)
        if payload["append"]:
            next_issues = copy.deepcopy(self._issues)
            positions = {
                self._issue_key(issue): index
                for index, issue in enumerate(next_issues)
            }
            for issue in incoming:
                key = self._issue_key(issue)
                if key in positions:
                    next_issues[positions[key]] = issue
                else:
                    positions[key] = len(next_issues)
                    next_issues.append(issue)
            selected = self._selected_issue_index
        else:
            next_issues = incoming
            selected = payload["selected_issue_index"]
        self._issues = next_issues
        self._selected_issue_index = (
            max(0, min(selected, len(next_issues) - 1)) if next_issues else 0
        )
        self._displayed_total = payload["displayed_total"]
        self._next_start_at = payload["next_start_at"]
        self._can_load_more = payload["can_load_more"]
        self._active_scope = (
            self._normalize_scope(payload["scope"]) if payload["scope"] else {}
        )

    def _apply_issue_detail(self, issue: Any) -> None:
        if not isinstance(issue, dict) or not (issue_key := self._issue_key(issue)):
            return
        for index, existing in enumerate(self._issues):
            if self._issue_key(existing) == issue_key:
                self._issues[index] = copy.deepcopy(issue)
                return

    def _reset_browse_state(self) -> None:
        self._issues = []
        self._saved_filters = []
        self._selected_issue_index = 0
        self._displayed_total = 0
        self._can_load_more = False
        self._next_start_at = 0
        self._active_scope = {}

    def _scope_summary(self) -> str:
        if not self._active_scope:
            return ""
        if jql := str(self._active_scope["raw_jql_text"] or "").strip():
            return f"{self._t('JQL')}: {jql}"
        not_limited = self._t("Not limited")

        def labels(kind: str, key: str, default: str = "") -> str:
            values = [
                self._browse_option_label(kind, value)
                for value in self._values(self._active_scope[key])
                if value in _OPTION_IDS[kind]
            ]
            return ", ".join(values) or default

        assignee = (
            self._t("Current user")
            if self._active_scope["only_mine"]
            else ", ".join(self._values(self._active_scope["assignee_text"])) or not_limited
        )
        parts = (
            ("Projects", labels("project", "project_ids_csv", self._t("All Supported Projects"))),
            ("Workflow Preset", self._browse_option_label("board", self._active_scope["board_id"])),
            ("Time Window", self._browse_option_label("timeframe", self._active_scope["timeframe_id"])),
            ("Statuses", labels("status", "status_ids_csv", not_limited)),
            ("Priorities", labels("priority", "priority_ids_csv", not_limited)),
            ("Issue Types", labels("issue_type", "issue_type_ids_csv", not_limited)),
            ("Keyword text", str(self._active_scope["keyword_text"] or "").strip() or not_limited),
            ("Assignee", assignee),
            ("Reporter", ", ".join(self._values(self._active_scope["reporter_text"])) or not_limited),
            ("Labels", ", ".join(self._values(self._active_scope["labels_text"])) or not_limited),
        )
        return " | ".join(f"{self._t(label)}: {value}" for label, value in parts)

    def _render_issue_row(self, issue: dict[str, Any]) -> dict[str, Any]:
        rendered = copy.deepcopy(issue)
        assignee = str(rendered.get("assignee", "") or "").strip()
        rendered["assignee"] = assignee or self._t("Unassigned")
        return rendered

    def _handle_language_changed(self) -> None:
        self.connectionChanged.emit()
        self.stateChanged.emit()

    def _cache_dir(self) -> Path:
        return app_data_dir() / "jira"

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

    def _ensure_workspace_service(self) -> JiraWorkspaceService:
        if self._workspace_service_injected:
            return self._workspace_service
        username = self._auth_bridge.currentUsername()
        _username, password = self._auth_bridge.transientCredential()
        if not username or not password:
            raise RuntimeError(self._t("LDAP session is missing Jira credentials. Please sign in again."))
        identity = (username, password)
        if self._workspace_service is not None and self._service_identity == identity:
            return self._workspace_service

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
        try:
            filters = self._ensure_workspace_service().fetch_saved_filters()
            self._applyFiltersResult.emit({"worker_id": worker_id, "filters": filters})
        except Exception:  # noqa: BLE001
            smart_log("JiraBridge favourite filters load failed", level="error", exc_info=True)
            self._applyFiltersResult.emit({"worker_id": worker_id, "filters": []})

    def _browse_scope(
        self,
        *,
        request: dict[str, Any],
        worker_id: int,
    ) -> None:
        try:
            result = self._ensure_workspace_service().browse(
                worker_id=worker_id,
                translated_state=self._translated_state,
                **request,
            )
            self._applyResult.emit(self._worker_result(result, worker_id))
        except Exception as exc:  # noqa: BLE001
            smart_log("JiraBridge browse failed", level="error", exc_info=True)
            self._applyError.emit({"worker_id": worker_id, "message": f"{exc}"})

    def _fetch_issue_detail(
        self,
        *,
        issue_key: str,
        include_comments: bool,
        include_links: bool,
        worker_id: int,
    ) -> None:
        try:
            result = self._ensure_workspace_service().fetch_issue_detail(
                worker_id=worker_id,
                issue_key=issue_key,
                include_comments=include_comments,
                include_links=include_links,
            )
            self._applyDetailResult.emit(self._worker_result(result, worker_id))
        except Exception as exc:  # noqa: BLE001
            smart_log("JiraBridge issue detail failed", level="error", exc_info=True)
            self._applyDetailError.emit({"worker_id": worker_id, "message": f"{exc}"})

    def _search_and_analyze(
        self,
        *,
        prompt: str,
        scope: dict[str, Any],
        include_user_message: bool,
        worker_id: int,
    ) -> None:
        try:
            self._applyProgress.emit({"worker_id": worker_id, "message": self._t("Analyzing request: preparing search scope...")})
            self._applyProgress.emit({"worker_id": worker_id, "message": self._t("Analyzing request: retrieving Jira issues...")})
            result = self._ensure_workspace_service().analyze(
                worker_id=worker_id,
                include_user_message=include_user_message,
                prompt=prompt,
                translated_state=self._translated_state,
                raw_state=self._raw_state,
                assistant_timestamp=self._t("Just now"),
                **scope,
            )
            self._applyProgress.emit({"worker_id": worker_id, "message": self._t("Analyzing request: generating response...")})
            self._applyResult.emit(self._worker_result(result, worker_id))
        except Exception as exc:  # noqa: BLE001
            smart_log("JiraBridge query failed", level="error", exc_info=True)
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
            request=self._request(
                {
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
            )
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
            self._conversation_controller.append_user(
                author=self._auth_bridge.currentUsername(),
                message=clean_prompt,
                timestamp=self._t("Just now"),
            )
        self.stateChanged.emit()
        self._start_analysis_worker(
            prompt=clean_prompt,
            scope=self._normalize_scope(
                {
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
            ),
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
        self._start_analysis_worker(
            prompt=clean_prompt,
            scope=self._normalize_scope(self._active_scope),
            include_user_message=False,
        )

    def _start_browse_worker(
        self,
        *,
        request: dict[str, Any],
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
            kwargs={"request": request, "worker_id": worker_id},
            daemon=True,
        ).start()

    def _start_analysis_worker(
        self,
        *,
        prompt: str,
        scope: dict[str, Any],
        include_user_message: bool,
    ) -> None:
        self._worker_seq += 1
        worker_id = self._worker_seq
        self._set_loading(True)
        self._conversation_controller.replace_progress(
            message=self._t("Searching Jira issues from your request..."),
            timestamp=self._t("Just now"),
        )
        self.stateChanged.emit()
        self._set_connection(
            connected=self._connected,
            status_state=self._translated_state("Analyzing Jira request..."),
        )
        Thread(
            target=self._search_and_analyze,
            kwargs={
                "prompt": prompt,
                "scope": scope,
                "include_user_message": include_user_message,
                "worker_id": worker_id,
            },
            daemon=True,
        ).start()

    @Slot(int, bool, bool)
    def selectIssue(self, index: int, include_comments: bool, include_links: bool) -> None:
        if index < 0 or index >= len(self._issues):
            return
        issue_key = self._issue_key(self._issues[index])
        if not issue_key:
            return
        self._selected_issue_index = index
        self.stateChanged.emit()
        self._detail_worker_seq += 1
        worker_id = self._detail_worker_seq
        self._detail_loading = True
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
        self._start_browse_worker(
            request=self._request(
                self._active_scope,
                start_at=self._next_start_at,
                append=True,
            )
        )

    @Slot()
    def clearConversation(self) -> None:
        self._invalidate_active_worker()
        self._conversation_controller.clear(
            initial_row=JiraConversationController.system_row(
                message_template="Session cleared. Ask a new Jira question when ready.",
                timestamp_template="Reset",
            )
        )
        self.stateChanged.emit()

    @Slot(str)
    def restoreConversation(self, conversation_id: str) -> None:
        self._invalidate_active_worker()
        self._conversation_controller.restore(conversation_id)
        self.stateChanged.emit()

    def _invalidate_active_worker(self) -> None:
        was_loading = self._loading
        self._worker_seq += 1
        self._conversation_controller.remove_progress()
        self._set_loading(False)
        if was_loading:
            self._set_connection(
                connected=self._connected,
                status_state=self._translated_state("Ready"),
            )

    def _handle_auth_changed(self) -> None:
        if self._auth_bridge.isAuthenticated() and self._auth_bridge.hasCredential():
            if not self._saved_filters:
                self._start_saved_filters_worker()
            return
        self._worker_seq += 1
        self._detail_worker_seq += 1
        self._filters_worker_seq += 1
        self._conversation_controller.remove_progress()
        self._set_loading(False)
        self._detail_loading = False
        self._reset_browse_state()
        self._filters_loading = False
        self._analysis_summary_state = self._translated_state("Sign in again to restore Jira access.")
        self._analysis_actions = []
        self._workspace_service = None
        self._service_identity = None
        self._set_connection(connected=False, status_state=self._translated_state("Signed out"))
        self.stateChanged.emit()

    @Slot(object)
    def _on_worker_result(self, payload: dict[str, Any]) -> None:
        worker_id = self._payload_worker_id(payload)
        if worker_id is None or worker_id != self._worker_seq:
            return
        try:
            validated = validate_workspace_result(payload)
            self._apply_browse_result(validated)
        except ValueError as exc:
            self._settle_worker_error(message=str(exc), append_conversation=False)
            return
        self._analysis_summary_state = validated["analysis_summary_state"]
        self._analysis_actions = validated["analysis_actions"]
        assistant_message = validated["assistant_message"].strip()
        self._conversation_controller.remove_progress()
        if assistant_message:
            self._conversation_controller.append_assistant(
                message=assistant_message,
                timestamp=validated["assistant_timestamp"],
            )
        self._conversation_controller.persist()
        self._set_connection(
            connected=validated["connected"],
            status_state=validated["status_state"],
        )
        self._set_loading(False)
        self.stateChanged.emit()

    @Slot(object)
    def _on_progress_update(self, payload: dict[str, Any]) -> None:
        worker_id = self._payload_worker_id(payload)
        if worker_id is None:
            return
        if worker_id != self._worker_seq:
            return
        message = str((payload or {}).get("message", "") or "").strip()
        if not message:
            return
        self._conversation_controller.replace_progress(message=message, timestamp=self._t("Just now"))
        self.stateChanged.emit()

    @Slot(object)
    def _on_filters_result(self, payload: dict[str, Any]) -> None:
        worker_id = self._payload_worker_id(payload)
        if worker_id is None:
            return
        if worker_id != self._filters_worker_seq:
            return
        self._saved_filters = [
            {
                "id": str(item.get("id", "")),
                "name": str(item.get("name", "")),
                "jql": str(item.get("jql", "")),
            }
            for item in (payload.get("filters") or [])
            if isinstance(item, dict)
        ]
        self._filters_loading = False
        self.stateChanged.emit()

    @Slot(object)
    def _on_detail_result(self, payload: dict[str, Any]) -> None:
        worker_id = self._payload_worker_id(payload)
        if worker_id is None:
            return
        if worker_id != self._detail_worker_seq:
            return
        self._detail_loading = False
        self._apply_issue_detail(payload.get("issue"))
        self.stateChanged.emit()

    @Slot(object)
    def _on_detail_error(self, payload: dict[str, Any]) -> None:
        worker_id = self._payload_worker_id(payload)
        if worker_id is None or worker_id != self._detail_worker_seq:
            return
        self._detail_loading = False
        self.stateChanged.emit()

    @Slot(object)
    def _on_worker_error(self, payload: dict[str, Any]) -> None:
        worker_id = self._payload_worker_id(payload)
        if worker_id is None:
            return
        if worker_id != self._worker_seq:
            return
        message = str((payload or {}).get("message", "") or self._t("Unknown Jira error"))
        self._settle_worker_error(message=message, append_conversation=True)

    def _settle_worker_error(self, *, message: str, append_conversation: bool) -> None:
        self._set_connection(
            connected=False,
            status_state=self._translated_state("Jira request failed: {message}", message=message),
        )
        self._analysis_summary_state = self._translated_state(
            "Jira request failed. Check the connection message above and sign in again if needed."
        )
        self._analysis_actions = []
        self._conversation_controller.remove_progress()
        if append_conversation:
            self._conversation_controller.append_system(
                message_template="Jira request failed. Check the connection message above and sign in again if needed.",
                timestamp_template="Error",
            )
        self._set_loading(False)
        self.stateChanged.emit()

    @staticmethod
    def _payload_worker_id(payload: Any) -> int | None:
        if not isinstance(payload, dict) or "worker_id" not in payload:
            return None
        try:
            return int(payload.get("worker_id", 0))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _worker_result(payload: Any, worker_id: int) -> dict[str, Any]:
        result = dict(payload) if isinstance(payload, dict) else {"invalid_result": payload}
        result["worker_id"] = worker_id
        return result

    @Slot(result="QVariantList")
    def projectFilterOptions(self):
        return [
            {"id": option_id, "label": self._browse_option_label("project", option_id)}
            for option_id in _OPTION_IDS["project"]
        ]

    @Slot(result="QVariantList")
    def boardOptions(self):
        return [self._browse_option_label("board", option_id) for option_id in _OPTION_IDS["board"]]

    @Slot(result="QVariantList")
    def timeframeOptions(self):
        return [
            self._browse_option_label("timeframe", option_id)
            for option_id in _OPTION_IDS["timeframe"]
        ]

    @Slot(result="QVariantList")
    def statusFilterOptions(self):
        return [
            {"id": option_id, "label": self._browse_option_label("status", option_id)}
            for option_id in _OPTION_IDS["status"]
        ]

    @Slot(result="QVariantList")
    def priorityFilterOptions(self):
        return [
            {"id": option_id, "label": self._browse_option_label("priority", option_id)}
            for option_id in _OPTION_IDS["priority"]
        ]

    @Slot(result="QVariantList")
    def issueTypeFilterOptions(self):
        return [
            {"id": option_id, "label": self._browse_option_label("issue_type", option_id)}
            for option_id in _OPTION_IDS["issue_type"]
        ]

    @Slot(result="QVariantList")
    def savedFilters(self):
        return copy.deepcopy(self._saved_filters)

    @Slot(result="QVariantList")
    def conversationRows(self):
        return [self._render_conversation_row(row) for row in self._conversation_controller.conversation_rows()]

    @Slot(result="QVariantList")
    def conversationHistoryRows(self):
        rows = []
        for entry in self._conversation_controller.history_rows():
            updated_at = int(entry.get("updated_at", 0) or 0)
            rows.append(
                {
                    "id": str(entry.get("id", "")),
                    "title": str(entry.get("title", "") or self._t("Jira AI Conversation")),
                    "preview": str(entry.get("preview", "")),
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M", time.localtime(updated_at)) if updated_at else "",
                    "messageCount": int(entry.get("message_count", 0) or 0),
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
        return self._render_issue_row(self._issues[self._selected_issue_index])

    @Slot(str, result=str)
    def issueBrowseUrl(self, issue_key: str) -> str:
        clean_key = str(issue_key or "").strip()
        if not clean_key:
            return ""
        return f"{JIRA_BASE_URL.rstrip('/')}/browse/{quote(clean_key)}"

    @Slot(result="QVariantList")
    def quickStats(self):
        high_priority = sum(
            str(issue.get("priority", "")).lower() in {"highest", "critical", "high"}
            for issue in self._issues
        )
        blocked = sum(
            str(issue.get("status", "")).lower() == "blocked"
            for issue in self._issues
        )
        ready = sum(
            str(issue.get("status", "")).lower() in {"ready for test", "verified", "resolved"}
            for issue in self._issues
        )
        return [
            {
                "label": self._t("Matched"),
                "value": str(self._displayed_total),
                "detail": self._t("{displayed} displayed in the current view").format(
                    displayed=len(self._issues)
                ),
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
                "value": str(ready),
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
        return self._scope_summary()

    def _get_filters_loading(self) -> bool:
        return self._filters_loading

    loading = Property(bool, _get_loading, notify=loadingChanged)
    connected = Property(bool, _get_connected, notify=connectionChanged)
    statusText = Property(str, _get_status_text, notify=connectionChanged)
    activeScopeSummary = Property(str, _get_active_scope_summary, notify=stateChanged)
    filtersLoading = Property(bool, _get_filters_loading, notify=stateChanged)
    quickViews = Property(
        "QVariantList",
        lambda self: [
            {
                "id": item["id"],
                "label": item["name"],
                "query": item["jql"],
            }
            for item in self._saved_filters
        ],
        notify=stateChanged,
    )
    activeQuickViewId = Property(str, lambda self: "", notify=stateChanged)
