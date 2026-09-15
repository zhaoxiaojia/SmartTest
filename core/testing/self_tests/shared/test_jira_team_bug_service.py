import json

from core.jira.services.team_bug_service import aggregate_team_bugs, load_fae_qa_roster


def issue(*, project="TV", issue_type="Bug", assignee=None, priority=None, resolution=None):
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
    ], ("alice", "bob"))

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
    ], ("a", "z"))

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


def test_project_mapping_isolated_per_product_line_and_excludes_fq():
    overview = aggregate_team_bugs([
        issue(project="IPTV", assignee={"name": "amy", "displayName": "Amy"}),
        issue(project="SH", assignee={"name": "amy", "displayName": "Amy"}, resolution="Resolved"),
        issue(project="OTT", assignee={"name": "zed", "displayName": "Zed"}, priority="P0"),
        issue(project="FQ", assignee={"name": "amy", "displayName": "Amy"}),
    ], ("amy", "zed"))

    payload = overview.to_payload()
    assert [(line["id"], line["projectKey"]) for line in payload["productLines"]] == [
        ("DOPL", "IPTV"), ("SDPL", "SH"), ("TV", "TV"), ("OOPL", "OTT"),
    ]
    assert payload["teamTotal"] == 3
    assert payload["productLines"][0]["people"][0]["bugCount"] == 1
    assert payload["productLines"][1]["people"][0]["resolvedCount"] == 1
    assert payload["productLines"][2]["people"] == []
    assert payload["productLines"][3]["people"][0]["p0Count"] == 1
