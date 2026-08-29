import sqlite3
import pytest

from smarttest_web.confluence_repository import ConfluenceCurrentStateRepository


def _snapshot(project_id="page-1", owner="Alice", version=2):
    return {"schema_version": 1, "updated_at": "2026-08-28T00:00:00Z", "phase": "ready",
            "projects": [{"identity": f"DOPL:{project_id}", "page_id": project_id,
                          "project_id": "P1", "name": "Project One", "space_key": "DOPL",
                          "page_url": "https://c/pages/1", "active": True, "status": "current",
                          "fields": {"current stage": "Stage 3", "new field": "Dynamic"},
                          "raw_fields": {"Current Stage": "Stage 3", "New Field": "Dynamic"},
                          "raw_headers": ["Current Stage", "New Field"],
                          "roles": {"FAE QA": [{"identity": "u1", "name": owner}]},
                          "catalog_source": {"page_id": "catalog", "version": version},
                          "detail_source": {"page_id": "basic", "version": version}}]}


def test_repository_shares_current_project_data_but_isolates_account_visibility(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    repository.import_legacy_snapshot("coco", _snapshot())
    repository.import_legacy_snapshot("atlas", {**_snapshot(), "projects": []})

    assert repository.load_account_snapshot("coco")["projects"][0]["fields"]["new field"] == "Dynamic"
    assert repository.load_account_snapshot("atlas")["projects"] == []
    with sqlite3.connect(tmp_path / "web.db") as connection:
        assert connection.execute("select count(*) from confluence_projects").fetchone()[0] == 1
        assert connection.execute("select count(*) from confluence_project_attributes").fetchone()[0] == 2
        assert connection.execute("select count(*) from confluence_project_people").fetchone()[0] == 1


def test_account_catalog_refresh_preserves_shared_detail_and_replaces_only_its_visibility(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    repository.import_legacy_snapshot("coco", _snapshot(owner="Alice", version=2))
    catalog = _snapshot(owner="", version=3)
    project = catalog["projects"][0]
    project.update(status="catalog_ready", detail_source=None, roles={})
    project["fields"] = {"current stage": "Stage 4"}

    revision = repository.account_store("atlas").save(catalog)

    coco = repository.load_account_snapshot("coco")["projects"][0]
    atlas = repository.load_account_snapshot("atlas")
    assert revision == atlas["revision"]
    assert [row["page_id"] for row in atlas["projects"]] == ["page-1"]
    assert coco["roles"] == {"FAE QA": [{"identity": "u1", "name": "Alice"}]}
    assert coco["detail_source"]["version"] == 2
    assert coco["fields"]["new field"] == "Dynamic"
    assert coco["fields"]["current stage"] == "Stage 4"


def test_failed_project_update_keeps_last_successful_current_state(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    repository.import_legacy_snapshot("coco", _snapshot(owner="Alice"))
    failed = _snapshot(owner="", version=3)
    failed["projects"][0].update(status="failed", error={"type": "TimeoutError", "message": "offline"})

    repository.import_legacy_snapshot("coco", failed)

    project = repository.load_account_snapshot("coco")["projects"][0]
    assert project["roles"]["FAE QA"][0]["name"] == "Alice"
    assert project["status"] == "stale"


def test_visibility_replacement_is_atomic_and_increments_revision(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    first = repository.import_legacy_snapshot("coco", _snapshot("page-1"))
    second = repository.import_legacy_snapshot("coco", _snapshot("page-2"))

    assert second == first + 1
    loaded = repository.load_account_snapshot("coco")
    assert [row["page_id"] for row in loaded["projects"]] == ["page-2"]
    assert loaded["revision"] == second


def test_single_project_upsert_replaces_complete_state_without_changing_visibility(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    repository.import_legacy_snapshot("coco", _snapshot(owner="Alice", version=2))
    project = _snapshot(owner="Bob", version=3)["projects"][0]
    project["fields"] = {"replacement": "yes"}
    project["raw_fields"] = {"Replacement": "yes"}
    project["raw_headers"] = ["Replacement"]

    repository.upsert_project(project)

    loaded = repository.load_account_snapshot("coco")["projects"][0]
    assert loaded["fields"] == {"replacement": "yes"}
    assert loaded["roles"] == {"FAE QA": [{"identity": "u1", "name": "Bob"}]}
    assert loaded["detail_source"]["version"] == 3
    with sqlite3.connect(tmp_path / "web.db") as connection:
        assert connection.execute("SELECT account_id,project_page_id FROM confluence_account_project_access").fetchall() == [("coco", "page-1")]
        assert connection.execute("SELECT account_id FROM confluence_sync_state ORDER BY account_id").fetchall() == [("coco",)]


def test_single_project_upsert_rolls_back_every_table_on_error(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    repository.import_legacy_snapshot("coco", _snapshot(owner="Alice", version=2))
    broken = _snapshot(owner="Bob", version=3)["projects"][0]
    broken["unserializable"] = {"not-json"}

    with pytest.raises(TypeError):
        repository.upsert_project(broken)

    loaded = repository.load_account_snapshot("coco")["projects"][0]
    assert loaded["fields"]["new field"] == "Dynamic"
    assert loaded["roles"]["FAE QA"][0]["name"] == "Alice"
    assert loaded["detail_source"]["version"] == 2
