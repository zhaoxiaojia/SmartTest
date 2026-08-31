from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class OverduePolicy:
    priority_threshold_hours: dict[str, float] = field(default_factory=lambda: {
        "immediate": 24.0, "urgent": 72.0, "high": 120.0, "normal": 168.0,
    })
    customer_threshold_hours: float = 168.0
    trackers: frozenset[str] = frozenset({"bug", "support"})
    excluded_statuses: frozenset[str] = frozenset({"closed", "resolved"})
    title_exclusions: tuple[str, ...] = ("标准模板", "Redmine - Bug标准格式", "Redmine - 需求/Feature 标准格式", "问题\\需求提报的标准格式")
    fallback_to_created: bool = True
    timezone_offset_hours: float = 8
    stale_threshold_hours: float = 720.0


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _name(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).casefold()


def _time(value: Any, tz: timezone) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    else:
        text = _text(value)
        if not text:
            return None
        text = text.replace("Z", "+00:00")
        result = None
        try:
            result = datetime.fromisoformat(text)
        except ValueError:
            candidates = [text, re.sub(r"^(updated|added|created|by)\s+", "", text, flags=re.I)]
            formats = (
                "%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S",
                "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S",
                "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%b %d, %Y %H:%M", "%b %d, %Y %I:%M %p",
                "%B %d, %Y %H:%M", "%B %d, %Y %I:%M %p", "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y",
            )
            for candidate in candidates:
                for fmt in formats:
                    try:
                        result = datetime.strptime(candidate, fmt)
                        break
                    except ValueError:
                        pass
                if result:
                    break
            if result is None:
                patterns = (
                    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?", r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}(?::\d{2})?",
                    r"\d{2}/\d{2}/\d{4} \d{1,2}:\d{2}(?::\d{2})?(?: [AP]M)?",
                )
                for pattern in patterns:
                    match = re.search(pattern, text, flags=re.I)
                    if match:
                        for fmt in formats:
                            try:
                                result = datetime.strptime(match.group(), fmt)
                                break
                            except ValueError:
                                pass
                    if result:
                        break
        if result is None:
            return None
    return result.replace(tzinfo=tz) if result.tzinfo is None else result


def _due_deadline(value: Any, tz: timezone) -> datetime | None:
    raw = _text(value)
    parsed = _time(raw, tz)
    if parsed is None:
        return None
    if not re.search(r"\d{1,2}:\d{2}", raw) and re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}/\d{1,2}/\d{4}", raw):
        return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed


def _assignment(detail: str) -> tuple[str, str] | None:
    for pattern in (
        r"Assigned to changed from (?P<from>.+?) to (?P<to>.+)$",
        r"Assignee changed from (?P<from>.+?) to (?P<to>.+)$",
        r"指派给\s*从\s*(?P<from>.+?)\s*变更为\s*(?P<to>.+)$",
        r"指派给\s*从\s*(?P<from>.+?)\s*改为\s*(?P<to>.+)$",
    ):
        match = re.search(pattern, _text(detail), re.I)
        if match:
            return _text(match.group("from")), _text(match.group("to"))
    return None


def _journal_time(journal: dict[str, Any], tz: timezone) -> datetime | None:
    return _time(journal.get("timestamp") or journal.get("created_at") or journal.get("anchor_title") or journal.get("header"), tz)


def _age_text(hours: float) -> str:
    if hours < 24:
        return f"{max(0, int(hours))}h"
    days = hours / 24
    return f"{int(days)}d" if days.is_integer() else f"{days:.1f}d"


def analyze_issue(*, issue: dict[str, Any], journals: Iterable[dict[str, Any]], aml_names: Iterable[str], now: datetime | None = None, policy: OverduePolicy | None = None) -> dict[str, Any]:
    policy = policy or OverduePolicy()
    redmine_tz = timezone(timedelta(hours=policy.timezone_offset_hours))
    current_time = now or datetime.now(redmine_tz)
    current_time = current_time.replace(tzinfo=redmine_tz) if current_time.tzinfo is None else current_time
    prepared = [(j, _journal_time(j, redmine_tz)) for j in journals]
    last_visible_journal = max((pair for pair in prepared if pair[1]), key=lambda pair: pair[1], default=None)
    evidence = {
        "issue_id": _text(issue.get("id")), "assignee": _text(issue.get("assignee")), "party": "",
        "threshold_hours": None, "assignment_source": "", "assignment_start": "", "base_time": "",
        "last_matching_update_author": "", "last_matching_update_time": "",
        "last_visible_journal_author": _text(last_visible_journal[0].get("author")) if last_visible_journal else "",
        "last_visible_journal_time": last_visible_journal[1].isoformat() if last_visible_journal else "",
        "last_visible_journal_content": _text((last_visible_journal[0].get("note") or " ".join(last_visible_journal[0].get("details", ())))) if last_visible_journal else "",
        "ignored_opposite_update_author": "", "ignored_opposite_update_time": "",
        "elapsed_hours": None, "overdue_hours": None, "risk": "unknown", "reason": "", "age_text": "",
        "responsibility_type": "", "stale_type": "", "stale_elapsed_hours": None, "stale_threshold_hours": policy.stale_threshold_hours,
    }

    def neutral(reason: str, *, responsibility_type: str = "") -> dict[str, Any]:
        return {**evidence, "reason": reason, "responsibility_type": responsibility_type}

    tracker, status, subject = _name(issue.get("tracker")), _name(issue.get("status")), _name(issue.get("subject"))
    if tracker not in policy.trackers or status in policy.excluded_statuses:
        return neutral("filtered")
    if any(_name(word) in subject for word in policy.title_exclusions if _name(word)):
        return neutral("filtered")
    due_date = _due_deadline(issue.get("due_date"), redmine_tz)
    if due_date and current_time <= due_date:
        return neutral("due_date_not_reached")
    assignee = _text(issue.get("assignee"))
    aml = {_name(name) for name in aml_names if _name(name)}
    is_unassigned = not assignee or assignee.casefold() in {"-", "--", "none", "n/a", "na", "null", "unassigned"}
    party = "amlogic" if not is_unassigned and _name(assignee) in aml else "customer"
    evidence["party"] = party
    start_date = _time(issue.get("start_date"), redmine_tz)
    if start_date:
        stale_elapsed = max(0.0, (current_time - start_date).total_seconds() / 3600)
        evidence["stale_elapsed_hours"] = stale_elapsed
        if stale_elapsed > policy.stale_threshold_hours:
            evidence["stale_type"] = "stale_amlogic" if party == "amlogic" else "stale_customer"
    if is_unassigned:
        latest_aml_assignment = None
        saw_assignment = False
        for journal, timestamp in prepared:
            if not timestamp:
                continue
            for detail in journal.get("details", ()):
                change = _assignment(detail)
                if not change:
                    continue
                saw_assignment = True
                if _name(change[1]) in aml and (latest_aml_assignment is None or timestamp > latest_aml_assignment):
                    latest_aml_assignment = timestamp
        assignment_source = "assignment"
        if latest_aml_assignment is None and policy.fallback_to_created and not saw_assignment:
            latest_aml_assignment = _time(issue.get("created_at"), redmine_tz)
            assignment_source = "created_fallback"
        if latest_aml_assignment:
            evidence.update({"assignment_source": assignment_source, "assignment_start": latest_aml_assignment.isoformat(), "base_time": latest_aml_assignment.isoformat()})
        evidence["party"] = ""
        return neutral("unassigned", responsibility_type="unassigned")
    threshold = policy.priority_threshold_hours.get(_name(issue.get("priority"))) if party == "amlogic" else policy.customer_threshold_hours
    evidence["threshold_hours"] = float(threshold) if threshold is not None else None
    if threshold is None:
        return {**evidence, "reason": "priority_without_threshold"}
    current = _name(assignee)
    latest_current = latest_any = None
    saw_assignment = False
    for journal, timestamp in prepared:
        if not timestamp:
            continue
        for detail in journal.get("details", ()):
            change = _assignment(detail)
            if not change:
                continue
            saw_assignment = True
            target = _name(change[1])
            matches_party = target in aml if party == "amlogic" else bool(target and target not in aml)
            if matches_party and (latest_any is None or timestamp > latest_any):
                latest_any = timestamp
            if party == "customer" and target == current and (latest_current is None or timestamp > latest_current):
                latest_current = timestamp
    start = latest_any if party == "amlogic" else (latest_current or latest_any)
    assignment_source = "assignment"
    if start is None and policy.fallback_to_created and (party == "customer" or not saw_assignment):
        start = _time(issue.get("created_at"), redmine_tz)
        assignment_source = "created_fallback"
    if start is None:
        return {**evidence, "reason": "missing_start_time"}
    evidence.update({"assignment_source": assignment_source, "assignment_start": start.isoformat()})
    last_actor = None
    last_actor_author = ""
    latest_opposite = None
    latest_opposite_author = ""
    for journal, timestamp in prepared:
        author = _name(journal.get("author"))
        matches_actor = author in aml if party == "amlogic" else bool(author and author not in aml)
        if matches_actor and timestamp and timestamp > start and (last_actor is None or timestamp > last_actor):
            last_actor = timestamp
            last_actor_author = _text(journal.get("author"))
        if author and not matches_actor and timestamp and timestamp > start and (latest_opposite is None or timestamp > latest_opposite):
            latest_opposite = timestamp
            latest_opposite_author = _text(journal.get("author"))
    base = max(start, last_actor) if last_actor else start
    elapsed = max(0.0, (current_time - base).total_seconds() / 3600)
    risk = "red" if elapsed > threshold else "yellow" if elapsed >= threshold / 3 else "green"
    responsibility_type = f"{party}_overdue" if risk == "red" else f"{party}_watch"
    return {**evidence, "risk": risk, "reason": "calculated", "elapsed_hours": elapsed, "overdue_hours": elapsed - float(threshold), "age_text": _age_text(elapsed), "base_time": base.isoformat(), "responsibility_type": responsibility_type, "last_matching_update_author": last_actor_author, "last_matching_update_time": last_actor.isoformat() if last_actor else "", "ignored_opposite_update_author": latest_opposite_author, "ignored_opposite_update_time": latest_opposite.isoformat() if latest_opposite else ""}


def load_redmine_people(path) -> tuple[set[str], dict[str, str]]:
    """Load optional Redmine identities; absent/empty fields are intentionally harmless."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return set(), {}
    configured = payload.get("redmine") or {}
    analysis = configured.get("analysis") or {}
    unclassified_department = _name(analysis.get("unclassified_aml_department")) or "amlogic"
    aml_accounts = ((configured.get("accounts") or {}).get("amlogic") or [])
    aml_names = set()
    departments = {}
    for account in aml_accounts:
        if not isinstance(account, dict):
            continue
        name = _text(account.get("display_name") or account.get("account"))
        department = _name(account.get("department"))
        if name:
            aml_names.add(name)
        if name and department:
            departments[name.casefold()] = department
    for name in aml_names:
        departments.setdefault(name.casefold(), unclassified_department)
    return aml_names, departments
