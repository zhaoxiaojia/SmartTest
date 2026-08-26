from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from smarttest_web.app import create_app
from smarttest_web.report_workspace import ClientAuditReportOwner
from smarttest_web.project_facts_api import ProjectFactsWebOwner


def _workbook(path, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Report"
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_jira_reports_are_listed_previewed_and_downloaded_from_client_export(tmp_path):
    report = tmp_path / "jira_format_audit_20260826_143000.xlsx"
    _workbook(report, [["指标", "值"], ["问题总数", 3], ["通过 Jira 数", 2]])
    owner = ClientAuditReportOwner(jira_dir=tmp_path, confluence_dir=tmp_path / "missing")
    client = TestClient(create_app(report_owner=lambda: owner))

    listed = client.get("/api/report-workspaces/jira")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["state"] == "ready"
    assert payload["reports"][0]["title"] == "Jira format audit"
    assert payload["reports"][0]["status"] == "attention"

    report_id = payload["reports"][0]["id"]
    detail = client.get(f"/api/report-workspaces/jira/{report_id}")
    assert detail.status_code == 200
    assert detail.json()["sections"][0]["rows"][0] == ["问题总数", 3]
    assert detail.json()["summary"]["total"] == 3

    download = client.get(f"/api/report-workspaces/jira/{report_id}/download")
    assert download.status_code == 200
    assert download.content == report.read_bytes()
    assert "attachment" in download.headers["content-disposition"]


def test_confluence_project_facts_expose_dynamic_facets_and_filter_local_snapshot():
    snapshot = {
        "schema_version": 1, "updated_at": "2026-08-26T12:00:00+00:00",
        "field_discrepancies": ["Unexpected Owner"],
        "projects": [{
            "identity": "DOPL:A", "project_id": "A", "name": "Apollo", "space_key": "DOPL", "active": True,
            "status": "stale", "fields": {"support mode": "B", "unexpected owner": "Alice"},
            "raw_headers": ["Support Mode", "Unexpected Owner"],
            "roles": {"FAE QA": [{"name": "Coco", "identity": "u-1"}]},
        }],
    }
    client = TestClient(create_app(project_facts_owner=lambda: ProjectFactsWebOwner(lambda: snapshot)))
    response = client.get("/api/confluence/project-facts", params={"field.unexpected owner": "Alice", "search": "u-1"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "partial_success"
    assert payload["counts"] == {"stale": 1, "failed": 0, "inactive": 0}
    assert payload["projects"][0]["project_id"] == "A"
    assert {facet["label"] for facet in payload["facets"]} >= {"Support Mode", "Unexpected Owner"}
    product_space = next(facet for facet in payload["facets"] if facet["label"] == "Product Space")
    assert product_space["options"] == [{"value": "DOPL", "label": "China Operator Business"}]
    assert payload["discrepancies"] == ["Unexpected Owner"]


def test_confluence_facets_keep_full_structure_and_cascade_options_when_filtered():
    snapshot = {"schema_version": 1, "projects": [
        {"project_id": "A", "name": "A", "space_key": "DOPL", "active": True, "status": "current",
         "fields": {"launch os": "Android"}, "raw_headers": ["Launch OS"], "roles": {}},
        {"project_id": "B", "name": "B", "space_key": "SDPL", "active": True, "status": "current",
         "fields": {"next target": "MP"}, "raw_headers": ["Next Target"], "roles": {}},
    ]}
    client = TestClient(create_app(project_facts_owner=lambda: ProjectFactsWebOwner(lambda: snapshot)))
    payload = client.get("/api/confluence/project-facts", params={"field.__product_space__": "DOPL"}).json()
    assert [row["project_id"] for row in payload["projects"]] == ["A"]
    facets = {row["label"]: row["options"] for row in payload["facets"]}
    assert facets["Product Space"] == [{"value": "DOPL", "label": "China Operator Business"}]
    assert facets["Launch OS"] == ["Android"]
    assert facets["Next Target"] == []
    assert facets["Major PM"] == []


def test_confluence_repeated_field_parameters_are_or_values():
    snapshot = {"schema_version": 1, "projects": [
        {"project_id": "A", "name": "A", "space_key": "DOPL", "active": True,
         "status": "current", "fields": {"support mode": "A"}, "roles": {}},
        {"project_id": "B", "name": "B", "space_key": "DOPL", "active": True,
         "status": "current", "fields": {"support mode": "B"}, "roles": {}},
    ]}
    client = TestClient(create_app(project_facts_owner=lambda: ProjectFactsWebOwner(lambda: snapshot)))
    response = client.get("/api/confluence/project-facts?field.support%20mode=A&field.support%20mode=B")
    assert [row["project_id"] for row in response.json()["projects"]] == ["A", "B"]


def test_confluence_request_logs_safe_filter_and_response_summaries(monkeypatch):
    import smarttest_web.app as app_module
    records = []
    monkeypatch.setattr(app_module, "smart_log",
                        lambda message, **kwargs: records.append((message, kwargs)))
    snapshot = {"schema_version": 1, "updated_at": "2026-08-26T12:00:00Z", "projects": [{
        "project_id": "SECRET-PROJECT", "name": "Secret", "space_key": "DOPL", "active": True,
        "status": "current", "fields": {"support mode": "A"},
        "roles": {"FAE QA": [{"name": "Private Person", "identity": "uid-secret"}]},
    }]}
    client = TestClient(app_module.create_app(project_facts_owner=lambda: ProjectFactsWebOwner(lambda: snapshot)))
    response = client.get("/api/confluence/project-facts?field.support%20mode=A&field.project%20owner=Private%20Person&field.project%20id=SECRET-PROJECT&field.dynamic%20identity=uid-secret&search=Private%20Person")
    assert response.status_code == 200
    business = [(message, kwargs) for message, kwargs in records
                if kwargs.get("source") == "confluence_project_facts"]
    assert [message for message, _kwargs in business] == [
        "Confluence project facts request received",
        "Confluence project facts response ready",
    ]
    assert business[0][1]["extra"] == {"filters": {
        "support mode": {"values": ["A"], "selected_count": 1},
        "project owner": {"selected_count": 1},
        "project id": {"selected_count": 1},
        "dynamic identity": {"selected_count": 1},
    }, "search_enabled": True}
    assert "Private Person" not in str(business) and "SECRET-PROJECT" not in str(business)
    assert sum(kwargs.get("source") == "request" for _message, kwargs in records) == 1


def test_confluence_project_facts_expose_missing_and_schema_states():
    missing = TestClient(create_app(project_facts_owner=lambda: ProjectFactsWebOwner(lambda: None)))
    missing_payload = missing.get("/api/confluence/project-facts").json()
    assert missing_payload["state"] == "no_snapshot"
    assert [facet["label"] for facet in missing_payload["facets"]] == [
        "Product Space", "Page", "Date of Commercial approval", "Project ID", "ODM",
        "OEM/Operator", "Key Part Number", "Project Status", "Current Stage",
        "Major PM", "Project Owner", "Support Mode", "Launch OS", "Date of Kick Off",
        "planned closure", "actual closure", "MP Time",
        "Launch Time", "Next Target", "Next Target Date", "Sum",
    ]
    assert all(facet["options"] == [] for facet in missing_payload["facets"])

    class Broken:
        def load(self):
            from core.tools.common.project_weekly_audit import ProjectFactsSchemaError
            raise ProjectFactsSchemaError("bad")

    broken = TestClient(create_app(project_facts_owner=lambda: ProjectFactsWebOwner(Broken().load)))
    broken_payload = broken.get("/api/confluence/project-facts").json()
    assert broken_payload["state"] == "schema_error"
    assert [facet["label"] for facet in broken_payload["facets"]] == [
        facet["label"] for facet in missing_payload["facets"]
    ]


def test_report_workspace_exposes_empty_config_failure_and_partial_states(tmp_path):
    empty_owner = ClientAuditReportOwner(jira_dir=tmp_path, confluence_dir=None)
    client = TestClient(create_app(report_owner=lambda: empty_owner))
    assert client.get("/api/report-workspaces/jira").json()["state"] == "empty"
    assert client.get("/api/report-workspaces/confluence").status_code == 404

    good = tmp_path / "jira_format_audit_20260826_143000.xlsx"
    _workbook(good, [["指标", "值"], ["问题总数", 1]])
    (tmp_path / "jira_format_audit_20260825_143000.xlsx").write_bytes(b"not an xlsx")
    payload = client.get("/api/report-workspaces/jira").json()
    assert payload["state"] == "partial_success"
    assert len(payload["reports"]) == 1
    assert payload["failures"] == 1


def test_unknown_source_and_report_id_are_not_exposed(tmp_path):
    owner = ClientAuditReportOwner(jira_dir=tmp_path, confluence_dir=tmp_path)
    client = TestClient(create_app(report_owner=lambda: owner))
    assert client.get("/api/report-workspaces/redmine").status_code == 404
    assert client.get("/api/report-workspaces/jira/not-a-report").status_code == 404


def test_jira_generated_reports_are_filtered_by_exported_jql(tmp_path):
    _workbook(tmp_path / "jira_format_audit_20260826_143000.xlsx", [
        ["指标", "值"], ["JQL 查询条件", "project = TV AND issuetype = Bug"], ["问题总数", 1],
    ])
    owner = ClientAuditReportOwner(jira_dir=tmp_path, confluence_dir=tmp_path / "missing")
    client = TestClient(create_app(report_owner=lambda: owner))
    match = client.get("/api/report-workspaces/jira", params={"jql": "project = TV AND issuetype = Bug"}).json()
    assert match["state"] == "ready"
    assert match["reports"][0]["jql"] == "project = TV AND issuetype = Bug"
    missing = client.get("/api/report-workspaces/jira", params={"jql": "project = OTT"}).json()
    assert missing["state"] == "empty"


def test_report_access_denial_is_an_explicit_safe_state():
    class DeniedOwner:
        def list_reports(self, source, filters):
            raise PermissionError("private personnel scope")

    response = TestClient(create_app(report_owner=lambda: DeniedOwner())).get("/api/report-workspaces/jira")
    assert response.status_code == 403
    assert response.json() == {"detail": {"state": "unauthorized"}}
    assert "personnel" not in response.text
