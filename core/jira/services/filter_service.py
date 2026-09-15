from __future__ import annotations

from typing import Any


class JiraFilterService:
    """Normalize Jira's read-only filter metadata without inventing candidates."""

    _CONTROLS = {
        "com.atlassian.jira.issue.status.Status": "multi",
        "com.atlassian.jira.issue.issuetype.IssueType": "multi",
        "com.atlassian.jira.project.Project": "multi",
        "com.atlassian.jira.user.ApplicationUser": "user",
        "java.util.Date": "date",
        "java.lang.String": "text",
        "java.lang.Number": "number",
    }

    def __init__(self, gateway) -> None:
        self.gateway = gateway

    def fields(self) -> list[dict[str, Any]]:
        payload = self.gateway.fetch_query_fields()
        result = []
        for item in payload.get("visibleFieldNames") or ():
            if not isinstance(item, dict) or not item.get("value"):
                continue
            types = [str(value) for value in item.get("types") or ()]
            control = next((self._CONTROLS[value] for value in types if value in self._CONTROLS), "advanced")
            result.append({
                "id": str(item["value"]),
                "name": str(item.get("displayName") or item["value"]),
                "schema": {"types": types, "operators": list(item.get("operators") or ())},
                "control": control,
                "queryable": control != "advanced",
            })
        return result

    def saved_filters(self) -> list[dict[str, str]]:
        return [{
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or ""),
            "owner": str((item.get("owner") or {}).get("displayName") or ""),
        } for item in self.gateway.fetch_saved_filters() if item.get("id")]

    def suggestions(self, field_name: str, query: str = "") -> list[dict[str, str]]:
        payload = self.gateway.fetch_query_suggestions(field_name, query)
        return [{
            "value": str(item["value"]),
            "displayName": str(item.get("displayName") or item["value"]),
        } for item in payload.get("results") or () if isinstance(item, dict) and item.get("value") is not None]

    def saved_filter(self, filter_id: str) -> dict[str, str]:
        item = self.gateway.fetch_filter(filter_id)
        return {key: str(item.get(key) or "") for key in ("id", "name", "jql")}

    def validate(self, jql: str) -> dict[str, Any]:
        return self.gateway.validate_jql(jql)
