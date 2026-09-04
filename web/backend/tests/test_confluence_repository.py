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
