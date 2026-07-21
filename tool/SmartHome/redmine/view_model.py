from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tool.SmartHome.redmine.mapping import map_issue_to_jira
from tool.SmartHome.redmine.models import RedmineContext, RedmineIssueDetail, RedmineIssueListItem, RedmineProject
from tool.SmartHome.redmine.overdue import OverduePolicy


def empty_view(all_projects: str, all_statuses: str) -> dict[str, Any]:
    return view(RedmineContext(), all_projects=all_projects, all_statuses=all_statuses)


def view(
    context: RedmineContext,
    *,
    all_projects: str,
    all_statuses: str,
    filters: dict[str, str] | None = None,
    selected_detail: RedmineIssueDetail | None = None,
) -> dict[str, Any]:
    source_filters = filters or {}
    filters = {
        "project": str(source_filters.get("project", "") or ""),
        "status": str(source_filters.get("status", "") or ""),
        "type": str(source_filters.get("type", "") or ""),
        "text": str(source_filters.get("text", "") or ""),
    }
    projects = [project for project in context.projects if project.project_id]
    analysis = dict(context.raw.get("issue_analysis") or {})
    policy = OverduePolicy()
    rows = [issue_row(project, issue, analysis.get(issue.id)) for project in projects for issue in project.issues if _monitored(issue, analysis.get(issue.id) or {}, policy) and _match(project, issue, filters)]
    selected = detail_row(selected_detail, project=context.project_for_detail(selected_detail)) if selected_detail else (rows[0] if rows else {})
    selected_id = str(selected.get("id") or selected.get("key") or "")
    payload = asdict(context)
    payload["filters"] = filters
    payload["selected_issue_id"] = selected_id
    actionable = sorted(
        [row for row in rows if _row_is_actionable(row)],
        key=lambda row: (_action_rank(row), -float(row.get("updateElapsedHours") or row.get("staleElapsedHours") or 0)),
    )
    return {
        "context": context,
        "context_payload": payload,
        "filters": filters,
        "projectFilterLabels": [all_projects] + [_project_label(project) for project in projects],
        "statusFilterLabels": [all_statuses, "Open", "Closed"],
        "typeFilterLabels": ["All types"] + sorted({issue.tracker for project in projects for issue in project.issues if issue.tracker}),
        "issueRows": rows,
        "selectedIssue": selected,
        "selectedIssueId": selected_id,
        "actionableIssues": actionable,
    }


def replace_detail(context: RedmineContext, detail: RedmineIssueDetail) -> RedmineContext:
    return context.with_detail(detail, jira_issue=map_issue_to_jira(detail, project=context.project_for_detail(detail)))


def issue_row(project: RedmineProject, issue: RedmineIssueListItem, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    risk = dict(analysis or {})
    return {"id": issue.id, "key": issue.id, "title": issue.subject, "webUrl": issue.url, "projectIdentifier": project.identifier, "projectName": project.name, "projectId": project.project_id, "status": issue.status, "type": issue.tracker or "Bug", "assignee": issue.assignee, "priority": issue.priority, "updatedAt": issue.updated_at, "updateRisk": risk.get("risk", "unknown"), "updateAgeText": risk.get("age_text", ""), "updateElapsedHours": risk.get("elapsed_hours"), "updateThresholdHours": risk.get("threshold_hours"), "updateParty": risk.get("party", ""), "updateReason": risk.get("reason", ""), "responsibilityType": risk.get("responsibility_type", ""), "staleType": risk.get("stale_type", ""), "staleElapsedHours": risk.get("stale_elapsed_hours")}


def _row_is_actionable(row: dict[str, Any]) -> bool:
    return row.get("updateRisk") in {"red", "yellow"} or row.get("responsibilityType") == "unassigned" or bool(row.get("staleType"))


def _action_rank(row: dict[str, Any]) -> int:
    if row.get("updateRisk") == "red": return 0
    if row.get("responsibilityType") == "unassigned": return 1
    if row.get("staleType"): return 2
    return 3


def detail_row(issue: RedmineIssueDetail | None = None, *, item: RedmineIssueListItem | None = None, project: RedmineProject | None = None) -> dict[str, Any]:
    if issue is None and item is None:
        return {}
    if issue is None:
        issue_id, title, web_url, description = item.id, item.subject, item.url, ""
        status, priority, assignee, tracker, updated_at, component = item.status, item.priority, item.assignee, item.tracker or "Bug", item.updated_at, item.category
        reporter = created = ""
        comments = attachments = []
        jira = {}
    else:
        jira = map_issue_to_jira(issue, project=project)
        fields = jira.get("fields", {})
        issue_id, title, web_url, description = issue.id, issue.subject, issue.url, issue.description
        status = fields.get("status", {}).get("name", "")
        priority = fields.get("priority", {}).get("name", "")
        assignee = fields.get("assignee", {}).get("displayName", "")
        tracker = fields.get("issuetype", {}).get("name", issue.tracker or "Bug")
        updated_at = issue.list_item.updated_at if issue.list_item else ""
        component = issue.attributes.get("Category", "")
        reporter = issue.attributes.get("Author") or issue.attributes.get("Reporter") or ""
        created = issue.attributes.get("Created") or issue.attributes.get("Created on") or ""
        comments = [{"id": c.id, "author": c.author, "time": c.created_at or c.header, "body": c.note or "\n".join(c.details)} for c in issue.comments if c.note or c.details]
        attachments = [{"id": a.id, "filename": a.filename, "name": a.filename, "size": a.size, "author": a.author, "createdAt": a.created_at, "detailUrl": a.detail_url, "downloadUrl": a.download_url, "url": a.download_url or a.detail_url} for a in issue.attachments]
    project_name = project.name if project else ""
    attrs = issue.attributes if issue else {}
    return {
        "id": issue_id,
        "key": issue_id,
        "title": title,
        "webUrl": web_url,
        "projectName": project_name,
        "projectUrl": project.url if project else "",
        "projectPath": [{"label": project_name, "url": project.url}] if project else [],
        "description": description,
        "detailsFields": [
            _field("Type", tracker),
            _field("Status", status, kind="status"),
            _field("Priority", priority),
            _field("Resolution", _attr(attrs, "Resolution")),
            _field("Affects Version/s", _attr(attrs, "Affects Version/s", "Affected Version", "Affected version")),
            _field("Fix Version/s", _attr(attrs, "Fix Version/s", "Target version", "Fixed Version")),
            _field("Component/s", component),
            _field("Labels", _labels(attrs), kind="tags"),
            _field("Channel of Reporter", _attr(attrs, "Channel of Reporter")),
            _field("Severity", _attr(attrs, "Severity")),
            _field("Product", _attr(attrs, "Product")),
            _field("Project ID", project.project_id if project else ""),
            _field("Software Release", _attr(attrs, "Software Release")),
            _field("Compare Status", _attr(attrs, "Compare Status")),
            _field("Attachment links", _attachment_links(attachments), kind="multiline"),
        ],
        "peopleFields": [
            _field("Assignee", assignee, kind="person"),
            _field("Reporter", reporter, kind="person"),
            _field("Manager", _attr(attrs, "Manager"), kind="person"),
            _field("QA Assignee", _attr(attrs, "QA Assignee"), kind="person"),
            _field("FAE Coworker", _attr(attrs, "FAE Coworker"), kind="person"),
            _field("FAE Manager", _attr(attrs, "FAE Manager"), kind="person"),
            _field("Watchers", _attr(attrs, "Watchers")),
            _field("Votes", _attr(attrs, "Votes")),
        ],
        "dateFields": [_field("Created", created), _field("Updated", updated_at)],
        "extraSections": [
            {"title": "Agile", "fields": [_field("View on Board", _attr(attrs, "Agile", "Agile Board"), kind="link", url=_attr(attrs, "Agile link", "Agile URL"))]},
            {"title": "WBS Gantt-Chart", "fields": [_field("Browse this issue in WBS Gantt-Chart", _attr(attrs, "WBS Gantt-Chart"), kind="link", url=_attr(attrs, "WBS Gantt-Chart link", "WBS Gantt-Chart URL"))]},
        ],
        "comments": comments,
        "attachments": attachments,
        "jira": jira,
    }


def _match(project: RedmineProject, issue: RedmineIssueListItem, filters: dict[str, str]) -> bool:
    wanted_project = filters.get("project", "")
    wanted_status = filters.get("status", "")
    wanted_type = filters.get("type", "")
    text = filters.get("text", "").lower()
    return (
        (not wanted_project or wanted_project in {_project_label(project), project.name, project.identifier, project.project_id})
        and (not wanted_status or _status_matches(issue.status, wanted_status))
        and (not wanted_type or issue.tracker == wanted_type)
        and (not text or text in " ".join([issue.id, issue.subject, issue.status, issue.priority, issue.assignee, issue.category, project.name, project.project_id]).lower())
    )


def _monitored(issue: RedmineIssueListItem, analysis: dict[str, Any], policy: OverduePolicy) -> bool:
    tracker = str(issue.tracker or "").strip().casefold()
    status = str(issue.status or "").strip().casefold()
    subject = "".join(str(issue.subject or "").casefold().split())
    if tracker and tracker not in policy.trackers:
        return False
    if status in policy.excluded_statuses:
        return False
    if any("".join(value.casefold().split()) in subject for value in policy.title_exclusions):
        return False
    if analysis.get("reason") in {"filtered", "due_date_not_reached"}:
        return False
    if analysis and analysis.get("risk") == "unknown" and not analysis.get("responsibility_type") and not analysis.get("stale_type"):
        return False
    return True


def _project_label(project: RedmineProject) -> str:
    return f"{project.name} [{project.project_id}]" if project.project_id else project.name


def _status_matches(status: str, wanted: str) -> bool:
    normalized = str(status or "").strip().lower()
    wanted_normalized = str(wanted or "").strip().lower()
    if wanted_normalized == "open":
        return normalized not in {"closed"}
    if wanted_normalized == "closed":
        return normalized == "closed"
    return status == wanted


def _attr(attrs: dict[str, Any], *names: str) -> str:
    for name in names:
        value = attrs.get(name)
        if value:
            return str(value)
    return ""


def _labels(attrs: dict[str, Any]) -> list[str]:
    value = _attr(attrs, "Labels", "Label")
    if not value:
        return []
    return [part.strip() for part in value.replace(",", " ").split() if part.strip()]


def _attachment_links(attachments: list[dict[str, Any]]) -> str:
    return "\n".join(str(item.get("url") or "") for item in attachments if item.get("url"))


def _field(label: str, value: Any, *, kind: str = "", url: str = "") -> dict[str, Any]:
    payload = {"label": label, "value": value or "", "url": url}
    if kind:
        payload["kind"] = kind
    if kind == "tags":
        payload["values"] = value or []
    return payload
