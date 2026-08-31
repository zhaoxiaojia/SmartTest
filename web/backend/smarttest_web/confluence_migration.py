from __future__ import annotations

import json


class LegacyConfluenceSnapshotMigration:
    """One-time reader for the retired account JSON snapshot format."""

    def __init__(self, repository, legacy_root):
        self._repository = repository
        self._legacy_root = legacy_root

    def import_account(self, account, namespace):
        if self._repository.load_account_snapshot(account) is not None:
            return False
        path = self._legacy_root / namespace / "project_responsibility_facts.json"
        if not path.exists():
            return False
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("projects"), list):
            raise ValueError("Legacy Confluence snapshot is invalid")
        self._repository.import_legacy_snapshot(account, snapshot)
        path.unlink()
        return True
