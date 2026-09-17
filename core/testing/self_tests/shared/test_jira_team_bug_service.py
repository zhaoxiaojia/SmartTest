import json

from core.jira.services.team_bug_service import QARoster, aggregate_team_bugs, load_fae_qa_roster
from core.product_lines import DASHBOARD_PRODUCT_LINES, PRODUCT_LINES, WIRELESS_CONNECTION
import core.jira.services.team_bug_service as service


def test_self_test_card_fixed_boundary_uses_active_qa_reporters_and_rejects_empty_roster():
    import pytest
    assert service.self_test_jira_conditions(("qa.two", "qa.one")) == (
        'issuetype = Bug AND reporter IN ("qa.two", "qa.one") AND "Channel of Reporter" = "Self-Test"'
        ' AND created >= startOfYear() AND created <= endOfYear()'
    )
    with pytest.raises(ValueError, match="empty_fae_qa_roster"):
        service.self_test_jira_conditions(())


def test_self_test_groups_by_qa_reporter_not_non_qa_assignee():
    payload = issue(reporter={"name": "qa", "displayName": "QA"})
    payload["fields"]["assignee"] = {"name": "outside", "displayName": "Outside"}
    result = aggregate_team_bugs([payload], roster(qa=(TV_LINE.name,)))
    assert result.productLines[2].people[0].identity == "qa"
    assert result.productLines[2].people[0].displayName == "QA"


def test_wireless_reporter_owns_unknown_project_while_other_reporter_remains_unmapped():
    result = aggregate_team_bugs([
        issue(project='RK', reporter={'name': 'wifi', 'displayName': 'WiFi'}),
        issue(project='RK', reporter={'name': 'other', 'displayName': 'Other'}),
    ], roster(wifi=(WIRELESS_CONNECTION.name,), other=(CHINA.name,)))
    assert result.productLines[4].people[0].bugCount == 1
    assert result.productLines[4].people[0].identity == 'wifi'
    assert result.unmappedCount == 1
    assert result.teamTotal == 2
    assert WIRELESS_CONNECTION.jira_project_keys == ()


def test_applied_collection_preserves_page_scope_and_reporter_grouping():
    result = aggregate_team_bugs([
        issue(issue_type="Task", reporter={"name": "outside", "displayName": "Outside"}),
        issue(reporter={"name": "wifi", "displayName": "Wifi"}),
        issue(),
        issue(project="unknown", reporter={"name": "outside"}),
        {},
    ], roster(wifi=(WIRELESS_CONNECTION.name,)))
    assert result.teamTotal == 5
    assert result.unassignedCount == 2
    assert result.unmappedCount == 1
    assert result.teamTotal == sum(person.bugCount for line in result.productLines for person in line.people) + result.unassignedCount + result.unmappedCount
    by_line = {line.id: line.people for line in result.productLines}
    assert by_line[TV_LINE.name][0].identity == "outside"
    assert by_line[WIRELESS_CONNECTION.name][0].identity == "wifi"


def test_query_or_calendar_year_change_invalidates_roster_snapshot_identity(tmp_path, monkeypatch):
    path = tmp_path / "personnel.json"
    path.write_text(json.dumps({"amlogic": {"departments": {"FAE-QA": {"employees": [{"account": "amy"}]}}}}), encoding="utf-8")
    first = load_fae_qa_roster(path)
    monkeypatch.setattr(service, "self_test_jira_conditions", lambda _accounts: "different query")
    assert load_fae_qa_roster(path).fingerprint != first.fingerprint
    second = load_fae_qa_roster(path)
    class NextYear:
        @staticmethod
        def today():
            return type("Day", (), {"year": 2099})()
    monkeypatch.setattr(service, "date", NextYear)
    assert load_fae_qa_roster(path).fingerprint != second.fingerprint


CHINA, SMART, TV_LINE, GLOBAL = PRODUCT_LINES


def roster(**assignments):
    return QARoster(tuple(sorted(assignments)), "test", tuple(
        (account, tuple(lines)) for account, lines in sorted(assignments.items())
    ))


def issue(*, project=TV_LINE.jira_project_keys[0], issue_type="Bug", reporter=None, priority=None, resolution=None):
    return {"fields": {
        "project": {"key": project},
        "issuetype": {"name": issue_type},
        "reporter": reporter,
        "priority": None if priority is None else {"name": priority},
        "resolution": None if resolution is None else {"name": resolution},
    }}


def test_aggregate_team_bugs_uses_exact_jira_names_and_defined_denominators():
    rows = aggregate_team_bugs([
        issue(reporter={"name": "alice", "displayName": "Alice"}, priority="P0", resolution="Resolved"),
        issue(reporter={"name": "alice", "displayName": "Alice"}, priority="p0", resolution="Invalid"),
        issue(reporter={"name": "bob", "displayName": "Bob"}, resolution="Resolved"),
        issue(reporter={"name": "ignored", "displayName": "Ignored"}, issue_type="Task", priority="P0"),
    ], roster(alice=(TV_LINE.name,), bob=(TV_LINE.name,)))

    assert rows.teamTotal == 4
    assert rows.to_payload()["productLines"][2]["people"][0] == {
        "identity": "alice", "displayName": "Alice", "bugCount": 2,
        "resolvedCount": 1, "p0Count": 1, "invalidCount": 1,
    }


def test_missing_reporters_are_counted_and_ties_sort_by_display_name():
    rows = aggregate_team_bugs([
        issue(), issue(),
        issue(reporter={"accountId": "z", "displayName": "Zed"}),
        issue(reporter={"accountId": "a", "displayName": "Amy"}),
        issue(reporter={"accountId": "outside", "displayName": "Outside"}),
    ], roster(a=(TV_LINE.name,), z=(TV_LINE.name,)))

    assert [row.displayName for row in rows.productLines[2].people] == ["Amy", "Outside", "Zed"]
    assert rows.teamTotal == 5


def test_fae_qa_roster_keeps_active_accounts_in_stable_order_and_fingerprint(tmp_path):
    path = tmp_path / "personnel.json"
    path.write_text(json.dumps({"amlogic": {"departments": {"FAE-QA": {"employees": [
        {"account": " Zed ", "active": True}, {"account": "amy"},
        {"account": "disabled", "active": False}, {"account": ""}, {"account": "AMY"},
    ]}}}}), encoding="utf-8")

    first = load_fae_qa_roster(path)
    second = load_fae_qa_roster(path)

    assert first.accounts == ("amy", "zed")
    assert first.fingerprint == second.fingerprint


def test_assignment_changes_roster_fingerprint(tmp_path):
    path = tmp_path / "personnel.json"
    payload = {"amlogic": {"departments": {"FAE-QA": {"employees": [
        {"account": "amy", "assignments": [{"product_line_id": TV_LINE.name}]},
    ]}}}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    first = load_fae_qa_roster(path)
    payload["amlogic"]["departments"]["FAE-QA"]["employees"][0]["assignments"] = [{"product_line_id": SMART.name}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert first.fingerprint != load_fae_qa_roster(path).fingerprint


def test_project_mapping_keeps_unmapped_issues_in_total_but_not_bars():
    overview = aggregate_team_bugs([
        issue(project=CHINA.jira_project_keys[0], reporter={"name": "amy", "displayName": "Amy"}),
        issue(project=SMART.jira_project_keys[0], reporter={"name": "amy", "displayName": "Amy"}, resolution="Resolved"),
        issue(project=GLOBAL.jira_project_keys[0], reporter={"name": "zed", "displayName": "Zed"}, priority="P0"),
        issue(project="FQ", reporter={"name": "amy", "displayName": "Amy"}),
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


def test_project_mapping_uses_wireless_reporter_assignment_precedence():
    overview = aggregate_team_bugs([
        issue(project=TV_LINE.jira_project_keys[0], reporter={"name": "wifi", "displayName": "WiFi"}, resolution="Resolved"),
        issue(project=CHINA.jira_project_keys[0], reporter={"name": "wifi", "displayName": "WiFi"}, priority="P0"),
        issue(project=TV_LINE.jira_project_keys[0], reporter={"name": "tv", "displayName": "TV Owner"}),
        issue(project=SMART.jira_project_keys[0], reporter={"name": "tv", "displayName": "TV Owner"}),
        issue(project=GLOBAL.jira_project_keys[0], reporter={"name": "stb", "displayName": "STB Owner"}, resolution="Invalid"),
        issue(project="FQ", reporter={"name": "wifi", "displayName": "WiFi"}),
        issue(project=TV_LINE.jira_project_keys[0], reporter={"name": "none", "displayName": "No Assignment"}),
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
