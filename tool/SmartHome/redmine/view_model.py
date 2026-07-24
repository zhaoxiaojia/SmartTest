from __future__ import annotations

from typing import Any

from support.jira_integration.core import UnifiedIssue
from tool.SmartHome.redmine.models import RedmineContext, RedmineIssueDetail, RedmineIssueListItem, RedmineProject
from tool.SmartHome.redmine.overdue import OverduePolicy


def view(
    context: RedmineContext,
    *,
    all_projects: str,
    filters: dict[str, str] | None = None,
    selected_detail: RedmineIssueDetail | None = None,
) -> dict[str, Any]:
    source_filters = filters or {}
    filters = {
        "project": str(source_filters.get("project", "") or ""),
        "status": str(source_filters.get("status", "") or ""),
        "type": str(source_filters.get("type", "") or ""),
        "subject": str(source_filters.get("subject", "") or ""),
        "text": str(source_filters.get("text", "") or ""),
    }
    projects = [project for project in context.projects if project.project_id]
    analysis = dict(context.raw.get("issue_analysis") or {})
    policy = OverduePolicy()
    details = {detail.id: detail for detail in context.issues}
    if selected_detail is not None:
        details[selected_detail.id] = selected_detail
    issue_list = [
        unified_issue(
            project,
            issue,
            analysis=analysis.get(issue.id),
            detail=details.get(issue.id),
        )
        for project in projects
        for issue in project.issues
        if _monitored(issue, analysis.get(issue.id) or {}, policy)
    ]
    selected_id = (
        selected_detail.id
        if selected_detail is not None and any(issue.id == selected_detail.id for issue in issue_list)
        else (issue_list[0].id if issue_list else "")
    )
    return {
        "issue_list": issue_list,
        "filters": filters,
        "projectFilterLabels": [all_projects] + [_project_label(project) for project in projects],
        "selectedIssueId": selected_id,
    }


def unified_issue(
    project: RedmineProject,
    item: RedmineIssueListItem,
    *,
    analysis: dict[str, Any] | None = None,
    detail: RedmineIssueDetail | None = None,
) -> UnifiedIssue:
    risk = dict(analysis or {})
    projected = detail_row(detail, item=item, project=project)
    reporter = _field_value(projected.get("peopleFields"), "Reporter")
    created_at = _field_value(projected.get("dateFields"), "Created")
    return UnifiedIssue(
        id=item.id,
        key=item.id,
        source_system="redmine",
        source_url=item.url,
        title=detail.subject if detail else item.subject,
        web_url=detail.url if detail else item.url,
        project={
            "id": project.project_id,
            "identifier": project.identifier,
            "name": project.name,
            "url": project.url,
        },
        status={"name": _field_value(projected.get("detailsFields"), "Status") or item.status},
        issue_type={"name": _field_value(projected.get("detailsFields"), "Type") or item.tracker or "Bug"},
        priority={"name": _field_value(projected.get("detailsFields"), "Priority") or item.priority},
        assignee={"name": _field_value(projected.get("peopleFields"), "Assignee") or item.assignee},
        reporter={"name": reporter} if reporter else {},
        created_at=created_at,
        updated_at=item.updated_at,
        description=projected.get("description", ""),
        detail_fields=list(projected.get("detailsFields") or []),
        people_fields=list(projected.get("peopleFields") or []),
        date_fields=list(projected.get("dateFields") or []),
        extra_sections=list(projected.get("extraSections") or []),
        comments=list(projected.get("comments") or []),
        attachments=list(projected.get("attachments") or []),
        detail_state="loaded" if detail is not None else "unloaded",
        clone={
            "state": "not_cloned",
            "issue_key": "",
            "issue_url": "",
            "checked": False,
        },
        analysis=risk,
    )


def issue_row_from_unified(issue: UnifiedIssue) -> dict[str, Any]:
    project = issue.project
    analysis = issue.analysis
    clone = issue.clone
    row = {
        "id": issue.id,
        "key": issue.key or issue.id,
        "title": issue.title,
        "webUrl": issue.web_url or issue.source_url,
        "projectIdentifier": str(project.get("identifier") or ""),
        "projectName": str(project.get("name") or ""),
        "projectId": str(project.get("id") or ""),
        "status": str(issue.status.get("name") or ""),
        "type": str(issue.issue_type.get("name") or "Bug"),
        "assignee": str(issue.assignee.get("name") or issue.assignee.get("displayName") or ""),
        "priority": str(issue.priority.get("name") or ""),
        "updatedAt": issue.updated_at,
        "updateRisk": analysis.get("risk", "unknown"),
        "updateAgeText": analysis.get("age_text", ""),
        "updateElapsedHours": analysis.get("elapsed_hours"),
        "updateThresholdHours": analysis.get("threshold_hours"),
        "updateParty": analysis.get("party", ""),
        "updateReason": analysis.get("reason", ""),
        "responsibilityType": analysis.get("responsibility_type", ""),
        "staleType": analysis.get("stale_type", ""),
        "staleElapsedHours": analysis.get("stale_elapsed_hours"),
        "cloneStatus": str(clone.get("state") or "not_cloned"),
    }
    issue_key = str(clone.get("issue_key") or "")
    issue_url = str(clone.get("issue_url") or "")
    if issue_key:
        row["clonedIssueKey"] = issue_key
    if issue_url:
        row["clonedIssueUrl"] = issue_url
    return row


def detail_row_from_unified(issue: UnifiedIssue | None) -> dict[str, Any]:
    if issue is None:
        return {}
    project = issue.project
    reporter = str(issue.reporter.get("name") or issue.reporter.get("displayName") or "")
    return {
        **issue_row_from_unified(issue),
        "projectUrl": str(project.get("url") or ""),
        "projectPath": (
            [{"label": str(project.get("name") or ""), "url": str(project.get("url") or "")}]
            if project.get("name") or project.get("url")
            else []
        ),
        "description": issue.description,
        "detailsFields": list(issue.detail_fields),
        "peopleFields": list(issue.people_fields),
        "dateFields": list(issue.date_fields),
        "extraSections": list(issue.extra_sections),
        "comments": list(issue.comments),
        "attachments": list(issue.attachments),
        "reporter": reporter,
    }


def actionable_rows(issues: list[UnifiedIssue] | tuple[UnifiedIssue, ...]) -> list[dict[str, Any]]:
    rows = [issue_row_from_unified(issue) for issue in issues]
    return sorted(
        [row for row in rows if _row_is_actionable(row)],
        key=lambda row: (
            _action_rank(row),
            -float(row.get("updateElapsedHours") or row.get("staleElapsedHours") or 0),
        ),
    )


def replace_detail(context: RedmineContext, detail: RedmineIssueDetail) -> RedmineContext:
    return context.with_detail(detail)


def _field_value(fields: Any, label: str) -> str:
    return str(
        next(
            (
                field.get("value")
                for field in fields or []
                if isinstance(field, dict) and field.get("label") == label
            ),
            "",
        )
        or ""
    )


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
    else:
        issue_id, title, web_url, description = issue.id, issue.subject, issue.url, issue.description
        status = issue.attr("Status")
        priority = issue.attr("Priority")
        assignee = issue.attr("Assignee")
        tracker = issue.tracker or "Bug"
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
    }


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
