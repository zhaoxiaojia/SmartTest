import hashlib
import json

import pytest

from smarttest_web.confluence_repository import ConfluenceCurrentStateRepository
from smarttest_web.confluence_migration import LegacyConfluenceSnapshotMigration


def _path(root, account="coco"):
    namespace = hashlib.sha256(account.encode()).hexdigest()
    return root / namespace / "project_responsibility_facts.json", namespace


def test_legacy_snapshot_is_imported_once_then_removed(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    path, namespace = _path(tmp_path / "legacy"); path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"phase": "ready", "projects": [{
        "page_id": "p1", "project_id": "P1", "name": "One", "space_key": "DOPL",
        "page_url": "https://c/p1", "active": True, "status": "current",
        "fields": {}, "roles": {},
    }]}), encoding="utf-8")
    migration = LegacyConfluenceSnapshotMigration(repository, tmp_path / "legacy")

    assert migration.import_account("coco", namespace)
    assert not path.exists()
    assert not migration.import_account("coco", namespace)
    assert repository.load_account_snapshot("coco")["projects"][0]["page_id"] == "p1"


def test_failed_legacy_import_preserves_file_for_retry(tmp_path):
    repository = ConfluenceCurrentStateRepository(tmp_path / "web.db")
    path, namespace = _path(tmp_path / "legacy"); path.parent.mkdir(parents=True)
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        LegacyConfluenceSnapshotMigration(repository, tmp_path / "legacy").import_account("coco", namespace)

    assert path.exists()
    assert repository.load_account_snapshot("coco") is None
