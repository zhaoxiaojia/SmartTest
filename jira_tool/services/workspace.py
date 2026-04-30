from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable

from AI.core.errors import AIRequestError
from AI.mcp.context import McpContextService
from jira_tool.services.ai_analysis_service import JiraAIAnalysisService
from jira_tool.services.issue_service import JiraIssueService
from jira_tool.services.payloads import build_analysis_result, build_browse_result, build_detail_result, build_scope_context
from jira_tool.services.presenter import extract_actions, record_to_issue_row
from jira_tool.services.query_builder import build_base_jql
from jira_tool.services.specs import browse_specs, detail_specs


class JiraWorkspaceService:
    def __init__(
        self,
        *,
        base_url: str,
        issue_service: JiraIssueService,
        ai_service: JiraAIAnalysisService,
        mcp_context_service: McpContextService | None = None,
        max_display_issues: int = 50,
        max_analysis_issues: int = 1000,
    ):
        self._base_url = base_url
        self._issue_service = issue_service
        self._ai_service = ai_service
        self._mcp_context_service = mcp_context_service
        self._max_display_issues = max_display_issues
        self._max_analysis_issues = max_analysis_issues

    def fetch_saved_filters(self) -> list[dict[str, str]]:
        return self._normalize_saved_filters(self._issue_service._client.fetch_favourite_filters())

    def browse(
        self,
        *,
        worker_id: int,
        selected_issue_index: int,
        raw_jql_text: str,
        project_ids_csv: str,
        board_id: str,
        board_label: str,
        timeframe_id: str,
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
        translated_state: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        specs = browse_specs()
        plan = self._issue_service._registry.build_plan(specs, include_heavy=False)
        effective_jql = build_base_jql(
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
        page = self._issue_service._client.search_page(
            effective_jql,
            start_at=start_at,
            max_results=min(self._max_display_issues, 25),
            fields=list(plan.jira_fields),
            expand=list(plan.expand) or None,
        )
        records = [self._issue_service.project_issue(issue, list(plan.active_specs)) for issue in page.issues]
        issues = [record_to_issue_row(record) for record in records]
        return build_browse_result(
            worker_id=worker_id,
            base_url=self._base_url,
            loaded_count=start_at + len(issues),
            total_count=page.total,
            issues=issues,
            append=append,
            selected_issue_index=0 if not append else selected_issue_index,
            next_start_at=page.start_at + len(page.issues),
            can_load_more=(page.start_at + len(page.issues)) < page.total,
            scope=build_scope_context(
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
            translated_state=translated_state,
        )

    def fetch_issue_detail(
        self,
        *,
        worker_id: int,
        issue_key: str,
        include_comments: bool,
        include_links: bool,
    ) -> dict[str, Any]:
        record = self._issue_service.hydrate_issue(
            issue_key,
            specs=detail_specs(include_comments=include_comments, include_links=include_links),
        )
        return build_detail_result(worker_id=worker_id, issue=record_to_issue_row(record))

    def analyze(
        self,
        *,
        worker_id: int,
        raw_jql_text: str,
        project_ids_csv: str,
        board_id: str,
        board_label: str,
        timeframe_id: str,
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
        prompt: str,
        translated_state: Callable[..., dict[str, Any]],
        raw_state: Callable[[str], dict[str, Any]],
        assistant_timestamp: str,
        ) -> dict[str, Any]:
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
                plan = self._issue_service._registry.build_plan(specs, include_heavy=False)
                page = self._issue_service._client.search_page(
                    effective_jql,
                    max_results=1,
                    fields=list(plan.jira_fields),
                    expand=list(plan.expand) or None,
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
                plan = self._issue_service._registry.build_plan(specs, include_heavy=False)
                page = self._issue_service._client.search_page(
                    effective_jql,
                    max_results=self._max_display_issues,
                    fields=list(plan.jira_fields),
                    expand=list(plan.expand) or None,
                )
                records = [self._issue_service.project_issue(issue, list(plan.active_specs)) for issue in page.issues]
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
        analysis_prompt = prompt.strip() or (
            f"Summarize the main Jira risks for {project_ids_csv} / {board_label} in {timeframe_label}."
        )
        mcp_context = self._mcp_context(prompt) if _should_use_mcp_context(prompt) else []
        jira_context = self._build_analysis_context(
            prompt=analysis_prompt,
            effective_jql=effective_jql,
            issues=issues,
            total_count=total_count,
            mcp_context=mcp_context,
        )
        try:
            analysis_response = self._ai_service.ask(
                analysis_prompt,
                jira_context=jira_context,
                max_tokens=600,
                temperature=0.2,
            )
            analysis_text = (analysis_response.text or "").strip()
            if analysis_text == "":
                analysis_text = self._fallback_analysis_text(issues, total_count)
        except AIRequestError as exc:
            _trace_workspace("analysis_ai_retry_start", worker_id=worker_id, reason=str(exc)[:180])
            retry_context = self._build_retry_analysis_context(
                issues=issues,
                total_count=total_count,
                effective_jql=effective_jql,
            )
            try:
                retry_prompt = (
                    f"{analysis_prompt}\n\n"
                    "Respond in markdown. Keep the output concise and structured with headings/bullets/table."
                )
                retry_response = self._ai_service.ask(
                    retry_prompt,
                    jira_context=retry_context,
                    max_tokens=700,
                    temperature=0.2,
                )
                analysis_text = (retry_response.text or "").strip()
                if analysis_text == "":
                    analysis_text = self._fallback_analysis_text(issues, total_count)
                _trace_workspace("analysis_ai_retry_done", worker_id=worker_id, mode="light_context")
            except Exception as retry_exc:  # noqa: BLE001
                _trace_workspace("analysis_ai_fallback", worker_id=worker_id, reason=str(retry_exc)[:180])
                analysis_text = self._fallback_analysis_text_with_aggregate(issues, total_count, reason=str(retry_exc))
        except Exception as exc:  # noqa: BLE001
            _trace_workspace("analysis_unexpected_fallback", worker_id=worker_id, reason=str(exc)[:180])
            analysis_text = self._fallback_analysis_text_with_aggregate(issues, total_count, reason=str(exc))
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

    def _build_analysis_context(
        self,
        *,
        prompt: str,
        effective_jql: str,
        issues: list[dict[str, Any]],
        total_count: int,
        mcp_context: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {
            "jql": effective_jql,
            "returned_issue_count": len(issues),
            "total_issue_count": total_count,
        }
        if mcp_context:
            context["mcp_context"] = mcp_context
        if len(issues) >= self._max_analysis_issues:
            context["analysis_limit_note"] = (
                f"Analysis is capped at the first {self._max_analysis_issues} returned issues. "
                "Ask the user to narrow the Jira search scope if they need a complete analysis."
            )
        compact_issues = [_compact_issue(issue) for issue in issues]
        if len(issues) <= 200:
            context["issues"] = compact_issues[:120]
            context["issue_sample_note"] = (
                f"Only the first {len(context['issues'])} compact issues are included to control token usage."
            )
            return context
        _trace_workspace("aggregate_context_start", issues=len(issues))
        context["issues"] = compact_issues[:60]
        context["issue_sample_note"] = (
            f"Only the first {len(context['issues'])} compact issues are included as examples. "
            f"issue_aggregate covers all {len(issues)} returned issues."
        )
        context["issue_aggregate"] = _aggregate_issues(issues)
        return context

    def _build_retry_analysis_context(
        self,
        *,
        issues: list[dict[str, Any]],
        total_count: int,
        effective_jql: str,
    ) -> dict[str, Any]:
        return {
            "jql": effective_jql,
            "returned_issue_count": len(issues),
            "total_issue_count": total_count,
            "issues": [_compact_issue(issue) for issue in issues[:24]],
            "issue_aggregate": _aggregate_issues(issues),
            "retry_mode": "light_context",
            "issue_sample_note": "Retry with reduced issue sample to improve response stability.",
        }

    def _summarize_issue_batches(self, *, prompt: str, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        batch_size = 100
        for batch_index, start in enumerate(range(0, len(issues), batch_size), start=1):
            batch = issues[start : start + batch_size]
            summaries.append(self._summarize_issue_batch(prompt=prompt, batch_index=batch_index, issues=batch))
        return summaries

    def _summarize_issue_batch(
        self,
        *,
        prompt: str,
        batch_index: int,
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        batch_prompt = (
            "Summarize this Jira issue batch for the user's analysis request.\n"
            'Return JSON only with this schema: {"batch_index": number, "issue_count": number, '
            '"patterns": [{"name": string, "count": number, "evidence_keys": [string]}], "risks": [string]}.\n'
            "Use only this batch. Infer useful patterns from the issue text and metadata; do not use fixed categories unless the user asked for them."
        )
        batch_context = {
            "user_request": prompt,
            "batch_index": batch_index,
            "issue_count": len(issues),
            "issues": [_compact_issue(issue) for issue in issues],
        }
        _trace_workspace("batch_summary_request", batch_index=batch_index, issue_count=len(issues))
        try:
            response = self._ai_service.ask(batch_prompt, jira_context=batch_context, max_tokens=700, temperature=0.0)
            payload = json.loads(response.text or "")
            if isinstance(payload, dict):
                payload.setdefault("batch_index", batch_index)
                payload.setdefault("issue_count", len(issues))
                return payload
        except Exception as exc:  # noqa: BLE001
            return {
                "batch_index": batch_index,
                "issue_count": len(issues),
                "summary_error": str(exc),
                "sample_issues": [_compact_issue(issue) for issue in issues[:10]],
            }
        return {
            "batch_index": batch_index,
            "issue_count": len(issues),
            "summary_error": "Batch summary did not return a JSON object.",
            "sample_issues": [_compact_issue(issue) for issue in issues[:10]],
        }

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

    def _nl_clause(self, prompt: str, *, project_label: str, mcp_context: list[dict[str, Any]] | None = None) -> str:
        clean_prompt = prompt.strip()
        if clean_prompt == "":
            return ""
        context_text = json.dumps(mcp_context or [], ensure_ascii=False, indent=2)
        planning_prompt = (
            "Convert the user request into one extra Jira JQL clause.\n"
            'Return JSON only with this schema: {"jql_clause": string}.\n'
            "Rules:\n"
            "- Return only an additional clause, not a full query.\n"
            "- Use only Jira fields: summary, description, text, status, priority, assignee, reporter, labels, component, issuekey.\n"
            "- Convert natural-language search constraints into JQL filters; for free-text keyword constraints use text ~ \"keyword\".\n"
            "- The user's current message is the primary source for search constraints; do not inherit UI search scope unless the user mentions it.\n"
            "- Include product names, chip names, issue type, and time ranges from the user's text when they are stated.\n"
            "- Use Internal MCP context to understand company-specific terms, chips, products, modules, and aliases before building JQL.\n"
            "- Do not convert the analysis question itself into a filter unless it clearly narrows the Jira search scope.\n"
            "- If the prompt is mainly analytical and adds no filter, return an empty string.\n"
            f"- Current project scope label: {project_label}.\n"
            f"- User prompt: {clean_prompt}\n"
            f"Internal MCP context:\n{context_text}"
        )
        try:
            _trace_workspace("nl_clause_start", prompt=clean_prompt[:120])
            response = self._ai_service.ask(planning_prompt, model=None, max_tokens=200, temperature=0.0)
            text = response.text or ""
            if text.strip() == "":
                _trace_workspace("nl_clause_empty")
                return ""
            payload = json.loads(_strip_json_response(text))
        except Exception:  # noqa: BLE001
            _trace_workspace("nl_clause_failed")
            return ""
        clause = str(payload.get("jql_clause", "") or "").strip()
        _trace_workspace("nl_clause_done", clause=clause)
        return clause

    @staticmethod
    def _fallback_analysis_text(issues: list[dict[str, Any]], total: int) -> str:
        if not issues:
            return "No Jira issues matched the current scope."
        top_issue = issues[0]
        return (
            f"{total} Jira issues matched the current scope. "
            f"Top issue: {top_issue['keyId']} ({top_issue['status']}, {top_issue['priority']}) - {top_issue['summary']}"
        )

    @staticmethod
    def _fallback_analysis_text_with_aggregate(issues: list[dict[str, Any]], total: int, *, reason: str) -> str:
        if not issues:
            return "AI service is temporarily unavailable. No Jira issues matched the current scope."
        by_status = _top_counts((issue.get("status", "") for issue in issues), limit=3)
        by_priority = _top_counts((issue.get("priority", "") for issue in issues), limit=3)
        top_issue = issues[0]
        status_text = ", ".join(f"{item['name']}({item['count']})" for item in by_status) or "N/A"
        priority_text = ", ".join(f"{item['name']}({item['count']})" for item in by_priority) or "N/A"
        return (
            "AI service is temporarily unavailable; showing an automatic Jira summary.\n"
            f"Matched issues: {total}\n"
            f"Top statuses: {status_text}\n"
            f"Top priorities: {priority_text}\n"
            f"Top issue: {top_issue.get('keyId', '')} - {top_issue.get('summary', '')}\n"
            f"Reason: {reason[:220]}"
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


def _aggregate_issues(issues: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "issue_count": len(issues),
        "by_status": _top_counts(issue.get("status", "") for issue in issues),
        "by_priority": _top_counts(issue.get("priority", "") for issue in issues),
        "by_issue_type": _top_counts(issue.get("issueType", "") for issue in issues),
        "by_component": _top_counts(_iter_values(issue.get("components", [])) for issue in issues),
        "by_label": _top_counts(_iter_values(issue.get("labels", [])) for issue in issues),
        "summary_keywords": _top_summary_terms(issues),
    }


def _top_counts(values: Any, *, limit: int = 20) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for value in values:
        if isinstance(value, (list, tuple, set)):
            candidates = value
        else:
            candidates = [value]
        for candidate in candidates:
            clean = str(candidate or "").strip()
            if clean:
                counts[clean] = counts.get(clean, 0) + 1
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))[:limit]
    ]


def _iter_values(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return [str(values)] if str(values or "").strip() else []
    return [str(value) for value in values if str(value or "").strip()]


def _top_summary_terms(issues: list[dict[str, Any]], *, limit: int = 30) -> list[dict[str, Any]]:
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "bug",
        "issue",
        "issues",
        "jira",
        "test",
        "failed",
        "failure",
    }
    counts: dict[str, int] = {}
    for issue in issues:
        text = f"{issue.get('summary', '')} {issue.get('detail', '')}".lower()
        for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9_.-]{2,}\b", text):
            token = match.group(0)
            if token in stop_words:
                continue
            counts[token] = counts.get(token, 0) + 1
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


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
    print(f"{_trace_timestamp()} [JIRA_WORKSPACE] {stage} {details}".rstrip())


def _trace_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
