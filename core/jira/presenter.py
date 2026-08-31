from __future__ import annotations

from typing import Any

from core.domain.detail import DetailState
from core.jira.domain import Issue


def record_to_issue_row(issue: Issue) -> dict[str, Any]:
    comments = issue.comments.value if issue.comments.state is DetailState.LOADED else ()
    links = issue.links.value if issue.links.state is DetailState.LOADED else ()
    attachments = issue.attachments.value if issue.attachments.state is DetailState.LOADED else ()
    description_value = issue.description.value.value if issue.description.state is DetailState.LOADED and issue.description.value else ""
    normalized_comments = [normalize_text(item.body) for item in comments if normalize_text(item.body)]
    description = normalize_text(description_value)
    return {
        "keyId": issue.identity.key,
        "summary": issue.summary,
        "status": issue.status.name,
        "priority": issue.priority.name if issue.priority else "",
        "assignee": issue.assignee.display_name if issue.assignee else "",
        "reporter": issue.reporter.display_name if issue.reporter else "",
        "labels": list(issue.labels),
        "components": [item.name for item in issue.components],
        "project": issue.project.key,
        "updatedAt": issue.updated_at.isoformat() if issue.updated_at else "",
        "detail": (description or issue.summary).strip(),
        "description": description,
        "attachments": [item.__dict__ for item in attachments],
        "comments": normalized_comments,
        "commentCount": len(normalized_comments),
        "linkCount": len(links),
        "issueType": issue.issue_type.name,
        "resolution": issue.resolution.name if issue.resolution else "",
    }


def normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if "content" in value:
            return normalize_text(value.get("content"))
        fragments = [str(value.get(key)) for key in ("text", "value", "name") if value.get(key)]
        return " ".join(fragment.strip() for fragment in fragments).strip() if fragments else normalize_text(list(value.values()))
    if isinstance(value, list):
        return "\n".join(fragment for item in value if (fragment := normalize_text(item))).strip()
    return str(value).strip() if value is not None else ""


def extract_actions(text: str) -> list[str]:
    actions = []
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith(("-", "*", "1.", "2.", "3.")):
            actions.append(clean.lstrip("-*1234567890. ").strip())
    return actions[:5]
