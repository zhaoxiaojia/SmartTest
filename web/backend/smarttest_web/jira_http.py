from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime


def json_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {key: json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return str(value)


def issue_payload(issue, detail_names) -> dict:
    payload = {
        "id": issue.identity.id, "key": issue.identity.key,
        "webUrl": issue.identity.web_url, "summary": issue.summary,
        "project": {"id": issue.project.id, "key": issue.project.key, "name": issue.project.name},
        "status": {"id": issue.status.id, "name": issue.status.name},
        "issueType": {"id": issue.issue_type.id, "name": issue.issue_type.name},
        "priority": json_value(issue.priority), "assignee": json_value(issue.assignee),
        "reporter": json_value(issue.reporter), "createdAt": json_value(issue.created_at),
        "updatedAt": json_value(issue.updated_at), "labels": list(issue.labels),
        "sourceRevision": issue.revision.value,
    }
    payload["details"] = {
        name: {"state": getattr(issue, name).state.value,
               "value": json_value(getattr(issue, name).value),
               "sourceRevision": getattr(issue, name).source_revision,
               "errorCode": getattr(issue, name).error_code}
        for name in detail_names
    }
    return payload
