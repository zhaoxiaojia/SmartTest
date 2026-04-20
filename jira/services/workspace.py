from __future__ import annotations

import json
from typing import Any, Callable

from jira.services.ai_analysis_service import JiraAIAnalysisService
from jira.services.issue_service import JiraIssueService
from jira.services.payloads import build_analysis_result, build_browse_result, build_detail_result, build_scope_context
from jira.services.presenter import extract_actions, record_to_issue_row
from jira.services.query_builder import build_base_jql
from jira.services.specs import browse_specs, detail_specs


class JiraWorkspaceService:
    def __init__(
        self,
        *,
        base_url: str,
        issue_service: JiraIssueService,
        ai_service: JiraAIAnalysisService,
        max_display_issues: int = 50,
    ):
        self._base_url = base_url
        self._issue_service = issue_service
        self._ai_service = ai_service
        self._max_display_issues = max_display_issues

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
        base_jql = build_base_jql(
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
        extra_clause = "" if raw_jql_text.strip() else self._nl_clause(prompt, project_label=project_ids_csv)
        effective_jql = f"({base_jql}) AND ({extra_clause})" if extra_clause else base_jql
        full_dataset = self.requires_full_dataset(prompt)
        if full_dataset:
            records = self._issue_service.search_records(
                effective_jql,
                specs=specs,
                include_heavy=False,
                page_size=100,
                max_workers=6,
            )
            total_count = len(records)
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
        issues = [record_to_issue_row(record) for record in records]
        analysis_prompt = prompt.strip() or (
            f"Summarize the main Jira risks for {project_ids_csv} / {board_label} in {timeframe_label}."
        )
        analysis_response = self._ai_service.ask(
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
            can_load_more=(not full_dataset) and len(issues) < total_count,
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
            raw_state=raw_state,
            assistant_timestamp=assistant_timestamp,
        )
        result["analysis_actions"] = extract_actions(analysis_text)
        result["include_user_message"] = include_user_message
        result["prompt"] = prompt.strip()
        return result

    @staticmethod
    def requires_full_dataset(prompt: str) -> bool:
        normalized = (prompt or "").strip().lower()
        if normalized == "":
            return False
        markers = ("all issues", "all matched", "full dataset", "entire dataset", "全部", "所有", "全量", "完整数据")
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

    def _nl_clause(self, prompt: str, *, project_label: str) -> str:
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
            response = self._ai_service.ask(planning_prompt, model=None, max_tokens=200, temperature=0.0)
            text = response.text or ""
            if text.strip() == "":
                return ""
            payload = json.loads(text)
        except Exception:  # noqa: BLE001
            return ""
        return str(payload.get("jql_clause", "") or "").strip()

    @staticmethod
    def _fallback_analysis_text(issues: list[dict[str, Any]], total: int) -> str:
        if not issues:
            return "No Jira issues matched the current scope."
        top_issue = issues[0]
        return (
            f"{total} Jira issues matched the current scope. "
            f"Top issue: {top_issue['keyId']} ({top_issue['status']}, {top_issue['priority']}) - {top_issue['summary']}"
        )
