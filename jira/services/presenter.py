from __future__ import annotations

from typing import Any

from jira.core.models import IssueRecord


def record_to_issue_row(record: IssueRecord) -> dict[str, Any]:
    comments = record.fields.get("comments") or []
    links = record.fields.get("issuelinks") or []
    description = normalize_text(record.fields.get("description"))
    if not description:
        description = record.fields.get("summary") or ""
    normalized_comments = [normalize_text(item) for item in comments if normalize_text(item)]
    return {
        "keyId": record.key,
        "summary": str(record.fields.get("summary", "") or ""),
        "status": str(record.fields.get("status", "") or ""),
        "priority": str(record.fields.get("priority", "") or ""),
        "assignee": str(record.fields.get("assignee", "") or ""),
        "reporter": str(record.fields.get("reporter", "") or ""),
        "labels": list(record.fields.get("labels") or []),
        "components": list(record.fields.get("components") or []),
        "project": str(record.fields.get("project", "") or ""),
        "updatedAt": str(record.fields.get("updated", "") or ""),
        "detail": description.strip(),
        "comments": normalized_comments,
        "commentCount": len(normalized_comments),
        "linkCount": len(links) if isinstance(links, list) else 0,
        "issueType": str(record.fields.get("issueType", "") or ""),
        "resolution": str(record.fields.get("resolution", "") or ""),
    }


def normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if "content" in value:
            return normalize_text(value.get("content"))
        fragments: list[str] = []
        for key in ("text", "value", "name"):
            if value.get(key):
                fragments.append(str(value.get(key)))
        if fragments:
            return " ".join(fragment.strip() for fragment in fragments if fragment).strip()
        return normalize_text(list(value.values()))
    if isinstance(value, list):
        fragments = [normalize_text(item) for item in value]
        return "\n".join(fragment for fragment in fragments if fragment).strip()
    return str(value).strip() if value is not None else ""


def extract_actions(text: str) -> list[str]:
    actions: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith(("-", "*", "1.", "2.", "3.")):
            actions.append(clean.lstrip("-*1234567890. ").strip())
    return actions[:5]
