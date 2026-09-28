from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Iterable

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


def _fixed_jql(issue_type: str, period: str, *, channel: str = "", customer: bool = False) -> str:
    conditions = [f"issuetype = {issue_type}"]
    if customer:
        conditions.append(f'"Channel of Reporter" = "{channel}"')
        labels = _quoted(CUSTOMER_WIRELESS_LABELS)
        projects = _quoted(PRODUCT_LINE_BY_JIRA_PROJECT)
        wireless = (
            f"labels IN ({labels}) AND (resolution is EMPTY OR resolution NOT IN "
            f"({_quoted(CUSTOMER_WIRELESS_EXCLUDED_RESOLUTIONS)})) AND project NOT IN "
            f"({_quoted(CUSTOMER_WIRELESS_EXCLUDED_PROJECTS)})"
        )
        standard = f"project IN ({projects}) AND (labels is EMPTY OR labels NOT IN ({labels}))"
        conditions.append(f"(({wireless}) OR ({standard}))")
    else:
        conditions.append(f"({_creator_group_jql()})")
        if channel:
            conditions.append(f'"Channel of Reporter" = "{channel}"')
    conditions.append(jira_period_condition(period))
    return " AND ".join(conditions)


@dataclass(frozen=True)
class JiraStatisticsCardDefinition:
    card_key: str
    title: str
    first_metric_label: str
    issue_type: str
    channel: str = ""
    customer_rules: bool = False
    compatibility_fingerprint: str = ""

    def fixed_jql(self, period: str) -> str:
        return _fixed_jql(self.issue_type, period, channel=self.channel, customer=self.customer_rules)

    @property
    def fingerprint(self) -> str:
        if self.compatibility_fingerprint:
            return self.compatibility_fingerprint
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


SELF_TEST_COMPATIBILITY_FINGERPRINT = hashlib.sha256(json.dumps({
    "groups": [(group, line.name) for group, line in FAE_QA_GROUP_PRODUCT_LINES],
    "jql": _fixed_jql("Bug", "month", channel="Self-Test"),
}, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


JIRA_STATISTICS_CARDS = {
    definition.card_key: definition for definition in (
        JiraStatisticsCardDefinition(
            "self-test", "Product Lines Self Test Jiras Statistics", "Bugs", "Bug", "Self-Test", False,
            SELF_TEST_COMPATIBILITY_FINGERPRINT,
        ),
        JiraStatisticsCardDefinition(
            "task", "Product Lines Task Jiras Statistics", "Tasks", "Task",
        ),
        JiraStatisticsCardDefinition(
            "customer-feedback", "Product Lines Customer Feedback Jiras Statistics", "Bugs", "Bug",
            "Customer-Feedback", True,
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
        fixed = _fixed_jql(definition.issue_type, period, channel=definition.channel,
                           customer=definition.customer_rules)
        fixed = fixed.replace(jira_period_condition(period), str(value["condition"]))
        result[key] = {**value, "jql": compose_jql(user_jql, fixed)}
    return result


@dataclass(frozen=True)
class QARoster:
    fingerprint: str
    assignments: tuple[tuple[str, tuple[str, ...]], ...] = ()


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


def load_fae_qa_roster(gateway, accounts) -> QARoster:
    by_account: dict[str, set[str]] = defaultdict(set)
    product_line_by_group = dict(FAE_QA_GROUP_PRODUCT_LINES)
    for account in sorted({str(value or "").strip().casefold() for value in accounts if str(value or "").strip()}):
        by_account[account].update(
            product_line_by_group[group].name
            for group in gateway.user_groups(account) if group in product_line_by_group
        )
    assignments = tuple((account, tuple(sorted(lines))) for account, lines in sorted(by_account.items()))
    fingerprint = hashlib.sha256(json.dumps(assignments, separators=(",", ":")).encode()).hexdigest()
    return QARoster(fingerprint, assignments)


@dataclass(frozen=True)
class JiraStatisticsPerson:
    identity: str
    displayName: str
    bugCount: int
    resolvedCount: int
    p0Count: int
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


def _product_line(fields: dict[str, Any], assignments: set[str], definition: JiraStatisticsCardDefinition):
    labels = fields.get("labels") if isinstance(fields.get("labels"), list) else []
    if definition.customer_rules and any(label in CUSTOMER_WIRELESS_LABELS for label in labels):
        return WIRELESS_CONNECTION.name
    if not definition.customer_rules and WIRELESS_CONNECTION.name in assignments:
        return WIRELESS_CONNECTION.name
    project = fields.get("project")
    project_key = str(project.get("key") or "") if isinstance(project, dict) else ""
    line = PRODUCT_LINE_BY_JIRA_PROJECT.get(project_key)
    return line.name if line else ""


def aggregate_jira_statistics(
    issues: Iterable[dict[str, Any]], roster: QARoster, definition: JiraStatisticsCardDefinition,
) -> JiraStatisticsOverview:
    assignments = {account: set(lines) for account, lines in roster.assignments}
    people: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {
        "identity": "", "displayName": "", "bugCount": 0,
        "resolvedCount": 0, "p0Count": 0, "invalidCount": 0,
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
        product_line = _product_line(fields, assignments.get(identity, set()), definition)
        if not product_line:
            unmapped += 1
            continue
        row = people[product_line][identity]
        row["identity"] = identity
        row["displayName"] = str(creator.get("displayName") or identity)
        row["bugCount"] += 1
        row["resolvedCount"] += _name(fields.get("resolution")) == "Resolved"
        row["p0Count"] += _name(fields.get("priority")) == "P0"
        row["invalidCount"] += _name(fields.get("resolution")) == "Invalid"

    product_lines = []
    for line in DASHBOARD_PRODUCT_LINES:
        rows = [JiraStatisticsPerson(**row) for row in people[line.name].values()]
        rows.sort(key=lambda row: (-row.bugCount, row.displayName.casefold(), row.identity))
        product_lines.append(JiraStatisticsProductLine(line.name, line.name, tuple(rows)))
    return JiraStatisticsOverview(total, tuple(product_lines), unassigned, unmapped)


def build_comparison_statistics(definition: JiraStatisticsCardDefinition, gateway, current_rows,
                                previous_rows, ranges) -> dict[str, Any]:
    all_rows = [*current_rows, *previous_rows]
    roster = (load_fae_qa_roster(gateway, creator_accounts(all_rows))
              if not definition.customer_rules else QARoster(definition.fingerprint))
    clean_ranges = {
        key: {name: value for name, value in period.items() if name in {"start", "end"}}
        for key, period in ranges.items()
    }
    current = aggregate_jira_statistics(current_rows, roster, definition).to_payload()
    previous = aggregate_jira_statistics(previous_rows, roster, definition).to_payload()
    return {
        **current,
        "ranges": clean_ranges,
        "current": current,
        "previous": previous,
    }
