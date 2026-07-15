from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from AI.mcp.context import McpContextService
from jira_tool.services.issue_service import JiraIssueService
from jira_tool.services.payloads import build_analysis_result, build_scope_context
from jira_tool.services.presenter import extract_actions, record_to_issue_row
from jira_tool.services.query_builder import build_base_jql
from jira_tool.services.requests import JiraAnalysisRequest
from jira_tool.services.specs import detail_specs


class JiraAnalysisService:
    def __init__(
        self,
        *,
        base_url: str,
        issue_service: JiraIssueService,
        mcp_context_service: McpContextService | None = None,
        max_display_issues: int = 50,
        max_analysis_issues: int = 1000,
    ):
        self._base_url = base_url
        self._issue_service = issue_service
        self._mcp_context_service = mcp_context_service
        self._max_display_issues = max_display_issues
        self._max_analysis_issues = max_analysis_issues

    def analyze(self, request: JiraAnalysisRequest) -> dict[str, Any]:
        worker_id = request.worker_id
        raw_jql_text = request.raw_jql_text
        project_ids_csv = request.project_ids_csv
        board_id = request.board_id
        board_label = request.board_label
        timeframe_id = request.timeframe_id
        timeframe_label = request.timeframe_label
        status_ids_csv = request.status_ids_csv
        priority_ids_csv = request.priority_ids_csv
        issue_type_ids_csv = request.issue_type_ids_csv
        keyword_text = request.keyword_text
        assignee_text = request.assignee_text
        reporter_text = request.reporter_text
        labels_text = request.labels_text
        include_comments = request.include_comments
        include_links = request.include_links
        only_mine = request.only_mine
        include_user_message = request.include_user_message
        prompt = request.prompt
        translated_state = request.translated_state
        raw_state = request.raw_state
        assistant_timestamp = request.assistant_timestamp
        specs = detail_specs(include_comments=include_comments, include_links=include_links)
        nl_search_intent = _has_prompt_search_intent(prompt)
        extra_clause = _prompt_jql_clause(prompt) if nl_search_intent else ""
        if nl_search_intent and not extra_clause:
            extra_clause = self._nl_clause(prompt, project_label=project_ids_csv, mcp_context=[])
        if nl_search_intent and not extra_clause:
            raise ValueError(
                "SmartTest could not convert the natural-language search request into Jira JQL. "
                "Please make the search constraint more explicit or use the Jira filter fields."
            )
        base_jql = self._analysis_base_jql(
            raw_jql_text=raw_jql_text,
            project_ids_csv=project_ids_csv,
            board_id=board_id,
            timeframe_id=timeframe_id,
            status_ids_csv=status_ids_csv,
            priority_ids_csv=priority_ids_csv,
            issue_type_ids_csv=issue_type_ids_csv,
            keyword_text=keyword_text,
            assignee_text=assignee_text,
            reporter_text=reporter_text,
            labels_text=labels_text,
            only_mine=only_mine,
            prefer_prompt_scope=nl_search_intent and bool(extra_clause),
        )
        effective_jql = _combine_jql(base_jql, extra_clause)
        full_dataset = self.requires_full_dataset(prompt)
        route = "jira_api"
        _trace_workspace(
            "analyze_plan",
            worker_id=worker_id,
            full_dataset=full_dataset,
            capped_full_dataset=self._max_analysis_issues,
            extra_clause=extra_clause,
            jql=effective_jql,
            source="prompt" if nl_search_intent and extra_clause else "search_scope",
        )
        mcp_records: list[dict[str, Any]] = []
        if nl_search_intent:
            mcp_records = self._search_with_jira_mcp(effective_jql, limit=min(self._max_display_issues, 100))
            if mcp_records:
                route = "jira_mcp"
                _trace_workspace("mcp_jira_search_done", worker_id=worker_id, loaded=len(mcp_records))
            else:
                _trace_workspace("mcp_jira_search_empty", worker_id=worker_id, fallback="jira_api")
        records: list[Any]
        total_count = 0
        if mcp_records:
            route = "jira_mcp"
            records = mcp_records
            total_count = len(mcp_records)
            full_dataset = False
            _trace_workspace("mcp_jira_route_selected", worker_id=worker_id, total=total_count)
        elif full_dataset:
            if nl_search_intent:
                # Natural-language path should prefer responsiveness if MCP did not provide data.
                full_dataset = False
                _trace_workspace("full_dataset_downgraded", reason="mcp_empty_or_unavailable", worker_id=worker_id)
            else:
                _trace_workspace("full_dataset_keep", reason="scope_driven", worker_id=worker_id)
        if route != "jira_mcp":
            if full_dataset:
                page, _ = self._issue_service.search_page_records(
                    effective_jql,
                    specs=specs,
                    start_at=0,
                    max_results=1,
                )
                records = self._issue_service.search_records(
                    effective_jql,
                    specs=specs,
                    include_heavy=False,
                    page_size=100,
                    max_workers=6,
                    max_total_results=self._max_analysis_issues,
                )
                total_count = page.total
            else:
                page, records = self._issue_service.search_page_records(
                    effective_jql,
                    specs=specs,
                    start_at=0,
                    max_results=self._max_display_issues,
                )
                total_count = page.total
        if route == "jira_mcp":
            issues = [self._mcp_issue_to_row(record) for record in records]
        else:
            issues = [record_to_issue_row(record) for record in records]
        _trace_workspace(
            "issues_loaded",
            worker_id=worker_id,
            loaded=len(issues),
            total=total_count,
            truncated=full_dataset and len(issues) >= self._max_analysis_issues,
            route=route,
        )
        analysis_text = self._fallback_analysis_text(issues, total_count)
        result = build_analysis_result(
            worker_id=worker_id,
            base_url=self._base_url,
            returned_count=len(issues),
            total_count=total_count,
            issues=issues,
            analysis_text=analysis_text,
            append=False,
            next_start_at=len(issues),
            can_load_more=len(issues) < total_count,
            scope=build_scope_context(
                raw_jql_text=effective_jql if nl_search_intent else raw_jql_text,
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
            translated_state=translated_state,
            raw_state=raw_state,
            assistant_timestamp=assistant_timestamp,
        )
        result["analysis_actions"] = extract_actions(analysis_text)
        result["include_user_message"] = include_user_message
        result["prompt"] = prompt.strip()
        result["route"] = route
        return result

    def _mcp_context(self, prompt: str) -> list[dict[str, Any]]:
        if self._mcp_context_service is None:
            return []
        _trace_workspace("mcp_context_start", prompt=prompt[:120])
        context = self._mcp_context_service.enrich(prompt)
        _trace_workspace("mcp_context_done", items=len(context))
        return context

    def _search_with_jira_mcp(self, jql: str, *, limit: int) -> list[dict[str, Any]]:
        if self._mcp_context_service is None:
            return []
        fields = ["summary", "status", "assignee", "priority", "updated", "issuetype", "project"]
        attempts = [str(jql or "").strip()]
        relaxed = _relax_jql_for_retry(jql)
        if relaxed and relaxed not in attempts:
            attempts.append(relaxed)
        for idx, attempt_jql in enumerate(attempts, start=1):
            try:
                _trace_workspace(
                    "mcp_jira_search_start",
                    jql=attempt_jql,
                    limit=limit,
                    attempt=idx,
                    total_attempts=len(attempts),
                )
                issues = self._mcp_context_service.search_jira_issues(
                    jql=attempt_jql,
                    max_results=limit,
                    fields=fields,
                )
                _trace_workspace("mcp_jira_search_attempt_done", attempt=idx, returned=len(issues))
                if issues:
                    return issues
            except Exception as exc:  # noqa: BLE001
                _trace_workspace("mcp_jira_search_error", attempt=idx, error=str(exc))
        return []

    def _mcp_issue_to_row(self, issue: dict[str, Any]) -> dict[str, Any]:
        fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
        status_obj = fields.get("status") if isinstance(fields.get("status"), dict) else {}
        priority_obj = fields.get("priority") if isinstance(fields.get("priority"), dict) else {}
        assignee_obj = fields.get("assignee") if isinstance(fields.get("assignee"), dict) else {}
        issue_type_obj = fields.get("issuetype") if isinstance(fields.get("issuetype"), dict) else {}
        project_obj = fields.get("project") if isinstance(fields.get("project"), dict) else {}
        issue_key = str(issue.get("key", "") or issue.get("id", "")).strip()
        return {
            "keyId": issue_key,
            "summary": str(fields.get("summary", "") or ""),
            "status": str(status_obj.get("name", "") or fields.get("status", "")),
            "priority": str(priority_obj.get("name", "") or fields.get("priority", "")),
            "assignee": str(
                assignee_obj.get("displayName", "")
                or assignee_obj.get("name", "")
                or fields.get("assignee", "")
            ),
            "updated": str(fields.get("updated", "") or ""),
            "issueType": str(issue_type_obj.get("name", "") or fields.get("issuetype", "")),
            "project": str(project_obj.get("key", "") or fields.get("project", "")),
            "detail": str(fields.get("description", "") or ""),
            "comments": [],
            "links": [],
            "labels": list(fields.get("labels") or []),
        }

    def _analysis_base_jql(
        self,
        *,
        raw_jql_text: str,
        project_ids_csv: str,
        board_id: str,
        timeframe_id: str,
        status_ids_csv: str,
        priority_ids_csv: str,
        issue_type_ids_csv: str,
        keyword_text: str,
        assignee_text: str,
        reporter_text: str,
        labels_text: str,
        only_mine: bool,
        prefer_prompt_scope: bool,
    ) -> str:
        if prefer_prompt_scope:
            return "updated is not EMPTY ORDER BY updated DESC"
        return build_base_jql(
            raw_jql_text=raw_jql_text,
            project_ids_csv=project_ids_csv,
            board_id=board_id,
            timeframe_id=timeframe_id,
            status_ids_csv=status_ids_csv,
            priority_ids_csv=priority_ids_csv,
            issue_type_ids_csv=issue_type_ids_csv,
            keyword_text=keyword_text,
            assignee_text=assignee_text,
            reporter_text=reporter_text,
            labels_text=labels_text,
            only_mine=only_mine,
        )

    @staticmethod
    def requires_full_dataset(prompt: str) -> bool:
        normalized = (prompt or "").strip().lower()
        if normalized == "":
            return False
        markers = (
            "all issues",
            "all matched",
            "full dataset",
            "entire dataset",
            "aggregate",
            "aggregation",
            "distribution",
            "trend",
            "rank",
            "ranking",
            "top",
            "most",
            "category",
            "categories",
            "classify",
            "classification",
            "\u5168\u90e8",
            "\u6240\u6709",
            "\u5168\u91cf",
            "\u5b8c\u6574\u6570\u636e",
            "\u5206\u5e03",
            "\u8d8b\u52bf",
            "\u6392\u540d",
            "\u6392\u5e8f",
            "\u6700\u591a",
            "\u5360\u6bd4",
            "\u7edf\u8ba1",
            "\u5206\u7c7b",
        )
        return any(marker in normalized for marker in markers)

    def _nl_clause(self, prompt: str, *, project_label: str, mcp_context: list[dict[str, Any]] | None = None) -> str:
        del prompt, project_label, mcp_context
        _trace_workspace("nl_clause_disabled")
        return ""

    @staticmethod
    def _fallback_analysis_text(issues: list[dict[str, Any]], total: int) -> str:
        if not issues:
            return "No Jira issues matched the current scope."
        top_issue = issues[0]
        return (
            f"{total} Jira issues matched the current scope. "
            f"Top issue: {top_issue['keyId']} ({top_issue['status']}, {top_issue['priority']}) - {top_issue['summary']}"
        )

def _compact_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "keyId": issue.get("keyId", ""),
        "summary": issue.get("summary", ""),
        "status": issue.get("status", ""),
        "priority": issue.get("priority", ""),
        "issueType": issue.get("issueType", ""),
        "labels": issue.get("labels", []),
        "components": issue.get("components", []),
        "detail": str(issue.get("detail", "") or "")[:180],
    }


def _combine_jql(base_jql: str, extra_clause: str) -> str:
    clean_base = base_jql.strip()
    clean_extra = extra_clause.strip()
    if not clean_extra:
        return clean_base
    base_without_order, order_clause = _split_order_by(clean_base)
    if not base_without_order:
        return f"({clean_extra}) {order_clause}".strip()
    return f"({base_without_order}) AND ({clean_extra}) {order_clause}".strip()


def _relax_jql_for_retry(jql: str) -> str:
    text = str(jql or "").strip()
    if not text:
        return text
    text = re.sub(r"\bcreated\s*>=\s*-[0-9]+[dw]\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bupdated\s*>=\s*-[0-9]+[dw]\b", "", text, flags=re.IGNORECASE)
    base, _order = _split_order_by(text)
    base = re.sub(r"\s{2,}", " ", base)
    base = re.sub(r"\(\s*\)", "", base)
    base = re.sub(r"\bAND\s+AND\b", "AND", base, flags=re.IGNORECASE).strip()
    if not base:
        return "updated is not EMPTY ORDER BY updated DESC"
    return f"{base} ORDER BY updated DESC"


def _split_order_by(jql: str) -> tuple[str, str]:
    marker = " order by "
    lower = jql.lower()
    index = lower.rfind(marker)
    if index < 0:
        return jql, "ORDER BY updated DESC"
    return jql[:index].strip(), jql[index + 1 :].strip()


def _strip_json_response(text: str) -> str:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean = "\n".join(lines).strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end >= start:
        return clean[start : end + 1]
    return clean


def _has_natural_language_search_intent(prompt: str) -> bool:
    normalized = (prompt or "").strip().lower()
    if normalized == "":
        return False
    markers = (
        "search",
        "find",
        "query",
        "keyword",
        "contains",
        "related to",
        "\u641c\u7d22",
        "\u68c0\u7d22",
        "\u67e5\u8be2",
        "\u67e5\u627e",
        "\u5173\u952e\u8bcd",
        "\u5173\u952e\u5b57",
        "\u5305\u542b",
        "\u76f8\u5173",
    )
    return any(marker in normalized for marker in markers)


def _has_prompt_search_intent(prompt: str) -> bool:
    normalized = (prompt or "").strip().lower()
    if _has_natural_language_search_intent(prompt):
        return True
    if not _contains_searchable_token(normalized):
        return False
    analysis_markers = (
        "analyze",
        "analysis",
        "distribution",
        "trend",
        "rank",
        "most",
        "category",
        "classify",
        "\u5206\u6790",
        "\u5206\u5e03",
        "\u8d8b\u52bf",
        "\u6392\u540d",
        "\u6700\u591a",
        "\u5206\u7c7b",
        "\u7edf\u8ba1",
        "\u8fd1\u534a\u5e74",
        "\u6700\u8fd1",
    )
    return any(marker in normalized for marker in analysis_markers)


def _prompt_jql_clause(prompt: str) -> str:
    normalized = (prompt or "").strip().lower()
    clauses: list[str] = []
    token = _first_searchable_token(normalized)
    if token:
        clauses.append(f'text ~ "{_escape_jql_string(token)}"')
    if "bug" in normalized or "bugs" in normalized:
        clauses.append("issuetype = Bug")
    time_clause = _prompt_time_clause(normalized)
    if time_clause:
        clauses.append(time_clause)
    return " AND ".join(_unique_values(clauses))


def _first_searchable_token(text: str) -> str:
    stop_words = {
        "jira",
        "bug",
        "bugs",
        "issue",
        "issues",
        "analyze",
        "analysis",
        "distribution",
        "trend",
        "category",
        "classify",
        "find",
        "search",
        "query",
        "recent",
        "last",
        "half",
        "year",
    }
    for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9_.-]{1,}\b", text):
        token = match.group(0).lower()
        if token not in stop_words:
            return token
    return ""


def _prompt_time_clause(text: str) -> str:
    if any(marker in text for marker in ("\u8fd1\u534a\u5e74", "\u6700\u8fd1\u534a\u5e74", "half year", "six months", "6 months")):
        return "created >= -26w"
    if any(marker in text for marker in ("\u8fd1\u4e00\u5e74", "\u6700\u8fd1\u4e00\u5e74", "last year", "one year", "12 months")):
        return "created >= -52w"
    if any(marker in text for marker in ("\u8fd1\u4e00\u4e2a\u6708", "\u6700\u8fd1\u4e00\u4e2a\u6708", "\u6700\u8fd130\u5929", "last 30 days")):
        return "created >= -30d"
    match = re.search(r"(?:last|recent)\s*(\d+)\s*(?:days|day)", text)
    if match:
        return f"created >= -{int(match.group(1))}d"
    match = re.search(r"(?:last|recent)\s*(\d+)\s*(?:weeks|week)", text)
    if match:
        return f"created >= -{int(match.group(1))}w"
    match = re.search(r"(?:last|recent)\s*(\d+)\s*(?:months|month)", text)
    if match:
        return f"created >= -{int(match.group(1)) * 4}w"
    return ""


def _escape_jql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _unique_values(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result


def _should_use_mcp_context(prompt: str) -> bool:
    normalized = (prompt or "").strip().lower()
    markers = (
        "mcp",
        "spec",
        "datasheet",
        "confluence",
        "opengrok",
        "gerrit",
        "jenkins",
        "\u89c4\u683c",
        "\u6587\u6863",
        "\u6e90\u7801",
        "\u4ee3\u7801",
        "\u6784\u5efa",
        "\u6d41\u6c34\u7ebf",
    )
    return any(marker in normalized for marker in markers)


def _contains_searchable_token(text: str) -> bool:
    stop_words = {
        "jira",
        "bug",
        "bugs",
        "issue",
        "issues",
        "analyze",
        "analysis",
        "distribution",
        "trend",
        "category",
        "classify",
    }
    for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9_.-]{1,}\b", text):
        token = match.group(0).lower()
        if token not in stop_words:
            return True
    return False


def _trace_workspace(stage: str, **values: Any) -> None:
    details = " ".join(f"{key}={values[key]}" for key in sorted(values))
    from support.logging import smart_log

    smart_log(
        "%s %s",
        stage,
        details,
        level="debug",
        domain="jira",
        source="jira.services.workspace",
        extra={"stage": stage, **values},
    )


def _trace_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
