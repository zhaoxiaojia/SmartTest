import json

import pytest

from core.confluence.personnel_sync import PersonnelAssignmentAmbiguity, PersonnelAssignmentSync
from core.product_lines import PERSONNEL_PRODUCT_LINES


class Page:
    def __init__(self, body, view_body=""):
        self.body, self.view_body, self.version = body, view_body, 7


class Gateway:
    def __init__(self, body=None, error=None, view_body=""):
        self.body, self.error, self.view_body = body, error, view_body
    def get_page(self, page_id):
        assert page_id == "607299166"
        if self.error: raise self.error
        return Page(self.body, self.view_body)
    def resolve_user_keys(self, values):
        return {value: {"account": value, "display_name": value} for value in values}


def employee(name, account, assignments=()):
    return {"display_name": name, "account": account, "active": True,
            "assignments": list(assignments), "system_roles": ["user"]}


def personnel(qa=(), sw=()):
    return {"schema_version": 2, "amlogic": {"departments": {
        "FAE-QA": {"employees": list(qa)}, "FAE-SW": {"employees": list(sw)},
    }}}


def table(rows, header=("业务", "生态/产品", "Owner", "成员1", "成员2", "备注")):
    heading = "".join(f"<th>{value}</th>" for value in header)
    return "<table><tr>" + heading + "</tr>" + "".join(rows) + "</table>"


def test_rowspan_carries_business_and_only_owner_member_columns_supply_people(tmp_path):
    path = tmp_path / "personnel.json"
    original = personnel(
        qa=(employee("Alice Smith", "alice", ({"product_line_id": "Old", "primary": True},)),
            employee("Bob Jones", "bob"), employee("Carol Doe", "carol")),
        sw=(employee("Cross Team", "cross", ({"product_line_id": "TV", "primary": True},)),),
    )
    path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
    body = table([
        '<tr><td rowspan="2">TV</td><td>Alice Smith</td><td><ri:user ri:account-id="ALICE"/></td><td>New</td><td><ri:user ri:account-id="bob"/></td><td>Cross Team</td></tr>',
        '<tr><td>Bob Jones</td><td>Carol Doe</td><td>审批中</td><td></td><td><ri:user ri:account-id="cross"/></td></tr>',
    ])

    assert PersonnelAssignmentSync(Gateway(body), path).refresh() is True
    result = json.loads(path.read_text(encoding="utf-8"))
    qa, sw = (result["amlogic"]["departments"][key]["employees"] for key in ("FAE-QA", "FAE-SW"))
    assert [row["assignments"] for row in qa] == [
        [{"product_line_id": "TV Business", "responsibilities": []}],
        [{"product_line_id": "TV Business", "responsibilities": []}],
        [],
    ]
    assert sw[0]["assignments"] == []
    assert all("primary" not in item for person in qa + sw for item in person["assignments"])


def test_business_label_accepts_only_fixed_label_at_cell_start_with_a_boundary(tmp_path):
    path = tmp_path / "personnel.json"
    original = personnel(qa=(
        employee("Alice Smith", "alice"), employee("Bob Jones", "bob"),
        employee("Carol Doe", "carol"),
    ))
    path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
    body = table([
        '<tr><td rowspan="2"><p>TV</p><p>测试负责人 Jianfan Ai</p><p>人数38</p></td>'
        '<td>x</td><td><ri:user ri:account-id="alice"/></td><td></td><td></td><td></td></tr>',
        '<tr><td>y</td><td></td><td></td><td></td><td></td></tr>',
        '<tr><td><p>海外运营商</p><p>人数9</p></td><td>x</td>'
        '<td><ri:user ri:account-id="bob"/></td><td></td><td></td><td></td></tr>',
        '<tr><td><p>其他业务</p><p>TV</p></td><td>TV</td>'
        '<td><ri:user ri:account-id="carol"/></td><td></td><td></td><td>TV</td></tr>',
    ])
    assert PersonnelAssignmentSync(Gateway(body), path).refresh() is True
    employees = json.loads(path.read_text(encoding="utf-8"))["amlogic"]["departments"]["FAE-QA"]["employees"]
    assert [employee["assignments"] for employee in employees] == [
        [{"product_line_id": "TV Business", "responsibilities": []}],
        [{"product_line_id": "Global Operator & STB Business", "responsibilities": []}],
        [],
    ]


def test_five_mappings_use_only_structured_confluence_identities(tmp_path):
    path = tmp_path / "personnel.json"
    original = personnel(qa=(employee("Alice Smith", "alice"), employee("Bob Jones", "bob")))
    path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [
        f'<tr><td>{business}</td><td>not a person</td><td>{person}</td><td></td><td></td><td></td></tr>'
        for business, person in (
            ("TV", '<ri:user ri:account-id="alice"/>'), ("海外运营商", "Bob Jones"),
            ("互联", '<ri:user ri:username="alice"/>'), ("国内运营商", '<ri:user ri:account-id="alice"/>'),
            ("智能设备", '<ri:user ri:account-id="alice"/>'),
        )
    ]
    assert PersonnelAssignmentSync(Gateway(table(rows)), path).refresh() is True
    values = json.loads(path.read_text(encoding="utf-8"))["amlogic"]["departments"]["FAE-QA"]["employees"]
    assert [item["product_line_id"] for item in values[0]["assignments"]] == [
        "China Operator Business", "Smart Device Business", "TV Business", "Wireless Connection",
    ]
    assert values[1]["assignments"] == []


def test_success_replaces_page_assignments_and_keeps_only_declared_owner_baseline(tmp_path):
    path = tmp_path / "personnel.json"
    original = personnel(
        qa=(employee("Alice Smith", "alice", ({"product_line_id": "Old"},)),),
        sw=(employee("Bob Owner", "bob"), employee("Stale User", "stale", ({"product_line_id": "SmartHome"},))),
    )
    original["amlogic"]["product_lines"] = [
        {"id": "Smart Device Business", "owner_account": "bob"},
        {"id": "TV Business", "owner_account": "tv-owner"},
    ]
    original["amlogic"]["technical_centers"] = [
        {"id": "Wireless Connection", "owner_account": "wifi-owner"},
    ]
    path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
    body = table(['<tr><td>TV</td><td>x</td><td><ri:user ri:account-id="alice-key"/></td><td></td><td></td><td></td></tr>'])
    gateway = Gateway(body)
    gateway.resolve_user_keys = lambda values: {
        "alice-key": {"account": "alice", "display_name": "Alice Smith", "active": True},
    }

    assert PersonnelAssignmentSync(gateway, path).refresh() is True
    departments = json.loads(path.read_text(encoding="utf-8"))["amlogic"]["departments"]
    assert departments["FAE-QA"]["employees"][0]["assignments"] == [
        {"product_line_id": "TV Business", "responsibilities": []},
    ]
    assert departments["FAE-SW"]["employees"][0]["assignments"] == [
        {"product_line_id": "Smart Device Business", "responsibilities": []},
    ]
    assert departments["FAE-SW"]["employees"][1]["assignments"] == []


@pytest.mark.parametrize("body", [
    "<p>unexpected page</p>",
    table(['<tr><td>TV</td><td>x</td><td>Alice Smith</td></tr>'], header=("业务", "产品", "负责人")),
    table(['<tr><td>TV</td><td>x</td><td>张三</td><td></td><td></td><td></td></tr>']),
])
def test_invalid_contract_or_no_explicit_match_leaves_file_intact(tmp_path, body):
    path = tmp_path / "personnel.json"
    before = json.dumps(personnel(qa=(employee("Alice Smith", "alice"),)), ensure_ascii=False, indent=2)
    path.write_text(before, encoding="utf-8")
    with pytest.raises(PersonnelAssignmentAmbiguity):
        PersonnelAssignmentSync(Gateway(body), path).refresh()
    assert path.read_text(encoding="utf-8") == before


def test_duplicate_qa_english_name_or_remote_failure_leaves_file_intact(tmp_path):
    path = tmp_path / "personnel.json"
    before = json.dumps(personnel(qa=(employee("Same Name", "one"), employee("Same Name", "two"))), indent=2)
    path.write_text(before, encoding="utf-8")
    body = table(['<tr><td>TV</td><td>x</td><td>Same Name</td><td></td><td></td><td></td></tr>'])
    with pytest.raises(PersonnelAssignmentAmbiguity): PersonnelAssignmentSync(Gateway(body), path).refresh()
    with pytest.raises(RuntimeError): PersonnelAssignmentSync(Gateway(error=RuntimeError("offline")), path).refresh()
    assert path.read_text(encoding="utf-8") == before


def test_unchanged_refresh_does_not_replace_file(tmp_path):
    path = tmp_path / "personnel.json"
    value = personnel(qa=(employee("Alice Smith", "alice", ({"product_line_id": "TV Business", "responsibilities": []},)),))
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    called = []
    body = table(['<tr><td>TV</td><td>x</td><td><ri:user ri:account-id="alice"/></td><td></td><td></td><td></td></tr>'])
    sync = PersonnelAssignmentSync(Gateway(body), path, replace_file=lambda *args: called.append(args))
    assert sync.refresh() is False
    assert called == []


def test_structured_confluence_identity_resolves_through_confluence_user_api(tmp_path):
    path = tmp_path / "personnel.json"
    value = personnel(qa=(employee("Alice Smith", "alice"),))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    body = table(['<tr><td>TV</td><td>x</td><td><ri:user ri:account-id="alice"/></td><td></td><td></td><td></td></tr>'])

    gateway = Gateway(body)
    calls = []
    gateway.resolve_user_keys = lambda values: calls.append(values) or {
        "alice": {"account": "alice", "display_name": "Alice Smith", "active": True},
    }
    assert PersonnelAssignmentSync(gateway, path).refresh() is True
    assert calls == [("alice",)]


def test_chinese_plain_name_is_skipped_without_blocking_valid_ri_user(tmp_path):
    path = tmp_path / "personnel.json"
    value = personnel(qa=(employee("Alice Smith", "alice"),))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    queries = []
    body = table(['<tr><td>TV</td><td>x</td><td><ri:user ri:account-id="alice"/></td><td>张三</td><td></td><td></td></tr>'])
    gateway = Gateway(body)
    gateway.resolve_user_keys = lambda values: queries.extend(values) or {
        "alice": {"account": "alice", "display_name": "张三"}}
    sync = PersonnelAssignmentSync(gateway, path)

    assert sync.refresh() is True
    result = json.loads(path.read_text(encoding="utf-8"))
    assert queries == ["alice"]
    assert result["amlogic"]["departments"]["FAE-QA"]["employees"][0]["display_name"] == "Alice Smith"
    assert result["amlogic"]["departments"]["FAE-QA"]["employees"][0]["assignments"] == [
        {"product_line_id": "TV Business", "responsibilities": []},
    ]
    assert "张三" not in path.read_text(encoding="utf-8")


def test_non_fae_qa_ri_user_is_skipped_when_another_identity_matches(tmp_path):
    path = tmp_path / "personnel.json"
    before = json.dumps(personnel(qa=(employee("Alice Smith", "alice"),)), ensure_ascii=False, indent=2)
    path.write_text(before, encoding="utf-8")
    body = table(['<tr><td>TV</td><td>x</td><td><ri:user ri:account-id="alice"/></td>'
                  '<td><ri:user ri:account-id="outsider"/></td><td></td><td></td></tr>'])
    gateway = Gateway(body)
    assert PersonnelAssignmentSync(gateway, path).refresh() is True
    assert json.loads(path.read_text(encoding="utf-8"))["amlogic"]["departments"]["FAE-QA"]["employees"][0]["assignments"]


def test_verified_unknown_ri_user_is_added_with_blank_employee_template(tmp_path):
    path = tmp_path / "personnel.json"
    value = personnel(qa=(employee("Alice Smith", "alice"),))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    body = table(['<tr><td>海外运营商</td><td>x</td><td><ri:user ri:account-id="new.user"/></td>'
                  '<td><ri:user ri:account-id="alice"/></td><td></td><td></td></tr>'])
    gateway = Gateway(body)
    gateway.resolve_user_keys = lambda values: {
        "new.user": {"account": "new.user", "display_name": "New User", "active": True},
        "alice": {"account": "alice", "display_name": "Alice Smith", "active": True},
    }
    jira_calls = []
    def jira_users(account):
        jira_calls.append(account)
        return [{"account": "NEW.USER", "display_name": "New User", "active": True}]

    assert PersonnelAssignmentSync(gateway, path, jira_user_resolver=jira_users).refresh() is True
    employees = json.loads(path.read_text(encoding="utf-8"))["amlogic"]["departments"]["FAE-QA"]["employees"]
    created = employees[-1]
    assert jira_calls == ["new.user"]
    assert created == {
        "display_name": "New User", "account": "new.user", "reports_to": "", "active": True,
        "organization": {"team": "", "division": ""},
        "employment": {"grade": "", "job_title_override": "", "employee_type": ""},
        "assignments": [{"product_line_id": "Global Operator & STB Business", "responsibilities": []}],
        "expertise_domains": [], "system_roles": ["user"],
    }


@pytest.mark.parametrize("jira_failure", [False, True])
def test_unknown_jira_failure_or_ambiguity_skips_only_that_identity(tmp_path, jira_failure):
    path = tmp_path / "personnel.json"
    value = personnel(qa=(employee("Alice Smith", "alice"),))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    body = table(['<tr><td>TV</td><td>x</td><td><ri:user ri:account-id="alice"/></td>'
                  '<td><ri:user ri:account-id="unknown"/></td><td></td><td></td></tr>'])
    gateway = Gateway(body)
    gateway.resolve_user_keys = lambda values: {
        value: {"account": value, "display_name": "Unknown User" if value == "unknown" else "Alice Smith", "active": True}
        for value in values
    }
    def ambiguous(_account):
        if jira_failure:
            raise RuntimeError("jira unavailable")
        return [
            {"account": "unknown", "display_name": "Unknown User", "active": True},
            {"account": "unknown", "display_name": "Unknown User", "active": True},
        ]

    assert PersonnelAssignmentSync(gateway, path, jira_user_resolver=ambiguous).refresh() is True
    employees = json.loads(path.read_text(encoding="utf-8"))["amlogic"]["departments"]["FAE-QA"]["employees"]
    assert len(employees) == 1
    assert employees[0]["assignments"] == [{"product_line_id": "TV Business", "responsibilities": []}]


def test_explicit_identity_fills_unique_blank_account_without_jira(tmp_path):
    path = tmp_path / "personnel.json"
    value = personnel(qa=(employee("Wenjie Liu", ""),))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    body = table(['<tr><td>海外运营商</td><td>x</td><td><ri:user ri:account-id="wenjie-key"/></td><td></td><td></td><td></td></tr>'])
    gateway = Gateway(body)
    gateway.resolve_user_keys = lambda _values: {
        "wenjie-key": {"account": "wenjie.liu", "display_name": "Wenjie Liu", "active": True},
    }
    jira_calls = []
    assert PersonnelAssignmentSync(
        gateway, path, jira_user_resolver=lambda account: jira_calls.append(account) or [],
    ).refresh() is True
    person = json.loads(path.read_text(encoding="utf-8"))["amlogic"]["departments"]["FAE-QA"]["employees"][0]
    assert person["account"] == "wenjie.liu"
    assert person["assignments"] == [{"product_line_id": "Global Operator & STB Business", "responsibilities": []}]
    assert jira_calls == []


def test_confluence_user_failure_aborts_transaction(tmp_path):
    path = tmp_path / "personnel.json"
    before = json.dumps(personnel(qa=(employee("Alice Smith", "alice"),)), ensure_ascii=False, indent=2)
    path.write_text(before, encoding="utf-8")
    body = table([
        '<tr><td rowspan="2">TV</td><td>x</td><td><ri:user ri:account-id="alice"/></td><td></td><td></td><td></td></tr>',
        '<tr><td>y</td><td>张三</td><td></td><td></td><td></td></tr>',
    ])
    def fail(_names): raise RuntimeError("confluence unavailable")
    with pytest.raises(RuntimeError):
        PersonnelAssignmentSync(Gateway(body), path, key_resolver=fail).refresh()
    assert path.read_text(encoding="utf-8") == before


def test_plain_chinese_customer_notes_are_skipped(tmp_path):
    path = tmp_path / "personnel.json"
    value = personnel(qa=(employee("Maoguo Xie", "maoguo.xie"), employee("Yanyan Deng", "yanyan.deng")))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    queries = []
    body = table([
        '<tr><td rowspan="2">TV</td><td>x</td><td>谢茂国 (Hisense)</td><td></td><td></td><td></td></tr>',
        '<tr><td>y</td><td>邓炎炎（Sandia）</td><td></td><td></td><td></td></tr>',
    ])
    before = path.read_text(encoding="utf-8")
    with pytest.raises(PersonnelAssignmentAmbiguity): PersonnelAssignmentSync(Gateway(body), path).refresh()
    assert path.read_text(encoding="utf-8") == before


def test_colspan_expansion_keeps_project_customer_text_out_of_person_columns(tmp_path):
    path = tmp_path / "personnel.json"
    value = personnel(qa=(employee("Alice Smith", "alice"), employee("Skyworth", "skyworth")))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    body = table([
        '<tr><td rowspan="2">TV</td><td colspan="3">Skyworth / Changhong projects</td><td></td><td></td></tr>',
        '<tr><td>project detail</td><td><ri:user ri:account-id="alice"/></td><td></td><td></td><td></td></tr>',
    ])
    assert PersonnelAssignmentSync(Gateway(body), path).refresh() is True
    employees = json.loads(path.read_text(encoding="utf-8"))["amlogic"]["departments"]["FAE-QA"]["employees"]
    assert employees[0]["assignments"] == [{"product_line_id": "TV Business", "responsibilities": []}]
    assert employees[1]["assignments"] == []


def test_plain_english_display_name_is_not_used_as_identity(tmp_path):
    path = tmp_path / "personnel.json"
    value = personnel(qa=(employee("Alice (TV)", "alice"),))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    body = table(['<tr><td>TV</td><td>x</td><td>Alice (TV)</td><td></td><td></td><td></td></tr>'])
    before = path.read_text(encoding="utf-8")
    with pytest.raises(PersonnelAssignmentAmbiguity): PersonnelAssignmentSync(Gateway(body), path).refresh()
    assert path.read_text(encoding="utf-8") == before


def test_checked_in_personnel_uses_only_canonical_product_line_names():
    path = __import__("pathlib").Path(__file__).resolve().parents[3] / "config" / "personnel.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    amlogic = value["amlogic"]
    catalogs = [*(amlogic.get("product_lines") or []), *(amlogic.get("technical_centers") or [])]
    assignments = [
        assignment["product_line_id"]
        for department in amlogic["departments"].values()
        for person in department.get("employees", [])
        for assignment in person.get("assignments", [])
    ]
    assert {item["id"] for item in catalogs} == set(PERSONNEL_PRODUCT_LINES)
    assert {item["name"] for item in catalogs} == set(PERSONNEL_PRODUCT_LINES)
    assert {item["id"]: item.get("owner_account") for item in catalogs} == {
        "China Operator Business": "lingling.yu",
        "Smart Device Business": "fred.chen",
        "TV Business": "jianfan.ai",
        "Global Operator & STB Business": "junjie.li",
        "Wireless Connection": "zijie.chen",
    }
    assert set(assignments) <= set(PERSONNEL_PRODUCT_LINES)
    assert not any("primary" in assignment for department in amlogic["departments"].values()
                   for person in department.get("employees", []) for assignment in person.get("assignments", []))
    qa = amlogic["departments"]["FAE-QA"]["employees"]
    all_employees = [
        person
        for department in amlogic["departments"].values()
        for person in department.get("employees", [])
    ]
    all_accounts = [person["account"].casefold() for person in all_employees if person.get("account")]
    all_display_names = [
        person["display_name"].casefold()
        for person in all_employees if person.get("display_name")
    ]
    assert len(set(all_accounts)) == len(all_accounts)
    assert len(set(all_display_names)) == len(all_display_names)
    identities = {person["account"]: person for person in qa if person.get("account")}
    assert len(identities) == len([person for person in qa if person.get("account")])
    display_names = [person["display_name"].casefold() for person in qa if person.get("display_name")]
    assert len(set(display_names)) == len(display_names)
    expected = {
        "yu.zhang1": ("Yu Zhang1", "Wireless Connection"),
        "tracy.chen": ("Tracy Chen", "TV Business"),
        "wenjie.liu": ("Wenjie Liu", "Global Operator & STB Business"),
        "shaochun.chen": ("Shaochun Chen", "Global Operator & STB Business"),
        "yonghua.yan": ("Yonghua Yan", "Wireless Connection"),
        "shouneng.qiu": ("Shouneng Qiu", "China Operator Business"),
    }
    assert {
        account: (person["display_name"], person["assignments"][0]["product_line_id"])
        for account, person in identities.items() if account in expected
    } == expected
    assert "yu.zhang" not in identities and "dan.chen" not in identities
