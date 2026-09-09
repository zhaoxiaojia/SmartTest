from __future__ import annotations

from datetime import datetime, time, timedelta
import re
from zoneinfo import ZoneInfo


_SHANGHAI = ZoneInfo("Asia/Shanghai")
_JIRA_SCOPE = "project in (SH, TV, IPTV, OTT,RK) AND issuetype in (Bug, Sub-bug)"


def fixed_weekly_audit_scope(trigger_at: datetime) -> dict:
    """Return the fixed weekly-email scope frozen for one actual trigger."""
    trigger = (trigger_at.replace(tzinfo=_SHANGHAI) if trigger_at.tzinfo is None
               else trigger_at.astimezone(_SHANGHAI))
    days_since_friday = (trigger.weekday() - 4) % 7 or 7
    start = datetime.combine(trigger.date() - timedelta(days=days_since_friday), time.min, _SHANGHAI)
    start_text, end_text = start.isoformat(), trigger.isoformat()
    jira_start, jira_end = start.date().isoformat(), trigger.date().isoformat()
    return {
        "startDate": start_text,
        "endDate": end_text,
        "jira": {
            "filters": {},
            "jql": f'{_JIRA_SCOPE} AND created >= {jira_start} AND created <= {jira_end} order by updated DESC',
        },
        "confluence": {
            "filters": {
                "date of commercial approval": [str(trigger.year - 1), str(trigger.year)],
                "support mode": ["A", "B"],
                "project status": ["NORMAL"],
            },
            "search": "",
            "excludeCurrentStageAtOrAbove": 4,
            "excludeSupportModeBProductLines": ["SDPL"],
        },
    }


def weekly_audit_project_in_scope(project, commercial_years, stage_limit, support_mode_b_exclusions=()) -> bool:
    facts = dict(project.facts.value.values) if project.facts.value is not None else {}
    year = re.search(r"\b(20\d{2})\b", str(facts.get("date of commercial approval", "")))
    stage = re.match(r"^\s*(\d+)", project.stage.name if project.stage else "")
    return (
        (not commercial_years or bool(year and year.group(1) in commercial_years))
        and (stage_limit is None or not stage or int(stage.group(1)) < int(stage_limit))
        and not (
            project.product_space.key in support_mode_b_exclusions
            and project.support_mode is not None
            and project.support_mode.name.strip().casefold() == "b"
        )
    )
