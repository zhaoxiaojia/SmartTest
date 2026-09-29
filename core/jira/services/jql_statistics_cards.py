from __future__ import annotations

from collections import defaultdict
from datetime import date
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Iterable

from core.jira.mapper import JiraIssueMapper
from core.jira.services.filter_service import compose_jql, jira_period_condition, jira_period_ranges
from core.product_lines import (
    CHINA_OPERATOR_BUSINESS,
    DASHBOARD_PRODUCT_LINES,
    GLOBAL_OPERATOR_STB_BUSINESS,
    PRODUCT_LINE_BY_JIRA_PROJECT,
    SMART_DEVICE_BUSINESS,
    TV_BUSINESS,
    WIRELESS_CONNECTION,
)


FAE_QA_GROUP_PRODUCT_LINES = (
    ("fae-wifi-qa", WIRELESS_CONNECTION),
    ("fae-SH-qa", SMART_DEVICE_BUSINESS),
    ("fae-stb-qa", GLOBAL_OPERATOR_STB_BUSINESS),
    ("fae-tv-qa", TV_BUSINESS),
    ("fae-iptv-qa", CHINA_OPERATOR_BUSINESS),
)
FAE_QA_GROUPS = tuple(group for group, _line in FAE_QA_GROUP_PRODUCT_LINES)
CUSTOMER_WIRELESS_LABELS = (
    "Customer_W1", "Customer_W1U", "Customer_W2L", "customer_w2",
    "Customer_w1u", "customer-w2", "customer-w2L", "customer_w1d",
)
CUSTOMER_WIRELESS_EXCLUDED_RESOLUTIONS = (
    "Invalid Case", "Cannot Reproduce", "HW Fix", "Won't Fix", "Won't Do",
)
CUSTOMER_WIRELESS_EXCLUDED_PROJECTS = ("RD SW Platform", "Wireless Project")


def _quoted(values: Iterable[str]) -> str:
    return ", ".join(f'"{value}"' for value in values)


def _creator_group_jql() -> str:
    return " OR ".join(f'creator IN membersOf("{group}")' for group in FAE_QA_GROUPS)


def _customer_jql() -> str:
    labels = _quoted(CUSTOMER_WIRELESS_LABELS)
    projects = _quoted(PRODUCT_LINE_BY_JIRA_PROJECT)
    wireless = (
        f"labels IN ({labels}) AND (resolution is EMPTY OR resolution NOT IN "
        f"({_quoted(CUSTOMER_WIRELESS_EXCLUDED_RESOLUTIONS)})) AND project NOT IN "
        f"({_quoted(CUSTOMER_WIRELESS_EXCLUDED_PROJECTS)})"
    )
    standard = f"project IN ({projects}) AND (labels is EMPTY OR labels NOT IN ({labels}))"
    return f'issuetype = Bug AND "Channel of Reporter" = "Customer-Feedback" AND (({wireless}) OR ({standard}))'


@dataclass(frozen=True)
class JiraStatisticsCardDefinition:
    card_key: str
    title: str
    first_metric_label: str
    custom_jql: str

    def fixed_jql(self, period: str) -> str:
        return f"({_creator_group_jql()}) AND ({self.custom_jql}) AND {jira_period_condition(period)}"

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps({"definition": asdict(self), "groups": FAE_QA_GROUPS,
                              "aggregation": "qa-creators-comments-verify-v4"}, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


JIRA_STATISTICS_CARDS = {
    definition.card_key: definition for definition in (
        JiraStatisticsCardDefinition(
            "self-test", "Product Lines Self Test Jiras Statistics", "Bugs",
            'issuetype = Bug AND "Channel of Reporter" = "Self-Test"',
        ),
        JiraStatisticsCardDefinition(
            "task", "Product Lines Task Jiras Statistics", "Tasks", "issuetype = Task",
        ),
        JiraStatisticsCardDefinition(
            "customer-feedback", "Product Lines Customer Feedback Jiras Statistics", "Bugs", _customer_jql(),
        ),
    )
}


def card_definition(card_key: str) -> JiraStatisticsCardDefinition:
    return JIRA_STATISTICS_CARDS[card_key]


def effective_card_jql_pair(card_key: str, user_jql: str, period: str, today=None) -> dict[str, dict[str, Any]]:
    definition = card_definition(card_key)
    ranges = jira_period_ranges(period, today)
    result = {}
    for key, value in ranges.items():
        fixed = definition.fixed_jql(period)
        fixed = fixed.replace(jira_period_condition(period), str(value["condition"]))
        result[key] = {**value, "jql": compose_jql(user_jql, fixed)}
    return result


@dataclass(frozen=True)
class QARoster:
    fingerprint: str
    assignments: tuple[tuple[str, tuple[str, ...]], ...] = ()


def statistics_accounts(issues) -> tuple[str, ...]:
    accounts = set()
    for issue in issues:
        fields = issue.get("fields") if isinstance(issue, dict) else None
        creator = fields.get("creator") if isinstance(fields, dict) else None
        if isinstance(creator, dict):
            account = str(creator.get("name") or creator.get("accountId") or creator.get("key") or "").strip().casefold()
            if account:
                accounts.add(account)
        if isinstance(fields, dict):
            for comment in _comments(fields):
                if comment.author:
                    account = (comment.author.account or comment.author.identity).strip().casefold()
                    if account:
                        accounts.add(account)
        verification = JiraIssueMapper.last_verification(issue) if isinstance(issue, dict) else None
        if verification and verification.author:
            account = (verification.author.account or verification.author.identity).strip().casefold()
            if account:
                accounts.add(account)
    return tuple(sorted(accounts))


def load_fae_qa_roster(gateway, accounts, *, groups_cache=None) -> QARoster:
    groups_cache = {} if groups_cache is None else groups_cache
    by_account: dict[str, set[str]] = defaultdict(set)
    product_line_by_group = dict(FAE_QA_GROUP_PRODUCT_LINES)
    for account in sorted({str(value or "").strip().casefold() for value in accounts if str(value or "").strip()}):
        if account not in groups_cache:
            groups_cache[account] = tuple(gateway.user_groups(account))
        by_account[account].update(
            product_line_by_group[group].name
            for group in groups_cache[account] if group in product_line_by_group
        )
    assignments = tuple((account, tuple(sorted(lines))) for account, lines in sorted(by_account.items()))
    fingerprint = hashlib.sha256(json.dumps(assignments, separators=(",", ":")).encode()).hexdigest()
    return QARoster(fingerprint, assignments)


@dataclass(frozen=True)
class JiraStatisticsPerson:
    identity: str
    displayName: str
    bugCount: int
    commentCount: int
    verifyCount: int
    invalidCount: int


@dataclass(frozen=True)
class JiraStatisticsProductLine:
    id: str
    label: str
    people: tuple[JiraStatisticsPerson, ...]


@dataclass(frozen=True)
class JiraStatisticsOverview:
    teamTotal: int
    productLines: tuple[JiraStatisticsProductLine, ...]
    unassignedCount: int = 0
    unmappedCount: int = 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "teamTotal": self.teamTotal,
            "unassignedCount": self.unassignedCount,
            "unmappedCount": self.unmappedCount,
            "productLines": [{
                "id": line.id,
                "label": line.label,
                "people": [asdict(person) for person in line.people],
            } for line in self.productLines],
        }


def _name(value: Any) -> str:
    return str(value.get("name") or "") if isinstance(value, dict) else ""


def _comments(fields):
    return tuple(JiraIssueMapper.from_comment(item) for item in (fields.get("comment") or {}).get("comments", ()))


def _product_line(fields: dict[str, Any], assignments: set[str]):
    if WIRELESS_CONNECTION.name in assignments:
        return WIRELESS_CONNECTION.name
    project = fields.get("project")
    project_key = str(project.get("key") or "") if isinstance(project, dict) else ""
    line = PRODUCT_LINE_BY_JIRA_PROJECT.get(project_key)
    return line.name if line else ""


def aggregate_jira_statistics(
    issues: Iterable[dict[str, Any]], roster: QARoster,
) -> JiraStatisticsOverview:
    assignments = {account: set(lines) for account, lines in roster.assignments}
    people: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {
        "identity": "", "displayName": "", "bugCount": 0,
        "commentCount": 0, "verifyCount": 0, "invalidCount": 0,
    }))
    total = unassigned = unmapped = 0
    for issue in issues:
        total += 1
        fields = issue.get("fields") if isinstance(issue, dict) else None
        creator = fields.get("creator") if isinstance(fields, dict) else None
        if not isinstance(fields, dict) or not isinstance(creator, dict):
            unassigned += 1
            continue
        identity = str(creator.get("name") or creator.get("accountId") or creator.get("key") or "").strip().casefold()
        if not identity:
            unassigned += 1
            continue
        if not assignments.get(identity):
            total -= 1
            continue
        comment_line = _product_line(fields, set())
        if comment_line:
            for comment in _comments(fields):
                author = comment.author
                if not author:
                    continue
                account = (author.account or author.identity).strip().casefold()
                if not assignments.get(account):
                    continue
                comment_row = people[comment_line][account]
                comment_row["identity"] = account
                comment_row["displayName"] = author.display_name or account
                comment_row["commentCount"] += 1
        verification = JiraIssueMapper.last_verification(issue)
        if comment_line and verification and verification.author:
            author = verification.author
            account = (author.account or author.identity).strip().casefold()
            if assignments.get(account):
                verify_row = people[comment_line][account]
                verify_row["identity"] = account
                verify_row["displayName"] = author.display_name or account
                verify_row["verifyCount"] += 1
        product_line = _product_line(fields, assignments[identity])
        if not product_line:
            unmapped += 1
            continue
        row = people[product_line][identity]
        row["identity"] = identity
        row["displayName"] = str(creator.get("displayName") or identity)
        row["bugCount"] += 1
        row["invalidCount"] += _name(fields.get("resolution")) == "Invalid"

    product_lines = []
    for line in DASHBOARD_PRODUCT_LINES:
        rows = [JiraStatisticsPerson(**row) for row in people[line.name].values()]
        rows.sort(key=lambda row: (-row.bugCount, row.displayName.casefold(), row.identity))
        product_lines.append(JiraStatisticsProductLine(line.name, line.name, tuple(rows)))
    return JiraStatisticsOverview(total, tuple(product_lines), unassigned, unmapped)


def build_comparison_statistics(gateway, current_rows, previous_rows, ranges, *, groups_cache=None) -> dict[str, Any]:
    all_rows = [*current_rows, *previous_rows]
    roster = load_fae_qa_roster(gateway, statistics_accounts(all_rows), groups_cache=groups_cache)
    clean_ranges = {
        key: {name: value for name, value in period.items() if name in {"start", "end"}}
        for key, period in ranges.items()
    }
    current = aggregate_jira_statistics(current_rows, roster).to_payload()
    previous = aggregate_jira_statistics(previous_rows, roster).to_payload()
    return {
        **current,
        "ranges": clean_ranges,
        "current": current,
        "previous": previous,
    }


def build_annual_facts(gateway, current_rows, previous_rows, *, groups_cache=None):
    rows = [*current_rows, *previous_rows]
    roster = load_fae_qa_roster(gateway, statistics_accounts(rows), groups_cache=groups_cache)
    facts = []
    for issue in rows:
        statistics = aggregate_jira_statistics([issue], roster).to_payload()
        statistics["productLines"] = [line for line in statistics["productLines"] if line["people"]]
        verification = JiraIssueMapper.last_verification(issue)
        fields = issue.get("fields", {})
        creator = fields.get("creator") or {}
        facts.append({"issueId": str(issue["id"]), "createdAt": str(fields.get("created") or ""),
                      "creator": {key: creator[key] for key in ("name", "accountId", "key", "displayName") if key in creator},
                      "projectKey": (fields.get("project") or {}).get("key", ""), "statistics": statistics,
                      "verification": {"author": asdict(verification.author) if verification.author else None,
                                       "createdAt": verification.created_at.isoformat()} if verification else None})
    return {"_facts": facts, "roster": asdict(roster), "annual": True}


def aggregate_annual_facts(facts, metadata, period, today=None):
    today = today or date.today()
    ranges = jira_period_ranges(period, today)
    output = {}
    availability = {}
    for key, window in ranges.items():
        start, end = window["start"], window["end"]
        years = (["previous"] if start < f"{today.year}-01-01" else [])
        if end is None or end > f"{today.year}-01-01":
            years.append("current")
        availability[key] = {metric: all(metadata["availability"][year][metric] for year in years)
                             for metric in ("basic", "verify")}
        summary = aggregate_jira_statistics([], QARoster("", ())).to_payload()
        by_line = {line["id"]: {} for line in summary["productLines"]}
        for fact in facts:
            created = fact["createdAt"][:10]
            if not created or created < start or (end is not None and created >= end):
                continue
            contribution = fact["statistics"]
            for count in ("teamTotal", "unassignedCount", "unmappedCount"):
                summary[count] += contribution[count]
            for line in contribution["productLines"]:
                for person in line["people"]:
                    target = by_line[line["id"]].setdefault(person["identity"], {
                        "identity": person["identity"], "displayName": person["displayName"],
                        "bugCount": 0, "commentCount": 0, "verifyCount": 0, "invalidCount": 0})
                    for metric in ("bugCount", "commentCount", "verifyCount", "invalidCount"):
                        target[metric] += person[metric]
        for line in summary["productLines"]:
            line["people"] = sorted(by_line[line["id"]].values(),
                                    key=lambda person: (-person["bugCount"], person["displayName"].casefold(), person["identity"]))
            if not availability[key]["verify"]:
                for person in line["people"]:
                    person.pop("verifyCount")
        output[key] = summary
    return {**output["current"], **output, "availability": availability,
            "ranges": {key: {name: value for name, value in window.items() if name != "condition"}
                       for key, window in ranges.items()}}
