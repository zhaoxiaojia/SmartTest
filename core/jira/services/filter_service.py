from __future__ import annotations

from typing import Any
import re


_ORDER_BY = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|(?P<order>\border\s+by\b)''', re.IGNORECASE)

JIRA_PERIOD_CONDITIONS = {
    "week": 'created >= "-7d" AND created <= now()',
    "month": 'created >= "-30d" AND created <= now()',
    "quarter": 'created >= startOfDay("-3M") AND created <= now()',
}


def compose_jql(user_jql: str, fixed_conditions: str) -> str:
    """Intersect predicates before ordering; Jira's validator owns JQL validity."""
    draft, fixed = str(user_jql or "").strip(), str(fixed_conditions or "").strip()
    if not fixed:
        return draft
    order = next((match for match in _ORDER_BY.finditer(draft) if match.group("order")), None)
    predicate = draft[:order.start()].rstrip() if order else draft
    suffix = " " + draft[order.start():] if order else ""
    return (f"({predicate}) AND ({fixed})" if predicate else fixed) + suffix


def _quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _multi(field, values):
    clean = [value for value in values or () if str(value).strip()]
    return f"{field} IN ({', '.join(_quote(value) for value in clean)})" if clean else ""


def build_basic_jql(conditions, fields):
    clauses = []
    for key, field in (("project", "project"), ("issueType", "issuetype"), ("status", "status"), ("assignee", "assignee")):
        clause = _multi(field, conditions.get(key))
        if clause: clauses.append(clause)
    if str(conditions.get("containsText") or "").strip():
        clauses.append(f"text ~ {_quote(str(conditions['containsText']).strip())}")
    resolutions = conditions.get("resolution") or ()
    if resolutions:
        clauses.append(_multi("resolution", resolutions))
    for field_id, value in (conditions.get("more") or {}).items():
        metadata = fields.get(field_id) or {}
        if not metadata.get("queryable"):
            raise ValueError(f"advanced_only:{field_id}")
        control = metadata.get("control")
        if value in (None, "", [], {}): continue
        if control in {"multi", "user"}:
            clauses.append(_multi(field_id, value if isinstance(value, list) else [value]))
        elif control == "number":
            clauses.append(f"{field_id} = {float(value):g}")
        elif control == "date" and isinstance(value, dict):
            if value.get("from"): clauses.append(f"{field_id} >= {_quote(value['from'])}")
            if value.get("to"): clauses.append(f"{field_id} <= {_quote(value['to'])}")
        elif control == "text": clauses.append(f"{field_id} ~ {_quote(value)}")
        else: clauses.append(f"{field_id} = {_quote(value)}")
    return " AND ".join(filter(None, clauses))



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
