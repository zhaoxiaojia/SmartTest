from smarttest_web.confluence_periodic import PeriodicConfluenceRefresh


class FakeThread:
    def __init__(self, target): self.target = target; self.starts = 0; self.joins = 0
    def start(self): self.starts += 1
    def join(self, timeout=None): self.joins += 1


def test_periodic_refresh_clamps_interval_starts_once_deduped_accounts_and_stops():
    class Sessions:
        def active_account_credentials(self):
            return [("coco", "one"), ("atlas", "two")]

    class Refresh:
        def __init__(self): self.calls = []
        def start(self, owner, username, password):
            self.calls.append((owner, username, password)); return username != "atlas"

    threads = []; refresh = Refresh(); owner = object()
    periodic = PeriodicConfluenceRefresh(
        Sessions(), owner, refresh, interval_seconds=10,
        thread_factory=lambda target: threads.append(FakeThread(target)) or threads[-1],
    )
    assert periodic.interval_seconds == 300
    assert periodic.start()
    assert not periodic.start()
    periodic.tick()
    assert refresh.calls == [(owner, "coco", "one"), (owner, "atlas", "two")]
    periodic.stop()
    assert threads[0].starts == 1 and threads[0].joins == 1


def test_active_session_credentials_dedupe_accounts_and_skip_missing_credentials(tmp_path):
    from smarttest_web.session import PersistentSessionStore

    class Credentials:
        def __init__(self): self.values = {}; self.missing = set()
        def write(self, reference, username, password): self.values[reference] = (username, password)
        def read(self, reference):
            from smarttest_web.credentials import CredentialStoreError
            if reference in self.missing: raise CredentialStoreError("missing")
            return self.values[reference]
        def delete(self, reference): self.values.pop(reference, None)

    credentials = Credentials()
    store = PersistentSessionStore(tmp_path / "web.db", credential_store=credentials)
    store.create("coco", "first"); store.create("coco", "second")
    store.create("atlas", "missing")
    credentials.missing.add(next(reference for reference, value in credentials.values.items() if value[0] == "atlas"))

    active = store.active_account_credentials()
    assert len(active) == 1
    assert active[0][0] == "coco"
