from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable

from support.jira_integration.core import IssueStore, UnifiedIssue
from tool.SmartHome.redmine import context_store
from tool.SmartHome.redmine.models import (
    RedmineContext,
    RedmineIssueDetail,
    RedmineIssueListItem,
    RedmineProject,
)
from tool.SmartHome.redmine.view_model import (
    actionable_rows,
    context_payload,
    detail_row_from_unified,
    issue_row_from_unified,
    replace_detail,
    unified_issue,
    view,
)


_QUICK_VIEW_IDS = frozenset({"my_assigned", "watched"})
_FILTER_KEYS = ("project", "status", "type", "subject", "text")


@dataclass(frozen=True)
class IssueSource:
    project: RedmineProject | None = None
    item: RedmineIssueListItem | None = None
    detail: RedmineIssueDetail | None = None
    issue: UnifiedIssue | None = None
    needs_detail: bool = False


@dataclass(frozen=True)
class IssueSnapshot:
    context_payload: dict[str, Any]
    filters: dict[str, str]
    project_filter_labels: tuple[str, ...]
    status_filter_labels: tuple[str, ...]
    type_filter_labels: tuple[str, ...]
    issue_rows: tuple[dict[str, Any], ...]
    selected_issue: dict[str, Any]
    actionable_issues: tuple[dict[str, Any], ...]
    selected_id: str


@dataclass(frozen=True)
class EnrichmentProjection:
    issue_rows: tuple[dict[str, Any], ...]
    source: IssueSource


class RedmineIssueController:
    """Canonical owner of Redmine issue projection, selection, and persistence."""

    def __init__(
        self,
        *,
        account: str = "",
        all_projects: str,
        all_statuses: str,
        all_types: str,
    ) -> None:
        self._account = str(account or "")
        self._all_projects = str(all_projects)
        self._all_statuses = str(all_statuses)
        self._all_types = str(all_types)
        self._store = IssueStore()
        self._active_view_id = "my_assigned"
        self._reset_projection()

    @property
    def active_view_id(self) -> str:
        return self._active_view_id

    @property
    def snapshot(self) -> IssueSnapshot:
        records = self._store.issue_list
        selected_id = str(self._store.selected_id or "")
        return IssueSnapshot(
            context_payload=context_payload(
                records,
                account=self._account,
                source_url=self._source_context.source_url,
                filters=self._filters,
                selected_issue_id=selected_id,
            ),
            filters=dict(self._filters),
            project_filter_labels=self._project_filter_labels,
            status_filter_labels=self._status_filter_labels,
            type_filter_labels=self._type_filter_labels,
            issue_rows=tuple(issue_row_from_unified(issue) for issue in records),
            selected_issue=detail_row_from_unified(self._store.selected_issue),
            actionable_issues=tuple(actionable_rows(records)),
            selected_id=selected_id,
        )

    def reset(self, account: str = "") -> IssueSnapshot:
        self._account = str(account or "")
        self._active_view_id = "my_assigned"
        self._reset_projection()
        return self.snapshot

    def set_account(self, account: str) -> None:
        self._account = str(account or "")
        if self._source_context.account != self._account:
            self._source_context = replace(self._source_context, account=self._account)

    def activate_view(self, view_id: str) -> None:
        self._active_view_id = str(view_id or "")

    def filters_for_search(self, requested: dict[str, Any] | None = None) -> dict[str, str]:
        source = context_store.load_filters(self._account) if requested is None else requested
        return _normalize_filters(source)

    def enrichment_projection(
        self, context: RedmineContext, filters: dict[str, Any] | None
    ) -> EnrichmentProjection:
        projected = view(
            context,
            all_projects=self._all_projects,
            all_statuses=self._all_statuses,
            filters=_normalize_filters(filters),
        )
        issue_id = str(projected.get("selectedIssueId") or "")
        project, item = context.item_for_issue(issue_id)
        detail = next((entry for entry in context.issues if entry.id == issue_id), None)
        return EnrichmentProjection(
            tuple(projected.get("issueRows") or ()),
            IssueSource(project=project, item=item, detail=detail),
        )

    def load_cached(self) -> bool:
        view_id = self._active_view_id
        cached = (
            context_store.load_quick_view(self._account, view_id)
            if view_id in _QUICK_VIEW_IDS
            else context_store.load_view(self._account)
        )
        if not cached:
            return False
        records = cached["issue_list"]
        if not isinstance(records, list) or any(
            not isinstance(issue, UnifiedIssue) for issue in records
        ):
            raise TypeError("Cached issue_list must contain UnifiedIssue records")
        self._source_context = RedmineContext(account=self._account)
        self._filters = _normalize_filters(cached.get("filters"))
        self._replace_records(records, cached.get("selected_issue_id"))
        return True

    def replace_result(
        self,
        context: RedmineContext,
        *,
        filters: dict[str, Any] | None,
        selected_detail: RedmineIssueDetail | None = None,
        clone_status: dict[str, Any] | None = None,
    ) -> IssueSnapshot:
        return self._replace_result(
            context,
            filters=filters,
            selected_detail=selected_detail,
            clone_status=clone_status,
            persist=True,
        )

    def _replace_result(
        self,
        context: RedmineContext,
        *,
        filters: dict[str, Any] | None,
        selected_detail: RedmineIssueDetail | None = None,
        clone_status: dict[str, Any] | None = None,
        persist: bool,
    ) -> IssueSnapshot:
        if selected_detail is not None and not any(
            detail.id == selected_detail.id for detail in context.issues
        ):
            context = replace_detail(context, selected_detail)
        projected = view(
            context,
            all_projects=self._all_projects,
            all_statuses=self._all_statuses,
            filters=_normalize_filters(filters),
            selected_detail=selected_detail,
        )
        incoming = context_store.reconcile_issue_records(
            self._account,
            projected["issue_list"],
            known_records=self._store.issue_list,
        )
        selected_id = str(projected.get("selectedIssueId") or "")
        previous_id = str(self._store.selected_id or "")
        if previous_id and any(
            issue.id == previous_id for issue in incoming
        ):
            selected_id = previous_id
        self._source_context = context
        self._filters = _normalize_filters(projected.get("filters"))
        self._project_filter_labels = tuple(
            projected.get("projectFilterLabels") or (self._all_projects,)
        )
        self._status_filter_labels = tuple(
            projected.get("statusFilterLabels")
            or (self._all_statuses, "Open", "Closed")
        )
        type_labels = list(projected.get("typeFilterLabels") or (self._all_types,))
        if type_labels:
            type_labels[0] = self._all_types
        self._type_filter_labels = tuple(type_labels)
        self._replace_records(incoming, selected_id)
        self._patch_clone_results(clone_status, complete=True)
        if persist:
            self._persist_active_view()
        return self.snapshot

    def clear_active_view(self) -> IssueSnapshot:
        self._store.replace_all(())
        self._source_context = RedmineContext(account=self._account)
        self._persist_active_view()
        return self.snapshot

    def clear_watched_view(self) -> IssueSnapshot:
        self._reset_projection()
        self._persist_active_view()
        return self.snapshot

    def select_issue(self, issue_id: str) -> IssueSource:
        source = self._source(issue_id)
        issue = source.issue
        if issue is None and source.project is not None and source.item is not None:
            issue = self._store.upsert(
                unified_issue(source.project, source.item, detail=source.detail)
            )
            source = replace(source, issue=issue)
        if issue is None:
            return IssueSource()
        self._store.select(issue.id)
        return replace(source, needs_detail=issue.detail_state != "loaded")

    def source_for_issue(self, issue_id: str) -> IssueSource:
        source = self._source(issue_id)
        return replace(
            source,
            needs_detail=bool(
                source.issue and source.issue.detail_state != "loaded"
            ),
        )

    def apply_selected_detail(
        self, issue_id: str, detail: RedmineIssueDetail
    ) -> bool:
        issue_id = str(issue_id or "")
        current = self._store.get(issue_id)
        if issue_id != self._store.selected_id or current is None:
            return False
        self._source_context = replace_detail(self._source_context, detail)
        project, item = self._source_context.item_for_issue(issue_id)
        if item is None:
            project, item = _source_item(current)
        if project is None or item is None:
            return False
        hydrated = unified_issue(
            project, item, analysis=current.analysis, detail=detail
        )
        self._store.patch(
            issue_id,
            **{
                key: value
                for key, value in hydrated.to_dict().items()
                if key not in {"id", "clone"}
            },
        )
        self._persist_active_view()
        return True

    def record_clone_results(
        self, clone_status: dict[str, Any] | None
    ) -> IssueSnapshot:
        if clone_status is not None:
            self._patch_clone_results(clone_status, complete=False)
            self._persist_active_view()
        return self.snapshot

    def apply_project_options(
        self, options: Iterable[dict[str, Any]]
    ) -> IssueSnapshot:
        project_ids = _project_ids(options)
        self._source_context = _context_with_project_ids(
            self._source_context, project_ids
        )
        if not self._store.issue_list and self._source_context.projects:
            detail = self._source_context.issues[0] if self._source_context.issues else None
            return self._replace_result(
                self._source_context,
                filters=self._filters,
                selected_detail=detail,
                persist=False,
            )
        for issue in self._store.issue_list:
            identifier = str(issue.project.get("identifier") or "")
            project_id = project_ids.get(identifier)
            if project_id and project_id != issue.project.get("id"):
                self._store.patch(
                    issue.id, project={**issue.project, "id": project_id}
                )
        return self.snapshot

    def context_project_options(self) -> list[dict[str, str]]:
        return [
            {
                "id": project.identifier,
                "label": project.name,
                "projectId": project.project_id,
            }
            for project in self._source_context.projects
        ]

    def assigned_context(
        self,
        rows: Iterable[dict[str, Any]],
        project_options: Iterable[dict[str, Any]],
    ) -> RedmineContext:
        project_ids = _project_ids(project_options)
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            identifier = str(row.get("project_identifier") or "my-page")
            grouped.setdefault(
                identifier,
                {
                    "name": row.get("project_name") or "",
                    "url": row.get("project_url") or "",
                    "issues": [],
                },
            )["issues"].append(row["issue"])
        return RedmineContext(
            account=self._account,
            projects=tuple(
                RedmineProject(
                    name=str(data["name"] or identifier),
                    identifier=identifier,
                    url=str(data["url"] or ""),
                    project_id=project_ids.get(identifier, ""),
                    issues=tuple(data["issues"]),
                )
                for identifier, data in grouped.items()
            ),
        )

    def reconcile_project_ids(
        self,
        context: RedmineContext,
        options: Iterable[dict[str, Any]],
    ) -> RedmineContext:
        return _context_with_project_ids(context, _project_ids(options))

    def _reset_projection(self) -> None:
        self._store.replace_all(())
        self._source_context = RedmineContext(account=self._account)
        self._filters = _normalize_filters({})
        self._project_filter_labels = (self._all_projects,)
        self._status_filter_labels = (self._all_statuses, "Open", "Closed")
        self._type_filter_labels = (self._all_types,)

    def _source(self, issue_id: str) -> IssueSource:
        issue_id = str(issue_id or "").strip()
        issue = self._store.get(issue_id)
        project, item = self._source_context.item_for_issue(issue_id)
        detail = next(
            (entry for entry in self._source_context.issues if entry.id == issue_id),
            None,
        )
        if item is None and issue is not None:
            project, item = _source_item(issue)
        return IssueSource(
            project=project, item=item, detail=detail, issue=issue
        )

    def _replace_records(
        self, records: Iterable[UnifiedIssue], selected_id: Any = ""
    ) -> None:
        self._store.replace_all(records or ())
        selected_id = str(selected_id or "")
        if selected_id and self._store.get(selected_id) is not None:
            self._store.select(selected_id)
        elif self._store.issue_list:
            self._store.select(self._store.issue_list[0].id)

    def _patch_clone_results(
        self, clone_status: dict[str, Any] | None, *, complete: bool
    ) -> None:
        if clone_status is None:
            return
        for issue in self._store.issue_list:
            existing = clone_status.get(issue.id)
            if existing:
                clone = {
                    "state": "cloned",
                    "issue_key": str(getattr(existing, "key", "") or ""),
                    "issue_url": str(getattr(existing, "web_url", "") or ""),
                    "checked": True,
                }
            elif complete:
                clone = {
                    "state": "not_cloned",
                    "issue_key": "",
                    "issue_url": "",
                    "checked": True,
                }
            else:
                continue
            self._store.patch(issue.id, clone=clone)

    def _persist_active_view(self) -> None:
        if self._active_view_id in _QUICK_VIEW_IDS:
            context_store.save_quick_view(
                self._account,
                self._active_view_id,
                self._store,
                filters=self._filters,
            )
        else:
            context_store.save_view(
                self._account, self._store, filters=self._filters
            )


def _normalize_filters(filters: Any) -> dict[str, str]:
    source = filters if isinstance(filters, dict) else {}
    return {key: str(source.get(key, "") or "") for key in _FILTER_KEYS}


def _project_ids(
    options: Iterable[dict[str, Any]],
) -> dict[str, str]:
    return {
        str(option.get("id") or ""): str(option.get("projectId") or "")
        for option in options
        if isinstance(option, dict)
        and option.get("id")
        and option.get("projectId")
    }


def _context_with_project_ids(
    context: RedmineContext, project_ids: dict[str, str]
) -> RedmineContext:
    return replace(
        context,
        projects=tuple(
            replace(
                project,
                project_id=project_ids.get(
                    project.identifier, project.project_id
                ),
            )
            for project in context.projects
        ),
    )


def _source_item(
    issue: UnifiedIssue,
) -> tuple[RedmineProject, RedmineIssueListItem]:
    project = RedmineProject(
        name=str(issue.project.get("name") or ""),
        identifier=str(issue.project.get("identifier") or ""),
        url=str(issue.project.get("url") or ""),
        project_id=str(issue.project.get("id") or ""),
    )
    item = RedmineIssueListItem(
        id=issue.id,
        url=issue.web_url or issue.source_url,
        tracker=str(issue.issue_type.get("name") or ""),
        status=str(issue.status.get("name") or ""),
        priority=str(issue.priority.get("name") or ""),
        subject=issue.title,
        assignee=str(
            issue.assignee.get("name")
            or issue.assignee.get("displayName")
            or ""
        ),
        updated_at=issue.updated_at,
    )
    return project, item
