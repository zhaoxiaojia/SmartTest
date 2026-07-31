from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from support.account_snapshot_cache import AccountScopedSnapshotCache
from support.account_dynamic_source import AccountDynamicSource, RefreshState

NOW=datetime(2026,7,30,tzinfo=timezone.utc)
def immediate(call): call()

def test_cache_schema_size_source_and_file_lru(tmp_path):
    cache=AccountScopedSnapshotCache(tmp_path,max_files=2,max_bytes=500)
    cache.save("d","s","a",{"v":1},fetched_at=NOW)
    assert cache.load("d","s","a").payload=={"v":1}
    assert cache.load("d","other","a") is None
    cache.save("d","s","b",{"v":2},fetched_at=NOW)
    cache.save("d","s","c",{"v":3},fetched_at=NOW)
    directory=cache._path("d","s","c").parent
    assert len(list(directory.glob("*.json")))==2
    assert cache.load("d","s","a") is None
    assert '"account":"' not in "".join(path.read_text() for path in directory.glob("*.json"))

def test_two_domains_are_cache_first_account_isolated_and_ttl_aware(tmp_path):
    cache=AccountScopedSnapshotCache(tmp_path)
    cache.save("jira","filters","alice",{"v":1},fetched_at=NOW)
    for domain in ("jira","confluence"):
        events=[]; calls=[]
        source=AccountDynamicSource(cache,domain,"filters",lambda x:{"v":x},
          lambda x:x["v"],ttl=timedelta(minutes=10),now=lambda:NOW,submit=immediate)
        source.open("alice",lambda:calls.append(2) or 2,events.append)
        if domain=="jira":
            assert [e.state for e in events]==[RefreshState.CACHED]; assert not calls
        else:
            assert events[-1].state==RefreshState.UPDATED; assert calls
        assert all("alice" not in repr(e) for e in events)

def test_failure_keeps_cache_and_stale_generation_is_rejected(tmp_path):
    cache=AccountScopedSnapshotCache(tmp_path); pending=[]; events=[]
    cache.save("d","s","a",{"v":1},fetched_at=NOW-timedelta(hours=1))
    source=AccountDynamicSource(cache,"d","s",lambda x:{"v":x},lambda x:x["v"],
      ttl=timedelta(minutes=1),now=lambda:NOW,submit=pending.append)
    source.open("a",lambda:(_ for _ in ()).throw(RuntimeError("secret")),events.append)
    source.open("b",lambda:2,events.append)
    pending[0](); pending[1]()
    assert not any(e.state==RefreshState.REFRESH_FAILED for e in events)
    assert events[-1].state==RefreshState.UPDATED
    assert cache.load("d", "s", "a").payload == {"v": 1}


def test_synchronous_cached_callback_cannot_relabel_old_account(tmp_path):
    cache = AccountScopedSnapshotCache(tmp_path)
    cache.save("d", "s", "a", {"v": 1}, fetched_at=NOW)
    cache.save("d", "s", "b", {"v": 2}, fetched_at=NOW)
    source = AccountDynamicSource(
        cache, "d", "s", lambda value: {"v": value}, lambda row: row["v"],
        ttl=timedelta(hours=1), now=lambda: NOW, submit=immediate,
    )
    events = []

    def publish(event):
        events.append(event)
        if event.snapshot == 1:
            source.open("b", lambda: 3, events.append)

    source.open("a", lambda: 4, publish)
    assert [(event.snapshot, event.account_hash) for event in events] == [
        (1, cache.identity("a")),
        (2, cache.identity("b")),
    ]


def test_close_and_new_generation_prevent_submit_save_and_publish(tmp_path):
    cache = AccountScopedSnapshotCache(tmp_path)
    pending = []
    events = []
    source = AccountDynamicSource(
        cache, "d", "s", lambda value: {"v": value}, lambda row: row["v"],
        ttl=timedelta(0), now=lambda: NOW, submit=pending.append,
    )
    source.open("a", lambda: 1, events.append)
    source.open("a", lambda: 2, events.append)
    pending[0]()
    assert cache.load("d", "s", "a") is None
    source.close()
    pending[1]()
    assert cache.load("d", "s", "a") is None
    assert source.open("a", lambda: 3, events.append) is None


def test_publish_and_submit_exceptions_are_isolated(tmp_path):
    cache = AccountScopedSnapshotCache(tmp_path)
    events = []
    source = AccountDynamicSource(
        cache, "d", "s", lambda value: {"v": value}, lambda row: row["v"],
        ttl=timedelta(0), now=lambda: NOW,
        submit=lambda _work: (_ for _ in ()).throw(RuntimeError("executor stopped")),
    )
    source.open("a", lambda: 1, events.append)
    assert events[-1].state == RefreshState.REFRESH_FAILED
    assert events[-1].snapshot is None

    callback_source = AccountDynamicSource(
        cache, "x", "s", lambda value: {"v": value}, lambda row: row["v"],
        ttl=timedelta(0), now=lambda: NOW, submit=immediate,
    )
    callback_source.open(
        "a", lambda: 1,
        lambda _event: (_ for _ in ()).throw(RuntimeError("view destroyed")),
    )
    assert cache.load("x", "s", "a").payload == {"v": 1}


def test_corrupt_deserializer_becomes_cache_miss_and_refreshes(tmp_path):
    cache = AccountScopedSnapshotCache(tmp_path)
    cache.save("d", "s", "a", {"wrong": 1}, fetched_at=NOW)
    events = []
    source = AccountDynamicSource(
        cache, "d", "s", lambda value: {"v": value}, lambda row: row["v"],
        ttl=timedelta(hours=1), now=lambda: NOW, submit=immediate,
    )
    source.open("a", lambda: 9, events.append)
    assert [event.state for event in events] == [
        RefreshState.FIRST_LOADING, RefreshState.UPDATED,
    ]
    assert events[0].error_kind == "cache_corrupt"


def test_publish_callback_can_close_from_another_thread_without_deadlock(tmp_path):
    cache = AccountScopedSnapshotCache(tmp_path)
    source = AccountDynamicSource(
        cache, "d", "s", lambda value: {"v": value}, lambda row: row["v"],
        ttl=timedelta(0), now=lambda: NOW, submit=immediate,
    )
    close_completed = Event()
    callback_observed_close = Event()

    def publish(_event):
        closer = Thread(
            target=lambda: (source.close(), close_completed.set()),
            daemon=True,
        )
        closer.start()
        closer.join(timeout=0.5)
        if not closer.is_alive():
            callback_observed_close.set()

    source.open("a", lambda: 1, publish)
    assert close_completed.wait(0.1)
    assert callback_observed_close.is_set()
