from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

from core.product_lines import (
    CHINA_OPERATOR_BUSINESS,
    DASHBOARD_PRODUCT_LINES,
    GLOBAL_OPERATOR_STB_BUSINESS,
    PRODUCT_LINE_BY_JIRA_PROJECT,
    SMART_DEVICE_BUSINESS,
    TV_BUSINESS,
    WIRELESS_CONNECTION,
)
from core.jira.services.filter_service import compose_jql, jira_period_condition


def _name(value: Any) -> str:
    return str(value.get("name") or "") if isinstance(value, dict) else ""


TEAM_BUG_LINES = DASHBOARD_PRODUCT_LINES
SELF_TEST_JIRA_CONDITIONS = '"Channel of Reporter" = "Self-Test"'
FAE_QA_GROUP_PRODUCT_LINES = (
    ("fae-wifi-qa", WIRELESS_CONNECTION),
    ("fae-SH-qa", SMART_DEVICE_BUSINESS),
    ("fae-stb-qa", GLOBAL_OPERATOR_STB_BUSINESS),
    ("fae-tv-qa", TV_BUSINESS),
    ("fae-iptv-qa", CHINA_OPERATOR_BUSINESS),
)
FAE_QA_GROUPS = tuple(group for group, _line in FAE_QA_GROUP_PRODUCT_LINES)


@dataclass(frozen=True)
class QARoster:
    fingerprint: str
    assignments: tuple[tuple[str, tuple[str, ...]], ...] = ()


def load_fae_qa_roster(gateway, accounts) -> QARoster:
    by_account: dict[str, set[str]] = defaultdict(set)
    product_line_by_group = dict(FAE_QA_GROUP_PRODUCT_LINES)
    for account in sorted({str(value or "").strip().casefold() for value in accounts if str(value or "").strip()}):
        by_account[account].update(
            product_line_by_group[group].name
            for group in gateway.user_groups(account) if group in product_line_by_group
        )
    assignments = tuple((account, tuple(sorted(lines))) for account, lines in sorted(by_account.items()))
    accounts = tuple(account for account, _lines in assignments)
    encoded = json.dumps(
        {"accounts": accounts, "assignments": assignments,
         "lines": [(line.name, line.jira_project_keys) for line in TEAM_BUG_LINES],
         "groups": FAE_QA_GROUPS, "jql": compose_jql("", self_test_jira_conditions())},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    fingerprint = hashlib.sha256(encoded).hexdigest()
    return QARoster(fingerprint, assignments)


def self_test_jira_conditions(period: str = "month") -> str:
    groups = " OR ".join(f'creator IN membersOf("{group}")' for group in FAE_QA_GROUPS)
    return f"issuetype = Bug AND ({groups}) AND {SELF_TEST_JIRA_CONDITIONS} AND {jira_period_condition(period)}"


def creator_accounts(issues) -> tuple[str, ...]:
    accounts = set()
    for issue in issues:
        fields = issue.get("fields") if isinstance(issue, dict) else None
        creator = fields.get("creator") if isinstance(fields, dict) else None
        if isinstance(creator, dict):
            account = str(creator.get("name") or creator.get("accountId") or creator.get("key") or "").strip().casefold()
            if account:
                accounts.add(account)
    return tuple(sorted(accounts))


FAE_QA_MAPPING_FINGERPRINT = hashlib.sha256(json.dumps({
    "groups": [(group, line.name) for group, line in FAE_QA_GROUP_PRODUCT_LINES],
    "jql": self_test_jira_conditions(),
}, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TeamBugPerson:
    identity: str
    displayName: str
    bugCount: int
    resolvedCount: int
    p0Count: int
    invalidCount: int


@dataclass(frozen=True)
class TeamBugProductLine:
    id: str
    label: str
    people: tuple[TeamBugPerson, ...]


@dataclass(frozen=True)
class TeamBugOverview:
    teamTotal: int
    productLines: tuple[TeamBugProductLine, ...]
    unassignedCount: int = 0
    unmappedCount: int = 0

    def to_payload(self) -> dict[str, Any]:
        return {"teamTotal": self.teamTotal, "unassignedCount": self.unassignedCount,
                "unmappedCount": self.unmappedCount, "productLines": [{
            "id": line.id, "label": line.label,
            "people": [asdict(person) for person in line.people],
        } for line in self.productLines]}


def aggregate_team_bugs(issues: Iterable[dict[str, Any]], roster: QARoster) -> TeamBugOverview:
    assignments = {account: set(lines) for account, lines in roster.assignments}
    people: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {
        "identity": "", "displayName": "", "bugCount": 0,
        "resolvedCount": 0, "p0Count": 0, "invalidCount": 0,
    }))
    total = 0
    unassigned = unmapped = 0
    for issue in issues:
        total += 1
        fields = issue.get("fields") if isinstance(issue, dict) else None
        if not isinstance(fields, dict):
            unassigned += 1
            continue
        creator = fields.get("creator")
        if not isinstance(creator, dict):
            unassigned += 1
            continue
        identity = str(creator.get("name") or creator.get("accountId") or creator.get("key") or "").strip().casefold()
        display_name = str(creator.get("displayName") or identity)
        if not identity:
            unassigned += 1
            continue
        assigned = assignments.get(identity, set())
        if WIRELESS_CONNECTION.name in assigned:
            product_line = WIRELESS_CONNECTION.name
        else:
            project = fields.get("project")
            project_key = str(project.get("key") or "") if isinstance(project, dict) else ""
            line = PRODUCT_LINE_BY_JIRA_PROJECT.get(project_key)
            if line is None:
                unmapped += 1
                continue
            product_line = line.name
        row = people[product_line][identity]
        row["identity"], row["displayName"] = identity, display_name
        row["bugCount"] += 1
        row["resolvedCount"] += _name(fields.get("resolution")) == "Resolved"
        row["p0Count"] += _name(fields.get("priority")) == "P0"
        row["invalidCount"] += _name(fields.get("resolution")) == "Invalid"

    product_lines = []
    for line in TEAM_BUG_LINES:
        rows = [TeamBugPerson(**row) for row in people[line.name].values()]
        rows.sort(key=lambda row: (-row.bugCount, row.displayName.casefold(), row.identity))
        product_lines.append(TeamBugProductLine(line.name, line.name, tuple(rows)))
    return TeamBugOverview(total, tuple(product_lines), unassigned, unmapped)
