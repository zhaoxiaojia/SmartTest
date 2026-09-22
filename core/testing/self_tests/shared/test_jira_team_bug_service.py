from core.jira.services.team_bug_service import QARoster, aggregate_team_bugs, load_fae_qa_roster
from core.product_lines import DASHBOARD_PRODUCT_LINES, PRODUCT_LINES, WIRELESS_CONNECTION
import core.jira.services.team_bug_service as service


def test_self_test_card_fixed_boundary_uses_exact_creator_groups():
    assert service.self_test_jira_conditions() == (
        'issuetype = Bug AND (creator IN membersOf("fae-wifi-qa") OR creator IN membersOf("fae-SH-qa")'
        ' OR creator IN membersOf("fae-stb-qa") OR creator IN membersOf("fae-tv-qa")'
        ' OR creator IN membersOf("fae-iptv-qa")) AND "Channel of Reporter" = "Self-Test"'
        ' AND created >= "-30d" AND created <= now()'
    )


def test_self_test_groups_by_qa_creator_not_non_qa_reporter_or_assignee():
    payload = issue(creator={"name": "qa", "displayName": "QA"}, reporter={"name": "outside"})
    payload["fields"]["assignee"] = {"name": "outside", "displayName": "Outside"}
    result = aggregate_team_bugs([payload], roster(qa=(TV_LINE.name,)))
    assert result.productLines[2].people[0].identity == "qa"
    assert result.productLines[2].people[0].displayName == "QA"


def test_wireless_creator_owns_unknown_project_while_other_creator_remains_unmapped():
    result = aggregate_team_bugs([
        issue(project='RK', creator={'name': 'wifi', 'displayName': 'WiFi'}),
        issue(project='RK', creator={'name': 'other', 'displayName': 'Other'}),
    ], roster(wifi=(WIRELESS_CONNECTION.name,), other=(CHINA.name,)))
    assert result.productLines[4].people[0].bugCount == 1
    assert result.productLines[4].people[0].identity == 'wifi'
    assert result.unmappedCount == 1
    assert result.teamTotal == 2
    assert WIRELESS_CONNECTION.jira_project_keys == ()


def test_applied_collection_preserves_page_scope_and_creator_grouping():
    result = aggregate_team_bugs([
        issue(issue_type="Task", creator={"name": "outside", "displayName": "Outside"}),
        issue(creator={"name": "wifi", "displayName": "Wifi"}),
        issue(),
        issue(project="unknown", creator={"name": "outside"}),
        {},
    ], roster(wifi=(WIRELESS_CONNECTION.name,)))
    assert result.teamTotal == 5
    assert result.unassignedCount == 2
    assert result.unmappedCount == 1
    assert result.teamTotal == sum(person.bugCount for line in result.productLines for person in line.people) + result.unassignedCount + result.unmappedCount
    by_line = {line.id: line.people for line in result.productLines}
    assert by_line[TV_LINE.name][0].identity == "outside"
    assert by_line[WIRELESS_CONNECTION.name][0].identity == "wifi"


def test_group_roster_is_deterministic_and_preserves_multiple_memberships():
    class Gateway:
        def __init__(self):
            self.calls = []

        def user_groups(self, account):
            self.calls.append(account)
            return {
                "amy": ("jira-users", "fae-tv-qa"),
                "multi": ("fae-SH-qa", "fae-wifi-qa", "unrelated"),
            }[account]

    gateway = Gateway()
    first = load_fae_qa_roster(gateway, ("multi", "amy", "MULTI"))
    second = load_fae_qa_roster(Gateway(), ("amy", "multi"))

    assert tuple(account for account, _lines in first.assignments) == ("amy", "multi")
    assert dict(first.assignments)["multi"] == (SMART.name, WIRELESS_CONNECTION.name)
    assert first.fingerprint == second.fingerprint
    assert gateway.calls == ["amy", "multi"]


CHINA, SMART, TV_LINE, GLOBAL = PRODUCT_LINES


def roster(**assignments):
    return QARoster("test", tuple(
        (account, tuple(lines)) for account, lines in sorted(assignments.items())
    ))


def issue(*, project=TV_LINE.jira_project_keys[0], issue_type="Bug", creator=None, reporter=None, priority=None, resolution=None):
    return {"fields": {
        "project": {"key": project},
        "issuetype": {"name": issue_type},
        "reporter": reporter,
        "creator": creator,
        "priority": None if priority is None else {"name": priority},
        "resolution": None if resolution is None else {"name": resolution},
    }}


def test_aggregate_team_bugs_uses_exact_jira_names_and_defined_denominators():
    rows = aggregate_team_bugs([
        issue(creator={"name": "alice", "displayName": "Alice"}, priority="P0", resolution="Resolved"),
        issue(creator={"name": "alice", "displayName": "Alice"}, priority="p0", resolution="Invalid"),
        issue(creator={"name": "bob", "displayName": "Bob"}, resolution="Resolved"),
        issue(creator={"name": "ignored", "displayName": "Ignored"}, issue_type="Task", priority="P0"),
    ], roster(alice=(TV_LINE.name,), bob=(TV_LINE.name,)))

    assert rows.teamTotal == 4
    assert rows.to_payload()["productLines"][2]["people"][0] == {
        "identity": "alice", "displayName": "Alice", "bugCount": 2,
        "resolvedCount": 1, "p0Count": 1, "invalidCount": 1,
    }


def test_missing_creators_are_counted_and_ties_sort_by_display_name():
    rows = aggregate_team_bugs([
        issue(), issue(),
        issue(creator={"accountId": "z", "displayName": "Zed"}),
        issue(creator={"accountId": "a", "displayName": "Amy"}),
        issue(creator={"accountId": "outside", "displayName": "Outside"}),
    ], roster(a=(TV_LINE.name,), z=(TV_LINE.name,)))

    assert [row.displayName for row in rows.productLines[2].people] == ["Amy", "Outside", "Zed"]
    assert rows.teamTotal == 5


def test_project_mapping_keeps_unmapped_issues_in_total_but_not_bars():
    overview = aggregate_team_bugs([
        issue(project=CHINA.jira_project_keys[0], creator={"name": "amy", "displayName": "Amy"}),
        issue(project=SMART.jira_project_keys[0], creator={"name": "amy", "displayName": "Amy"}, resolution="Resolved"),
        issue(project=GLOBAL.jira_project_keys[0], creator={"name": "zed", "displayName": "Zed"}, priority="P0"),
        issue(project="FQ", creator={"name": "amy", "displayName": "Amy"}),
    ], roster(amy=(CHINA.name, SMART.name), zed=(GLOBAL.name,)))

    payload = overview.to_payload()
    assert [line["id"] for line in payload["productLines"]] == [line.name for line in DASHBOARD_PRODUCT_LINES]
    assert [line["label"] for line in payload["productLines"]] == [line.name for line in DASHBOARD_PRODUCT_LINES]
    assert all("projectKey" not in line for line in payload["productLines"])
    assert payload["teamTotal"] == 4
    assert payload["unmappedCount"] == 1
    assert payload["productLines"][0]["people"][0]["bugCount"] == 1
    assert payload["productLines"][1]["people"][0]["resolvedCount"] == 1
    assert payload["productLines"][2]["people"] == []
    assert payload["productLines"][3]["people"][0]["p0Count"] == 1


def test_project_mapping_uses_wireless_creator_assignment_precedence():
    overview = aggregate_team_bugs([
        issue(project=TV_LINE.jira_project_keys[0], creator={"name": "wifi", "displayName": "WiFi"}, resolution="Resolved"),
        issue(project=CHINA.jira_project_keys[0], creator={"name": "wifi", "displayName": "WiFi"}, priority="P0"),
        issue(project=TV_LINE.jira_project_keys[0], creator={"name": "tv", "displayName": "TV Owner"}),
        issue(project=SMART.jira_project_keys[0], creator={"name": "tv", "displayName": "TV Owner"}),
        issue(project=GLOBAL.jira_project_keys[0], creator={"name": "stb", "displayName": "STB Owner"}, resolution="Invalid"),
        issue(project="FQ", creator={"name": "wifi", "displayName": "WiFi"}),
        issue(project=TV_LINE.jira_project_keys[0], creator={"name": "none", "displayName": "No Assignment"}),
    ], roster(wifi=(WIRELESS_CONNECTION.name, TV_LINE.name), tv=(TV_LINE.name,), stb=(GLOBAL.name,), none=()))

    payload = overview.to_payload()
    assert [line["id"] for line in payload["productLines"]] == [line.name for line in DASHBOARD_PRODUCT_LINES]
    assert payload["teamTotal"] == 7
    assert payload["unmappedCount"] == 0
    assert {person['displayName'] for person in payload["productLines"][2]["people"]} == {'TV Owner', 'No Assignment'}
    assert payload["productLines"][3]["people"][0]["invalidCount"] == 1
    assert payload["productLines"][4]["people"][0] == {
        "identity": "wifi", "displayName": "WiFi", "bugCount": 3,
        "resolvedCount": 1, "p0Count": 1, "invalidCount": 0,
    }
