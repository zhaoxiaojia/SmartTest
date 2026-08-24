from __future__ import annotations

TRACKER_TO_JIRA_TYPE = {
    "bug": "Bug",
    "support": "Feature",
}


def redmine_tracker_to_jira_type(tracker: str) -> str:
    return TRACKER_TO_JIRA_TYPE.get(str(tracker or "").strip().lower(), "Bug")
