from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from smarttest_web.confluence_repository import ConfluenceCurrentStateRepository
from smarttest_web.confluence_sync import ConfluenceProjectSyncCoordinator


def _project(page_id, version=1):
    return {"identity": f"DOPL:{page_id}", "page_id": page_id, "project_id": page_id,
            "name": page_id, "space_key": "DOPL", "page_url": f"https://c/{page_id}",
            "active": True, "status": "catalog_ready", "fields": {}, "raw_fields": {},
            "raw_headers": [], "roles": {},
            "catalog_source": {"page_id": "catalog", "version": 1},
            "detail_source": {"page_id": f"basic-{page_id}", "version": version}}


def test_sync_never_exceeds_configured_workers_and_commits_every_project(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    projects = [_project(f"p{index}", 0) for index in range(5)]
    repository.import_legacy_snapshot("coco", {"phase": "ready", "projects": projects})
    coordinator = ConfluenceProjectSyncCoordinator(repository, max_workers=2)
    release = Event(); two_active = Event(); lock = Lock()
    active = maximum = 0

    def fetch(project):
        nonlocal active, maximum
        with lock:
            active += 1; maximum = max(maximum, active)
            if active == 2: two_active.set()
        release.wait(2)
        with lock: active -= 1
        return {**project, "status": "current"}

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(coordinator.sync, projects, fetch)
        assert two_active.wait(1)
        assert maximum == 2
        release.set()
        assert future.result().count("updated") == 5
    assert len(repository.load_account_snapshot("coco")["projects"]) == 5


def test_two_accounts_share_one_inflight_fetch_without_changing_visibility(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    project = _project("shared", 0)
    repository.import_legacy_snapshot("coco", {"phase": "ready", "projects": [project]})
    repository.import_legacy_snapshot("atlas", {"phase": "ready", "projects": [project]})
    coordinator = ConfluenceProjectSyncCoordinator(repository, max_workers=2)
    initial_coco_revision = repository.load_account_snapshot("coco")["revision"]
    initial_atlas_revision = repository.load_account_snapshot("atlas")["revision"]
    commits = 0
    real_upsert = repository.upsert_project

    def counted_upsert(row):
        nonlocal commits
        commits += 1
        return real_upsert(row)

    repository.upsert_project = counted_upsert
    entered = Event(); release = Event(); lock = Lock(); calls = 0

    def fetch(row):
        nonlocal calls
        with lock: calls += 1
        entered.set(); release.wait(2)
        return {**row, "status": "current"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(coordinator.sync, [project], fetch)
        assert entered.wait(1)
        second = pool.submit(coordinator.sync, [project], fetch)
        release.set()
        assert first.result() == ["updated"]
        assert second.result() == ["updated"]
    assert calls == 1
    assert commits == 1
    assert repository.load_account_snapshot("coco")["revision"] == initial_coco_revision + 1
    assert repository.load_account_snapshot("atlas")["revision"] == initial_atlas_revision + 1
    assert [row["page_id"] for row in repository.load_account_snapshot("coco")["projects"]] == ["shared"]
    assert [row["page_id"] for row in repository.load_account_snapshot("atlas")["projects"]] == ["shared"]


def test_equal_stored_version_skips_detail_fetch(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    project = _project("same", 4)
    repository.import_legacy_snapshot("coco", {"phase": "ready", "projects": [project]})
    fetch_calls = []

    result = ConfluenceProjectSyncCoordinator(repository).sync(
        [project], lambda row: fetch_calls.append(row) or row,
    )

    assert result == ["skipped"]
    assert fetch_calls == []


def test_newer_version_fetches_once_and_atomically_replaces_complete_project(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    old = _project("newer", 2); old["fields"] = {"old": "value"}
    repository.import_legacy_snapshot("coco", {"phase": "ready", "projects": [old]})
    incoming = _project("newer", 3); calls = []

    def fetch(row):
        calls.append(row)
        updated = {**row, "status": "current", "fields": {"new": "value"},
                   "raw_fields": {"New": "value"}, "raw_headers": ["New"],
                   "roles": {"FAE QA": [{"identity": "u2", "name": "Bob"}]}}
        return updated

    assert ConfluenceProjectSyncCoordinator(repository).sync([incoming], fetch) == ["updated"]
    loaded = repository.load_account_snapshot("coco")["projects"][0]
    assert len(calls) == 1
    assert loaded["fields"] == {"new": "value"}
    assert loaded["roles"]["FAE QA"] == [{"identity": "u2", "name": "Bob"}]
    assert loaded["detail_source"]["version"] == 3


def test_scoped_sync_advances_visible_revision_without_dropping_unmatched_projects(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    matched, unmatched = _project("matched", 1), _project("unmatched", 1)
    initial_revision = repository.import_legacy_snapshot(
        "coco", {"phase": "ready", "projects": [matched, unmatched]},
    )
    incoming = _project("matched", 2)

    result = ConfluenceProjectSyncCoordinator(repository).sync(
        [incoming], lambda row: {**row, "status": "current", "fields": {"fresh": "yes"}},
    )

    snapshot = repository.load_account_snapshot("coco")
    assert result == ["updated"]
    assert snapshot["revision"] == initial_revision + 1
    assert {row["page_id"] for row in snapshot["projects"]} == {"matched", "unmatched"}
    assert next(row for row in snapshot["projects"] if row["page_id"] == "matched")["fields"] == {"fresh": "yes"}


def test_fetch_failure_preserves_complete_project_and_marks_it_stale(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    old = _project("failed", 2); old["fields"] = {"kept": "yes"}
    old["roles"] = {"FAE QA": [{"identity": "u1", "name": "Alice"}]}
    repository.import_legacy_snapshot("coco", {"phase": "ready", "projects": [old]})
    incoming = _project("failed", 3)

    def fail(_row):
        raise RuntimeError("private failure detail must be bounded")

    assert ConfluenceProjectSyncCoordinator(repository).sync([incoming], fail) == ["failed"]
    loaded = repository.load_account_snapshot("coco")["projects"][0]
    assert loaded["fields"] == {"kept": "yes"}
    assert loaded["roles"]["FAE QA"][0]["name"] == "Alice"
    assert loaded["status"] == "stale"
    assert loaded["error"] == {"message": "RuntimeError"}


def test_cancel_before_project_start_does_not_fetch_or_overwrite_committed_data(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    old = _project("cancelled", 2); old["fields"] = {"kept": "yes"}
    repository.import_legacy_snapshot("coco", {"phase": "ready", "projects": [old]})
    calls = []

    result = ConfluenceProjectSyncCoordinator(repository).sync(
        [_project("cancelled", 3)], lambda row: calls.append(row) or row,
        cancelled=lambda: True,
    )

    assert result == ["cancelled"]
    assert calls == []
    assert repository.load_account_snapshot("coco")["projects"][0]["fields"] == {"kept": "yes"}


def test_cancellation_prevents_a_queued_project_from_starting_after_prior_commit(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    first, queued = _project("first", 0), _project("queued", 0)
    repository.import_legacy_snapshot("coco", {"phase": "ready", "projects": [first, queued]})
    cancelled = Event(); calls = []

    def fetch(row):
        calls.append(row["page_id"])
        if row["page_id"] == "first": cancelled.set()
        return {**row, "status": "current"}

    result = ConfluenceProjectSyncCoordinator(repository, max_workers=1).sync(
        [first, queued], fetch, cancelled=cancelled.is_set,
    )

    assert result == ["updated", "cancelled"]
    assert calls == ["first"]
