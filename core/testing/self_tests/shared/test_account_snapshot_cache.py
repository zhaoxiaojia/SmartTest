import json

import pytest

from core.accounts.snapshot_cache import AccountScopedSnapshotCache
from testing.self_tests.shared.test_account_dynamic_source import NOW


@pytest.mark.parametrize("content", [
    "[]", "null", "{}", '{"fetched_at": 4}', "{",
])
def test_malformed_cache_is_a_miss(tmp_path, content):
    cache = AccountScopedSnapshotCache(tmp_path)
    path = cache._path("d", "s", "a")
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    assert cache.load("d", "s", "a") is None


def test_owner_hash_avoids_sanitization_collisions(tmp_path):
    cache = AccountScopedSnapshotCache(tmp_path)
    assert cache._path("a/b", "s", "x").parent != cache._path("ab", "s", "x").parent
    assert cache._path("d", "a/b", "x").parent != cache._path("d", "ab", "x").parent


def test_lru_only_deletes_owned_snapshot_files(tmp_path):
    cache = AccountScopedSnapshotCache(tmp_path, max_files=1)
    cache.save("d", "s", "a", {"v": 1}, fetched_at=NOW)
    directory = cache._path("d", "s", "a").parent
    unrelated = directory / "unrelated.json"
    unrelated.write_text(json.dumps({"keep": True}), encoding="utf-8")
    cache.save("d", "s", "b", {"v": 2}, fetched_at=NOW)
    assert unrelated.is_file()
    assert cache.load("d", "s", "a") is None
    assert cache.load("d", "s", "b").payload == {"v": 2}
