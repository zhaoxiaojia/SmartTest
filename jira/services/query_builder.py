from __future__ import annotations

PROJECT_MAP = {
    "all_supported_projects": ("RK", "TV", "OTT", "IPTV", "GH", "SH"),
    "rk": ("RK",),
    "tv": ("TV",),
    "ott": ("OTT",),
    "iptv": ("IPTV",),
    "gh": ("GH",),
    "sh": ("SH",),
}

BOARD_CLAUSE_MAP = {
    "open_work": "statusCategory != Done",
    "ready_for_test": 'status in ("Ready for Test", Verified, Resolved)',
    "closed_bugs": "status in (Resolved, Closed, Verified)",
}

TIMEFRAME_CLAUSE_MAP = {
    "last_7_days": "updated >= -7d",
    "last_30_days": "updated >= -30d",
    "last_90_days": "updated >= -90d",
    "this_year": "created >= startOfYear()",
}

STATUS_NAME_MAP = {
    "open": "Open",
    "in_progress": "In Progress",
    "blocked": "Blocked",
    "ready_for_test": "Ready for Test",
    "verified": "Verified",
    "resolved": "Resolved",
    "closed": "Closed",
}

PRIORITY_NAME_MAP = {
    "highest": "Highest",
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

ISSUE_TYPE_NAME_MAP = {
    "bug": "Bug",
    "task": "Task",
    "story": "Story",
    "improvement": "Improvement",
}


def parse_csv_ids(raw_value: str) -> list[str]:
    values = []
    for item in str(raw_value or "").split(","):
        clean = item.strip()
        if clean and clean not in values:
            values.append(clean)
    return values


def parse_csv_terms(raw_value: str) -> list[str]:
    values = []
    normalized = str(raw_value or "").replace(";", ",")
    for item in normalized.split(","):
        clean = item.strip()
        if clean and clean not in values:
            values.append(clean)
    return values


def quote_jql_value(value: str) -> str:
    escaped = str(value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_base_jql(
    *,
    raw_jql_text: str,
    project_ids_csv: str,
    board_id: str,
    timeframe_id: str,
    status_ids_csv: str,
    priority_ids_csv: str,
    issue_type_ids_csv: str,
    keyword_text: str,
    assignee_text: str,
    reporter_text: str,
    labels_text: str,
    only_mine: bool,
) -> str:
    if raw_jql_text.strip():
        return raw_jql_text.strip()

    clauses: list[str] = []

    selected_projects: list[str] = []
    for project_id in parse_csv_ids(project_ids_csv):
        selected_projects.extend(PROJECT_MAP.get(project_id, ()))
    if not selected_projects or "all_supported_projects" in parse_csv_ids(project_ids_csv):
        selected_projects = list(PROJECT_MAP["all_supported_projects"])
    clauses.append(f'project in ({", ".join(selected_projects)})')

    selected_issue_types = [
        ISSUE_TYPE_NAME_MAP[issue_type_id]
        for issue_type_id in parse_csv_ids(issue_type_ids_csv)
        if issue_type_id in ISSUE_TYPE_NAME_MAP
    ]
    if selected_issue_types:
        clauses.append(
            "issuetype in ("
            + ", ".join(quote_jql_value(issue_type) for issue_type in selected_issue_types)
            + ")"
        )

    selected_statuses = [
        STATUS_NAME_MAP[status_id]
        for status_id in parse_csv_ids(status_ids_csv)
        if status_id in STATUS_NAME_MAP
    ]
    if selected_statuses:
        clauses.append(
            "status in (" + ", ".join(quote_jql_value(status) for status in selected_statuses) + ")"
        )
    else:
        clauses.append(BOARD_CLAUSE_MAP.get(board_id, BOARD_CLAUSE_MAP["open_work"]))

    clauses.append(TIMEFRAME_CLAUSE_MAP.get(timeframe_id, TIMEFRAME_CLAUSE_MAP["last_30_days"]))

    if only_mine:
        clauses.append("assignee = currentUser()")
    else:
        assignees = parse_csv_terms(assignee_text)
        if assignees:
            clauses.append(
                "assignee in (" + ", ".join(quote_jql_value(assignee) for assignee in assignees) + ")"
            )

    reporters = parse_csv_terms(reporter_text)
    if reporters:
        clauses.append(
            "reporter in (" + ", ".join(quote_jql_value(reporter) for reporter in reporters) + ")"
        )

    selected_priorities = [
        PRIORITY_NAME_MAP[priority_id]
        for priority_id in parse_csv_ids(priority_ids_csv)
        if priority_id in PRIORITY_NAME_MAP
    ]
    if selected_priorities:
        clauses.append(
            "priority in (" + ", ".join(quote_jql_value(priority) for priority in selected_priorities) + ")"
        )

    labels = parse_csv_terms(labels_text)
    if labels:
        clauses.append("labels in (" + ", ".join(quote_jql_value(label) for label in labels) + ")")

    if keyword_text.strip():
        escaped = keyword_text.strip().replace("\\", "\\\\").replace('"', '\\"')
        clauses.append(f'text ~ "{escaped}"')

    return " AND ".join(clauses) + " ORDER BY updated DESC"
