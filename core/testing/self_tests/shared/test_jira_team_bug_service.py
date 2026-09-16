import json

from core.jira.services.team_bug_service import QARoster, aggregate_team_bugs, load_fae_qa_roster
from core.product_lines import DASHBOARD_PRODUCT_LINES, PRODUCT_LINES, WIRELESS_CONNECTION


CHINA, SMART, TV_LINE, GLOBAL = PRODUCT_LINES


def roster(**assignments):
    return QARoster(tuple(sorted(assignments)), "test", tuple(
        (account, tuple(lines)) for account, lines in sorted(assignments.items())
    ))


def issue(*, project=TV_LINE.jira_project_keys[0], issue_type="Bug", assignee=None, priority=None, resolution=None):
    return {"fields": {
        "project": {"key": project},
        "issuetype": {"name": issue_type},
        "assignee": assignee,
        "priority": None if priority is None else {"name": priority},
        "resolution": None if resolution is None else {"name": resolution},
    }}


def test_aggregate_team_bugs_uses_exact_jira_names_and_defined_denominators():
    rows = aggregate_team_bugs([
        issue(assignee={"name": "alice", "displayName": "Alice"}, priority="P0", resolution="Resolved"),
        issue(assignee={"name": "alice", "displayName": "Alice"}, priority="p0", resolution="Invalid"),
        issue(assignee={"name": "bob", "displayName": "Bob"}, resolution="Resolved"),
        issue(assignee={"name": "ignored", "displayName": "Ignored"}, issue_type="Task", priority="P0"),
    ], roster(alice=(TV_LINE.name,), bob=(TV_LINE.name,)))

    assert rows.teamTotal == 3
    assert rows.to_payload()["productLines"][2]["people"][0] == {
        "identity": "alice", "displayName": "Alice", "bugCount": 2,
        "resolvedCount": 1, "p0Count": 1, "invalidCount": 1,
    }


def test_outside_roster_and_unassigned_are_rejected_and_ties_sort_by_display_name():
    rows = aggregate_team_bugs([
        issue(), issue(),
        issue(assignee={"accountId": "z", "displayName": "Zed"}),
        issue(assignee={"accountId": "a", "displayName": "Amy"}),
        issue(assignee={"accountId": "outside", "displayName": "Outside"}),
    ], roster(a=(TV_LINE.name,), z=(TV_LINE.name,)))

    assert [row.displayName for row in rows.productLines[2].people] == ["Amy", "Zed"]
    assert rows.teamTotal == 2


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


def test_project_mapping_isolated_per_product_line_and_excludes_fq():
    overview = aggregate_team_bugs([
        issue(project=CHINA.jira_project_keys[0], assignee={"name": "amy", "displayName": "Amy"}),
        issue(project=SMART.jira_project_keys[0], assignee={"name": "amy", "displayName": "Amy"}, resolution="Resolved"),
        issue(project=GLOBAL.jira_project_keys[0], assignee={"name": "zed", "displayName": "Zed"}, priority="P0"),
        issue(project="FQ", assignee={"name": "amy", "displayName": "Amy"}),
    ], roster(amy=(CHINA.name, SMART.name), zed=(GLOBAL.name,)))

    payload = overview.to_payload()
    assert [line["id"] for line in payload["productLines"]] == [line.name for line in DASHBOARD_PRODUCT_LINES]
    assert [line["label"] for line in payload["productLines"]] == [line.name for line in DASHBOARD_PRODUCT_LINES]
    assert all("projectKey" not in line for line in payload["productLines"])
    assert payload["teamTotal"] == 3
    assert payload["productLines"][0]["people"][0]["bugCount"] == 1
    assert payload["productLines"][1]["people"][0]["resolvedCount"] == 1
    assert payload["productLines"][2]["people"] == []
    assert payload["productLines"][3]["people"][0]["p0Count"] == 1


def test_project_and_assignment_both_gate_distribution_with_wireless_precedence():
    overview = aggregate_team_bugs([
        issue(project=TV_LINE.jira_project_keys[0], assignee={"name": "wifi", "displayName": "WiFi"}, resolution="Resolved"),
        issue(project=CHINA.jira_project_keys[0], assignee={"name": "wifi", "displayName": "WiFi"}, priority="P0"),
        issue(project=TV_LINE.jira_project_keys[0], assignee={"name": "tv", "displayName": "TV Owner"}),
        issue(project=SMART.jira_project_keys[0], assignee={"name": "tv", "displayName": "TV Owner"}),
        issue(project=GLOBAL.jira_project_keys[0], assignee={"name": "stb", "displayName": "STB Owner"}, resolution="Invalid"),
        issue(project="FQ", assignee={"name": "wifi", "displayName": "WiFi"}),
        issue(project=TV_LINE.jira_project_keys[0], assignee={"name": "none", "displayName": "No Assignment"}),
    ], roster(wifi=(WIRELESS_CONNECTION.name, TV_LINE.name), tv=(TV_LINE.name,), stb=(GLOBAL.name,), none=()))

    payload = overview.to_payload()
    assert [line["id"] for line in payload["productLines"]] == [line.name for line in DASHBOARD_PRODUCT_LINES]
    assert payload["teamTotal"] == 4
    assert payload["productLines"][2]["people"][0]["displayName"] == "TV Owner"
    assert payload["productLines"][3]["people"][0]["invalidCount"] == 1
    assert payload["productLines"][4]["people"][0] == {
        "identity": "wifi", "displayName": "WiFi", "bugCount": 2,
        "resolvedCount": 1, "p0Count": 1, "invalidCount": 0,
    }
