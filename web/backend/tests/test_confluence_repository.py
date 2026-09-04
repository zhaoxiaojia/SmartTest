from __future__ import annotations

from dataclasses import replace
import sqlite3

import pytest

from core.confluence.project import (
    ConfluencePageRef,
    ProductSpaceRef,
    Project,
    ProjectDetails,
    ProjectIdentity,
    ProjectMilestones,
    ProjectQuery,
    ProjectRole,
    SourceEvidence,
)
from core.domain.detail import DetailSection, DetailState
from core.domain.values import FieldBag, NamedValue, PersonRef, SourceRevision
from core.confluence.models import ConfluencePage
from core.confluence.project_catalog import refresh_project_catalogs
from core.confluence.project_discovery import ProductLine
from core.confluence.project_mapper import ConfluenceProjectMapper
from smarttest_web.release_query import ProjectReleaseQueryService
from smarttest_web.confluence.project_repository import ConfluenceProjectRepository
from smarttest_web.database import WebDatabase
from smarttest_web.schema import initialize_current_cache_schema


def _project(revision: str = "4") -> Project:
    return Project(
        ProjectIdentity("900", "P100"), "Project One",
        ProductSpaceRef("DOPL", "DOPL", "https://confluence/spaces/DOPL"),
        ConfluencePageRef("10", "Catalog", "https://confluence/pages/10", 4),
        NamedValue("normal", "Normal"), NamedValue("evt", "EVT"),
        NamedValue("onsite", "Onsite"), "Customer A",
        (PersonRef("u1", "alice", "Alice"),), SourceRevision(revision),
    )


def _repository(tmp_path) -> ConfluenceProjectRepository:
    database = WebDatabase(tmp_path / "web.db")
    initialize_current_cache_schema(database)
    return ConfluenceProjectRepository(database)


def test_project_core_and_all_detail_states_round_trip_without_field_loss(tmp_path) -> None:
    repository = _repository(tmp_path)
    project = _project()
    roles = (ProjectRole(NamedValue("fae", "FAE QA"), (PersonRef("u2", "bob", "Bob"),)),)
    evidence = (SourceEvidence("basic", ConfluencePageRef("11", "Basic", "https://confluence/pages/11", 7)),)

    repository.save_core((project,))
    repository.replace_roles("P100", DetailSection.loaded(roles, source_revision="4"))
    repository.replace_milestones("P100", DetailSection.stale(ProjectMilestones((("SOP", "2026-10"),)), source_revision="3"))
    repository.replace_hardware("P100", DetailSection.failed("remote_unavailable", value=FieldBag.from_mapping({"board": "A"}), source_revision="3"))
    repository.replace_software("P100", DetailSection())
    repository.replace_facts("P100", DetailSection.loaded(FieldBag.from_mapping({"region": ["US", "EU"]}), source_revision="4"))
    repository.replace_evidence("P100", DetailSection.loaded(evidence, source_revision="4"))

    loaded = repository.get("P100", ProjectDetails(True, True, True, True, True, True))

    assert replace(loaded, roles=DetailSection(), milestones=DetailSection(), hardware=DetailSection(), software=DetailSection(), facts=DetailSection(), evidence=DetailSection()) == project
    assert loaded.roles == DetailSection.loaded(roles, source_revision="4")
    assert loaded.milestones == DetailSection.stale(ProjectMilestones((("SOP", "2026-10"),)), source_revision="3")
    assert loaded.hardware == DetailSection.failed("remote_unavailable", value=FieldBag.from_mapping({"board": "A"}), source_revision="3")
    assert loaded.software.state is DetailState.UNLOADED
    assert loaded.facts == DetailSection.loaded(FieldBag.from_mapping({"region": ["US", "EU"]}), source_revision="4")
    assert loaded.evidence == DetailSection.loaded(evidence, source_revision="4")


def test_catalog_transaction_preserves_duplicate_owner_and_cross_space_project_id(tmp_path) -> None:
    repository = _repository(tmp_path)
    duplicate_owner = PersonRef("u1", "alice", "Alice")
    first = replace(
        _project(),
        identity=ProjectIdentity("DOPL:P100", "P100"),
        owner_summary=(duplicate_owner, duplicate_owner),
    )
    second = replace(
        _project(),
        identity=ProjectIdentity("TV:P100", "P100"),
        product_space=ProductSpaceRef("TV", "TV Business"),
        owner_summary=(),
    )

    repository.save_core((first, second))

    stored = repository.list(ProjectQuery(), 0, 10)
    assert [(project.identity.confluence_id, project.identity.project_id) for project in stored.projects] == [
        ("DOPL:P100", "P100"), ("TV:P100", "P100"),
    ]
    assert repository.get("DOPL:P100", ProjectDetails()).owner_summary == (duplicate_owner,)
    assert repository.get("TV:P100", ProjectDetails()).product_space.key == "TV"


def test_project_detail_replace_failure_rolls_back_value_and_state(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.save_core((_project(),))
    original = DetailSection.loaded(FieldBag.from_mapping({"kept": "yes"}), source_revision="4")
    repository.replace_facts("P100", original)

    with pytest.raises(TypeError):
        repository.replace_facts(
            "P100", DetailSection.loaded(FieldBag.from_mapping({"bad": {1}}), source_revision="5")
        )

    assert repository.get("P100", ProjectDetails(facts=True)).facts == original


def test_current_release_projection_tracks_only_named_confluence_fields(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.save_core((_project(),))

    repository.replace_facts("P100", DetailSection.loaded(FieldBag.from_mapping({
        "Launch OS": "Android 16", "Launch Time": "2026-11-02", "MP Time": "2026-10-18",
        "Next Target": "DVT exit", "Next Target Date": "2026-09-20",
        "Current HW Stage": "DVT2", "Status Summary": "On track",
        "planned closure": "2099-01-01",
    }), source_revision="detail-r2"))

    with repository.database.connect() as connection:
        row = connection.execute("SELECT * FROM project_current_releases WHERE confluence_id='900'").fetchone()
    assert row[1:] == (
        "P100", "Android 16", "2026-11-02", "2026-10-18", "DVT exit", "2026-09-20",
        "DVT2", "On track", "detail-r2", row[-1],
    )


def test_failed_sections_round_trip_explicit_value_presence_without_revision(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.save_core((_project(),))
    repository.replace_hardware(
        "P100",
        DetailSection.failed(
            "remote_unavailable", value=FieldBag.from_mapping({"board": "old"}),
        ),
    )
    repository.replace_facts(
        "P100", DetailSection.failed("remote_unavailable", value=FieldBag()),
    )
    repository.replace_evidence(
        "P100", DetailSection.failed("remote_unavailable", value=()),
    )

    loaded = repository.get(
        "P100", ProjectDetails(hardware=True, facts=True, evidence=True),
    )

    assert loaded.hardware.value == FieldBag.from_mapping({"board": "old"})
    assert loaded.hardware.source_revision == ""
    assert loaded.facts.value == FieldBag()
    assert loaded.evidence.value == ()


def test_project_delete_cascades_details_and_clear_is_isolated_from_jira(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.save_core((_project(),))
    repository.replace_facts("P100", DetailSection.loaded(FieldBag.from_mapping({"x": 1})))
    with repository.database.transaction() as connection:
        connection.execute(
            "INSERT INTO jira_issues(issue_id,issue_key,summary,cached_at) VALUES('1','J-1','kept','now')"
        )

    repository.delete("P100")
    with repository.database.connect() as connection:
        assert connection.execute("SELECT count(*) FROM confluence_project_fields").fetchone()[0] == 0
    repository.save_core((_project(),))
    repository.clear()

    with sqlite3.connect(repository.database.path) as connection:
        assert connection.execute("SELECT count(*) FROM confluence_projects").fetchone()[0] == 0
        assert connection.execute("SELECT summary FROM jira_issues").fetchone()[0] == "kept"


def test_canonical_catalog_name_is_unchanged_through_sqlite_and_dashboard_query(tmp_path) -> None:
    page = ConfluencePage(
        "catalog", "Project Space", "https://c/display/DOPL/Project+Space",
        view_body=(
            "<table><tr><th>Page</th><th>Project ID</th><th>Launch OS</th><th>Launch Time</th></tr>"
            '<tr><td><a href="/pages/viewpage.action?pageId=900">★ 1. Apollo - Project Status Report</a></td>'
            "<td>P100</td><td>Android 16</td><td>2026-10-01</td></tr></table>"
        ),
    )
    store = type("Store", (), {"load": lambda self: None, "save": lambda self, value: setattr(self, "value", value)})()
    client = type("Client", (), {"get_page_by_url": lambda self, _url: page})()
    row = refresh_project_catalogs(
        client, store, (ProductLine("DOPL", page.url, "DOPL"),),
    )["projects"][0]
    repository = _repository(tmp_path)
    project = ConfluenceProjectMapper().from_catalog(row)

    repository.save_core((project,))
    repository.replace_facts(project.identity.confluence_id, project.facts)
    stored = repository.get("P100", ProjectDetails())
    dashboard = ProjectReleaseQueryService(repository.database).dashboard(visible_ids=("DOPL:P100",))

    assert stored.name == "Apollo"
    assert dashboard["releases"][0]["projectName"] == "Apollo"


def test_repository_initialization_upgrades_legacy_cached_names_once_without_touching_source_facts(tmp_path) -> None:
    database = WebDatabase(tmp_path / "web.db")
    initialize_current_cache_schema(database)
    dirty_title = "1.★ Apollo - Project Status Report"
    cached_at = "2026-09-01T01:02:03+00:00"
    with database.transaction() as connection:
        connection.executemany(
            """INSERT INTO confluence_projects VALUES(
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                (
                    "legacy", "P100", dirty_title, "DOPL", "DOPL", "https://c/DOPL",
                    "catalog-1", dirty_title, "https://c/pages/catalog-1", 7,
                    "normal", "Normal", "evt", "EVT", "onsite", "Onsite",
                    "Customer A", "catalog-r7", cached_at,
                ),
                (
                    "clean", "P200", "Orion", "TV", "TV", "https://c/TV",
                    "catalog-2", "2. Orion - Project Status Report", "https://c/pages/catalog-2", 4,
                    "normal", "Normal", "dvt", "DVT", "remote", "Remote",
                    "Customer B", "catalog-r4", cached_at,
                ),
            ),
        )
        connection.executemany(
            """INSERT INTO project_current_releases VALUES(
            ?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ("legacy", "P100", "Android 16", "2026-10-01", "", "", "", "", "", "facts-r1", cached_at),
                ("clean", "P200", "Android 17", "2026-11-01", "", "", "", "", "", "facts-r2", cached_at),
            ),
        )
        connection.execute(
            "INSERT INTO confluence_project_fields VALUES(?,?,?,?)",
            ("legacy", "facts", "Page", f'{{"title": "{dirty_title}"}}'),
        )
        connection.execute(
            "INSERT INTO confluence_project_evidence VALUES(?,?,?,?,?,?)",
            ("legacy", "status", "status-1", dirty_title, "https://c/pages/status-1", 9),
        )

    ConfluenceProjectRepository(database)
    with database.connect() as connection:
        first = tuple(connection.execute(
            """SELECT confluence_id,name,catalog_page_title,source_revision,cached_at
            FROM confluence_projects ORDER BY confluence_id""",
        ))
        raw_field = connection.execute(
            "SELECT value_json FROM confluence_project_fields WHERE confluence_id='legacy'",
        ).fetchone()[0]
        evidence = connection.execute(
            """SELECT page_title,page_url,page_version FROM confluence_project_evidence
            WHERE confluence_id='legacy'""",
        ).fetchone()

    ConfluenceProjectRepository(database)
    with database.connect() as connection:
        second = tuple(connection.execute(
            """SELECT confluence_id,name,catalog_page_title,source_revision,cached_at
            FROM confluence_projects ORDER BY confluence_id""",
        ))
    dashboard = ProjectReleaseQueryService(database).dashboard(visible_ids=("legacy", "clean"))

    assert first == second == (
        ("clean", "Orion", "2. Orion - Project Status Report", "catalog-r4", cached_at),
        ("legacy", "Apollo", dirty_title, "catalog-r7", cached_at),
    )
    assert raw_field == f'{{"title": "{dirty_title}"}}'
    assert evidence == (dirty_title, "https://c/pages/status-1", 9)
    assert [row["projectName"] for row in dashboard["releases"]] == ["Apollo", "Orion"]
