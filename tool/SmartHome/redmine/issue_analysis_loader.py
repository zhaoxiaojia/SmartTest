from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Callable, Iterable

from tool.SmartHome.redmine.collector import RedmineContextCollector
from tool.SmartHome.redmine.models import RedmineContext
from tool.SmartHome.redmine.overdue import OverduePolicy, analyze_issue
from support.logging import smart_log


def project_specificity_score(name: str) -> tuple:
    value = str(name or "").strip()
    lower = value.casefold()
    digits = sum(char.isdigit() for char in value)
    return (1 if "android" in lower else 0, 1 if digits else 0, digits, sum(char in "._-" for char in value), -(1 if "project" in lower else 0), len(value))


def decision_diagnostic(result: dict) -> dict:
    keys = ("issue_id", "assignee", "party", "threshold_hours", "assignment_source", "assignment_start", "last_matching_update_author", "last_matching_update_time", "last_visible_journal_author", "last_visible_journal_time", "base_time", "elapsed_hours", "overdue_hours", "risk", "reason", "responsibility_type", "stale_type", "ignored_opposite_update_author", "ignored_opposite_update_time")
    return {key: result.get(key) for key in keys}


def consolidate_context(context: RedmineContext) -> RedmineContext:
    chosen = {}
    for project in context.projects:
        for issue in project.issues:
            current = chosen.get(issue.id)
            if current is None or project_specificity_score(project.name) > project_specificity_score(current[0].name):
                chosen[issue.id] = (project, issue)
    retained = set(chosen)
    projects = tuple(replace(project, issues=tuple(issue for issue in project.issues if issue.id in retained and chosen[issue.id][0].identifier == project.identifier)) for project in context.projects)
    return replace(context, projects=projects)


def _list_item_is_eligible(issue, policy: OverduePolicy) -> bool:
    tracker = str(issue.tracker or "").strip().casefold()
    status = str(issue.status or "").strip().casefold()
    subject = "".join(str(issue.subject or "").casefold().split())
    exclusions = ("".join(str(value).casefold().split()) for value in policy.title_exclusions)
    if status and status in policy.excluded_statuses:
        return False
    if tracker and tracker not in policy.trackers:
        return False
    if subject and any(value and value in subject for value in exclusions):
        return False
    return True


def analysis_work_count(context: RedmineContext, policy: OverduePolicy | None = None) -> int:
    policy = policy or OverduePolicy()
    consolidated = consolidate_context(context)
    return sum(_list_item_is_eligible(issue, policy) for project in consolidated.projects for issue in project.issues)


class IssueAnalysisLoader:
    def __init__(self, page, *, max_concurrency: int = 6, progress_callback: Callable[[int, int, str], None] | None = None, collector_factory=None):
        self._page = page
        self._limit = max(1, int(max_concurrency))
        self._progress = progress_callback
        self._collector_factory = collector_factory

    async def analyze(self, context: RedmineContext, *, aml_names: Iterable[str], policy: OverduePolicy | None = None) -> RedmineContext:
        context = consolidate_context(context)
        policy = policy or OverduePolicy()
        all_items = [(project, issue) for project in context.projects for issue in project.issues]
        work = [(project, issue) for project, issue in all_items if _list_item_is_eligible(issue, policy)]
        total, done = len(work), 0
        semaphore = asyncio.Semaphore(self._limit)
        analysis = {}
        details = []

        async def one(project, item):
            nonlocal done
            page = None
            try:
                async with semaphore:
                    page_context = getattr(self._page, "context", None)
                    if self._collector_factory:
                        collector = self._collector_factory(self._page)
                    elif page_context is not None and hasattr(page_context, "new_page"):
                        page = await page_context.new_page()
                        collector = RedmineContextCollector(page)
                    else:
                        collector = RedmineContextCollector(self._page)
                    detail = await collector.collect_issue_detail(item, project=project)
                issue_data = {
                    "tracker": detail.tracker or item.tracker,
                    "status": detail.attr("Status") or item.status,
                    "priority": detail.attr("Priority") or item.priority,
                    "assignee": detail.attr("Assignee") or item.assignee,
                    "subject": detail.subject or item.subject,
                    "created_at": detail.attr("Created") or detail.attr("Created on"),
                    "due_date": detail.attr("Due date"),
                    "start_date": detail.attr("Start date"),
                    "id": item.id,
                }
                journals = [{"author": j.author, "header": j.header, "created_at": j.created_at, "note": j.note, "details": j.details} for j in detail.comments]
                return item.id, detail, analyze_issue(issue=issue_data, journals=journals, aml_names=aml_names, policy=policy)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return item.id, None, {"issue_id": item.id, "assignee": item.assignee, "risk": "unknown", "reason": "detail_load_failed", "party": "", "responsibility_type": "", "stale_type": "", "elapsed_hours": None, "threshold_hours": None, "age_text": "", "error": str(exc)}
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass
                done += 1
                if self._progress:
                    self._progress(done, total, item.subject or item.id)

        for _project, item in all_items:
            if not _list_item_is_eligible(item, policy):
                analysis[item.id] = analyze_issue(issue={"id": item.id, "tracker": item.tracker, "status": item.status, "priority": item.priority, "assignee": item.assignee, "subject": item.subject}, journals=[], aml_names=aml_names, policy=policy)
        for issue_id, detail, result in await asyncio.gather(*(one(project, item) for project, item in work)):
            analysis[issue_id] = result
            if detail is not None:
                details.append(detail)
        for issue_id, result in analysis.items():
            smart_log("[REDMINE_OVERDUE] decision", domain="tool", source="IssueAnalysisLoader", level="debug", extra=decision_diagnostic(result))
        values = list(analysis.values())
        summary = {
            "amlogic": sum(item.get("party") == "amlogic" for item in values),
            "customer": sum(item.get("party") == "customer" for item in values),
            "unassigned": sum(item.get("responsibility_type") == "unassigned" for item in values),
            "stale": sum(bool(item.get("stale_type")) for item in values),
            "stale_amlogic": sum(item.get("stale_type") == "stale_amlogic" for item in values),
            "stale_customer": sum(item.get("stale_type") == "stale_customer" for item in values),
            "unknown": sum(item.get("risk") == "unknown" for item in values),
            "red": sum(item.get("risk") == "red" for item in values),
            "yellow": sum(item.get("risk") == "yellow" for item in values),
            "green": sum(item.get("risk") == "green" for item in values),
            "failures": sum(item.get("reason") == "detail_load_failed" for item in values),
        }
        smart_log("[REDMINE_OVERDUE] refresh summary", domain="tool", source="IssueAnalysisLoader", level="info", extra=summary)
        return replace(context, issues=tuple(details), raw={**context.raw, "issue_analysis": analysis, "issue_analysis_summary": summary})
