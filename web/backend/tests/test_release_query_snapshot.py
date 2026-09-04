from __future__ import annotations

from smarttest_web.database import WebDatabase
from smarttest_web.release_snapshot_repository import ReleaseQuerySnapshotRepository


def test_release_snapshot_survives_restart_with_both_source_versions(tmp_path):
    database = WebDatabase(tmp_path / "web.db")
    first = ReleaseQuerySnapshotRepository(database, now=lambda: 100.0)
    first.record(
        "session-1", "release-dashboard", {"status": ["WARNING"]}, "risk",
        ("P100", "P200"), ("Android 16", "Android 15"), "c-v2", "j-v4", expires_at=500,
    )

    restored = ReleaseQuerySnapshotRepository(database, now=lambda: 110.0).get(
        "session-1", "release-dashboard",
    )

    assert restored.project_ids == ("P100", "P200")
    assert restored.release_names == ("Android 16", "Android 15")
    assert restored.confluence_facts_version == "c-v2"
    assert restored.jira_cache_version == "j-v4"


def test_jira_drilldown_reads_dashboard_scope_without_accepting_new_project_ids(tmp_path):
    database = WebDatabase(tmp_path / "web.db")
    repository = ReleaseQuerySnapshotRepository(database, now=lambda: 100.0)
    repository.record(
        "session-1", "release-dashboard", {}, "", ("P100",), ("Android 16",),
        "c-v1", "j-v1", expires_at=500,
    )

    selection = repository.get("session-1", "release-dashboard")

    assert selection.project_ids == ("P100",)
    assert "FORGED" not in selection.project_ids


def test_snapshot_preserves_project_to_release_position_when_release_names_repeat(tmp_path):
    database = WebDatabase(tmp_path / "web.db")
    repository = ReleaseQuerySnapshotRepository(database, now=lambda: 100.0)
    repository.record(
        "session-1", "release-dashboard", {}, "", ("P100", "P200"),
        ("Android 16", "Android 16"), "c-v1", "j-v1", expires_at=500,
    )

    restored = repository.get("session-1", "release-dashboard")

    assert tuple(zip(restored.project_ids, restored.release_names)) == (
        ("P100", "Android 16"), ("P200", "Android 16"),
    )
