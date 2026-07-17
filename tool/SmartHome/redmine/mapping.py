from __future__ import annotations

from typing import Any

from tool.SmartHome.redmine.models import RedmineIssueDetail, RedmineProject

TRACKER_TO_JIRA_TYPE = {
    "bug": "Bug",
    "support": "Feature",
}


def redmine_tracker_to_jira_type(tracker: str) -> str:
    return TRACKER_TO_JIRA_TYPE.get(str(tracker or "").strip().lower(), "Bug")


def map_issue_to_jira(
    issue: RedmineIssueDetail,
    *,
    project: RedmineProject | None = None,
    project_key: str = "",
) -> dict[str, Any]:
    return issue.to_jira_transition(
        project=project,
        project_key=project_key,
        source_system="redmine",
        issue_type=redmine_tracker_to_jira_type(issue.tracker),
    )
