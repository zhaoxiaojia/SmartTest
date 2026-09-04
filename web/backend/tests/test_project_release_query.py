from __future__ import annotations

from datetime import date

from smarttest_web.database import WebDatabase
from smarttest_web.release_query import ProjectReleaseQueryService


def _service(tmp_path):
    database = WebDatabase(tmp_path / "web.db")
    service = ProjectReleaseQueryService(database, today=lambda: date(2026, 9, 4))
    with database.transaction() as connection:
        connection.executemany(
            """INSERT INTO confluence_projects
            (confluence_id,project_id,name,product_space_key,status_name,stage_name,
             catalog_page_url,source_revision,cached_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                ("c1", "AN16", "Orion", "DOPL", "NORMAL", "EVT", "https://wiki/orion", "c-r1", "2026-09-01"),
                ("c2", "P200", "Nebula AN16", "TV", "NORMAL", "DVT", "https://wiki/nebula", "c-r1", "2026-09-01"),
                ("c3", "P300", "Atlas", "SDPL", "BLOCK", "MP", "https://wiki/atlas", "c-r1", "2026-09-01"),
            ),
        )
        connection.executemany(
            "INSERT INTO confluence_project_owners(confluence_id,identity,account,display_name) VALUES(?,?,?,?)",
            (("c1", "u1", "alice", "Alice"), ("c2", "u2", "eve", "Eve")),
        )
        connection.executemany(
            "INSERT INTO confluence_project_roles(confluence_id,role_id,role_name) VALUES(?,?,?)",
            (("c1", "role.major_fae_qa", "Major FAE QA"),
             ("c2", "role.major_fae_qa", "Major FAE QA")),
        )
        connection.executemany(
            "INSERT INTO confluence_project_role_people(confluence_id,role_id,identity,account,display_name) VALUES(?,?,?,?,?)",
            (("c1", "role.major_fae_qa", "q1", "bob", "Bob"),
             ("c2", "role.major_fae_qa", "q2", "mallory", "Mallory")),
        )
        connection.executemany(
            """INSERT INTO project_current_releases
            (confluence_id,project_id,release_name,launch_time,next_target,next_target_date,
             current_hw_stage,status_summary,source_revision,cached_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                ("c1", "AN16", "Android 16", "2026-09-30", "Close P1", "2026-09-20", "EVT2", "On track", "c-r1", "2026-09-01"),
                ("c2", "P200", "Android 15", "2026-10-20", "DVT exit", "2026-09-25", "DVT1", "On track", "c-r1", "2026-09-01"),
                ("c3", "P300", "Android 16", "2026-08-31", "MP", "2026-08-30", "MP", "Blocked", "c-r1", "2026-09-01"),
            ),
        )
        connection.executemany(
            """INSERT INTO jira_issues
            (issue_id,issue_key,summary,status_id,status_name,issue_type_id,issue_type_name,
             priority_id,priority_name,updated_at,source_revision,cached_at,resolution_id,resolution_name)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ("i1", "SH-1", "Exact release", "1", "Open", "1", "Bug", "1", "P1", "2026-09-03", "j-r1", "2026-09-03", None, None),
                ("i2", "SH-2", "Missing release", "1", "Open", "1", "Bug", "0", "P0", "2026-09-04", "j-r1", "2026-09-04", None, None),
                ("i3", "SH-3", "AN16 appears only in title", "1", "Open", "1", "Bug", "1", "P1", "2026-09-04", "j-r1", "2026-09-04", None, None),
                ("i4", "SH-4", "Resolved blocker", "5", "Done", "1", "Bug", "0", "P0", "2026-09-02", "j-r1", "2026-09-02", "1", "Fixed"),
            ),
        )
        connection.executemany(
            """INSERT INTO jira_issue_release_facts
            (issue_id,project_business_id,software_release,severity,compare_status,qa_assignee_identity,manager_identity)
            VALUES(?,?,?,?,?,?,?)""",
            (
                ("i1", " an16 ", "ANDROID   16", "Major", "", "qa1", "m1"),
                ("i2", "AN16", "", "Critical", "", "qa1", "m1"),
                ("i3", "P200", "", "Major", "", "qa2", "m2"),
                ("i4", "P300", "Android 16", "Critical", "", "qa3", "m3"),
            ),
        )
        connection.executemany(
            "INSERT INTO jira_release_field_metadata(field_name,field_key,cached_at) VALUES(?,?,?)",
            tuple((name, f"field-{index}", "2026-09-04") for index, name in enumerate((
                "Project ID", "Software Release", "Severity", "Compare Status", "QA Assignee", "Manager",
            ))),
        )
    return service


def test_dashboard_uses_only_exact_project_id_and_keeps_version_pending_issues(tmp_path):
    result = _service(tmp_path).dashboard(visible_ids=("c1", "c2"))

    rows = {row["projectId"]: row for row in result["releases"]}
    assert rows["AN16"]["issueCounts"] == {
        "open": 2, "p0": 1, "p1": 1, "exact": 1, "versionPending": 1,
    }
    assert rows["P200"]["issueCounts"]["versionPending"] == 1
    assert rows["P200"]["issueCounts"]["open"] == 1
    assert rows["P200"]["health"]["state"] == "WARNING"
    assert any("版本待确认" in reason for reason in rows["P200"]["health"]["reasons"])


def test_health_priority_is_block_then_warning_then_incomplete_then_normal(tmp_path):
    result = _service(tmp_path).dashboard(visible_ids=("c1", "c2", "c3"))
    rows = {row["projectId"]: row for row in result["releases"]}

    assert rows["AN16"]["health"]["state"] == "BLOCK"
    assert any("P0" in reason for reason in rows["AN16"]["health"]["reasons"])
    assert rows["P300"]["health"]["state"] == "BLOCK"
    assert rows["P300"]["issueCounts"]["p0"] == 0


def test_issue_workbench_drilldown_matches_dashboard_scope_and_sorts_priority_then_updated(tmp_path):
    service = _service(tmp_path)
    dashboard = service.dashboard(visible_ids=("c1",), project_ids=("AN16",))
    issues = service.issues(visible_ids=("c1",), project_ids=("AN16",), page=0, page_size=20)

    assert dashboard["releases"][0]["issueCounts"]["open"] == issues["pagination"]["total"]
    assert [row["key"] for row in issues["issues"]] == ["SH-2", "SH-1"]
    assert issues["counts"] == {"exact": 1, "versionPending": 1}
    assert issues["sourceFreshness"]["jira"] == "2026-09-04"


def test_missing_required_release_data_is_explicit_not_substituted(tmp_path):
    service = _service(tmp_path)
    with service.database.transaction() as connection:
        connection.execute("UPDATE project_current_releases SET release_name='',launch_time='' WHERE confluence_id='c2'")

    row = service.dashboard(visible_ids=("c2",))["releases"][0]

    assert row["releaseName"] == "版本未填写"
    assert row["launchTime"] == ""
    assert row["health"]["state"] == "WARNING"
    assert any("版本名缺失" in reason for reason in row["health"]["reasons"])


def test_dashboard_and_jira_project_filters_apply_inside_authorized_sqlite_scope(tmp_path):
    service = _service(tmp_path)

    dashboard = service.dashboard(visible_ids=("c1", "c2"), filters={"owner": ["Alice"], "qa": ["Bob"]})
    issues = service.issues(visible_ids=("c1", "c2"), filters={"project": ["AN16"]})

    assert [row["projectId"] for row in dashboard["releases"]] == ["AN16"]
    assert {row["projectId"] for row in issues["issues"]} == {"AN16"}


def test_component_filter_matches_each_structured_component_member(tmp_path):
    service = _service(tmp_path)
    with service.database.transaction() as connection:
        connection.executemany(
            "INSERT INTO jira_issue_components(issue_id,component_id,component_name) VALUES(?,?,?)",
            (("i1", "c1", "Video"), ("i1", "c2", "Audio"), ("i2", "c3", "Camera")),
        )

    result = service.issues(
        visible_ids=("c1",), project_ids=("AN16",), filters={"component": ["Audio"]},
    )

    assert [row["key"] for row in result["issues"]] == ["SH-1"]
    assert next(facet for facet in result["facets"] if facet["key"] == "component")["options"] == [
        "Audio", "Video",
    ]


def test_fix_version_with_comma_matches_as_one_structured_version_name(tmp_path):
    service = _service(tmp_path)
    with service.database.transaction() as connection:
        connection.execute(
            "UPDATE project_current_releases SET release_name=? WHERE confluence_id='c1'",
            ("Android 16, EVT",),
        )
        connection.execute(
            "UPDATE jira_issue_release_facts SET software_release=? WHERE issue_id='i1'",
            ("Other release",),
        )
        connection.executemany(
            """INSERT INTO jira_issue_fix_versions
            (issue_id,version_id,version_name,released,release_date) VALUES(?,?,?,?,?)""",
            (("i1", "v1", "Android 16, EVT", 0, ""), ("i1", "v2", "Android 15", 0, "")),
        )

    result = service.issues(
        visible_ids=("c1",), project_ids=("AN16",), filters={"fixVersion": ["Android 16, EVT"]},
    )

    assert [row["key"] for row in result["issues"]] == ["SH-1"]
    assert result["issues"][0]["releaseAssociation"] == "exact"


def test_data_incomplete_summary_is_independent_of_higher_priority_health_state(tmp_path):
    service = _service(tmp_path)
    with service.database.transaction() as connection:
        connection.execute(
            "UPDATE project_current_releases SET launch_time='' WHERE confluence_id='c3'",
        )

    result = service.dashboard(visible_ids=("c1", "c2", "c3"))
    blocked = next(row for row in result["releases"] if row["projectId"] == "P300")

    assert blocked["health"]["state"] == "BLOCK"
    assert result["summary"]["dataIncomplete"] == 1


def test_dashboard_drilldown_scope_keeps_open_count_and_snapshotted_current_release(tmp_path):
    service = _service(tmp_path)
    with service.database.transaction() as connection:
        connection.execute(
            """INSERT INTO jira_issues
            (issue_id,issue_key,summary,status_id,status_name,issue_type_id,issue_type_name,
             priority_id,priority_name,updated_at,source_revision,cached_at,resolution_id,resolution_name)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("i5", "SH-5", "Resolved same release", "5", "Done", "1", "Bug", "1", "P1",
             "2026-09-04", "j-r1", "2026-09-04", "1", "Fixed"),
        )
        connection.execute(
            """INSERT INTO jira_issue_release_facts
            (issue_id,project_business_id,software_release,severity,compare_status,
             qa_assignee_identity,manager_identity) VALUES(?,?,?,?,?,?,?)""",
            ("i5", "AN16", "Android 16", "Major", "", "qa1", "m1"),
        )

    dashboard = service.dashboard(visible_ids=("c1",), project_ids=("AN16",))
    issues = service.issues(
        visible_ids=("c1",), project_ids=("AN16",),
        filters={"_scopeRelease": ["Android 16"], "_openOnly": True},
    )

    assert dashboard["releases"][0]["issueCounts"]["open"] == issues["pagination"]["total"] == 2
    assert service.issue_detail(
        "SH-5", visible_ids=("c1",), project_ids=("AN16",),
        filters={"_scopeRelease": ["Android 16"], "_openOnly": True},
    ) is None

    with service.database.transaction() as connection:
        connection.execute(
            "UPDATE project_current_releases SET release_name='Android 17' WHERE confluence_id='c1'",
        )

    stale = service.issues(
        visible_ids=("c1",), project_ids=("AN16",),
        filters={"_scopeRelease": ["Android 16"], "_openOnly": True},
    )
    assert stale["state"] == "no_snapshot"
    assert stale["pagination"]["total"] == 0
