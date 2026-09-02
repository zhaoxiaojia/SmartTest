import asyncio
from client.app.data_sources.common import (
    AuthenticatedCredentials,
    DataSourceError,
    DataSourceResult,
)

from client.app.ui.example.bridge.TestPageBridge import TestPageBridge as PageBridge


class Auth:
    def __init__(self, credentials=None):
        self.credentials = credentials
        self.invalidations = []
    def runtime_credentials(self): return self.credentials
    def invalidate_runtime_credentials(self, code):
        self.invalidations.append(code)
        return code == "invalid_credentials"


class Gateway:
    def __init__(self): self.created = None
    def create_suite(self, credentials, payload):
        self.created = payload
        return DataSourceResult.success({"id": "1", "revision": 1})


def test_suite_payload_contains_only_suite_metadata_and_order(tmp_path, monkeypatch):
    bridge = PageBridge(tmp_path, auth_bridge=Auth(), suite_source=Gateway())
    bridge._state.selected = []
    bridge._cases = [{"nodeid": "a", "file": "testing/tests/a.py", "case_type": "default"}]
    bridge._rebuild_case_indexes()
    bridge._set_case_selected("a", True)
    payload = bridge._suite_write_payload("Suite", "desc", "private")
    assert payload == {"name": "Suite", "description": "desc", "visibility": "private",
                       "orderedNodeids": ["a"]}


def test_loading_suite_replaces_selection_preserves_order_and_reports_missing(tmp_path, monkeypatch):
    bridge = PageBridge(tmp_path, auth_bridge=Auth(), suite_source=Gateway())
    bridge._cases = [
        {"nodeid": "a", "file": "testing/tests/a.py", "case_type": "default"},
        {"nodeid": "b", "file": "testing/tests/b.py", "case_type": "default"},
    ]
    bridge._rebuild_case_indexes()
    missing = bridge._apply_suite_selection({"id": "s", "revision": 2,
        "ownerUsername": "coco", "orderedNodeids": ["b", "gone", "a"]}, "coco")
    assert bridge._selected_nodeids() == ["b", "a"]
    assert missing == ["gone"]
    assert bridge._active_suite_id == "s" and bridge._active_suite_revision == 2


def test_account_generation_serializes_cookie_session_and_discards_old_results(tmp_path):
    class SessionSource:
        def __init__(self): self.username = ""; self.events = []
        def switch_account(self, credentials, scope):
            self.events.append("account:" + credentials.username)
            self.username = credentials.username
            return DataSourceResult.success([{"id": self.username, "name": scope}])
    class ControlledTasks:
        def __init__(self): self.old_started = asyncio.Event(); self.release_old = asyncio.Event()
        async def to_thread(self, label, function, *args):
            if label == "suite-account" and args[0].username == "old":
                self.old_started.set()
                await self.release_old.wait()
            return function(*args)

    async def scenario():
        source = SessionSource()
        bridge = PageBridge(tmp_path, auth_bridge=Auth(), suite_source=source)
        bridge._tasks = ControlledTasks()
        bridge._suite_session_generation = 1
        bridge._suite_view_generation = 1
        old = asyncio.create_task(bridge._reset_suite_session(
            AuthenticatedCredentials("old", "one"), 1, 1))
        await bridge._tasks.old_started.wait()
        bridge._suite_session_generation = 2
        bridge._suite_view_generation = 2
        new = asyncio.create_task(bridge._reset_suite_session(
            AuthenticatedCredentials("new", "two"), 2, 2))
        bridge._tasks.release_old.set()
        await asyncio.gather(old, new)
        assert source.username == "new"
        assert bridge._suite_rows == [{"id": "new", "name": "mine"}]
        assert source.events[-1] == "account:new"

    asyncio.run(scenario())


def test_view_generation_discards_stale_scope_refresh(tmp_path):
    class ScopeSource:
        @staticmethod
        def list_suites(credentials, scope):
            return DataSourceResult.success([{"id": scope, "name": scope}])

    class ControlledTasks:
        def __init__(self):
            self.mine_started = asyncio.Event()
            self.release_mine = asyncio.Event()

        async def to_thread(self, label, function, *args):
            if label == "suite-list" and args[1] == "mine":
                self.mine_started.set()
                await self.release_mine.wait()
            return function(*args)

    async def scenario():
        credentials = AuthenticatedCredentials("coco", "secret")
        bridge = PageBridge(tmp_path, auth_bridge=Auth(credentials), suite_source=ScopeSource())
        bridge._tasks = ControlledTasks()
        bridge._suite_session_generation = 1
        bridge._suite_view_generation = 1
        mine = asyncio.create_task(bridge._refresh_suites_task(1, 1, "mine"))
        await bridge._tasks.mine_started.wait()
        bridge._suite_scope = "shared"
        bridge._suite_view_generation = 2
        shared = asyncio.create_task(bridge._refresh_suites_task(1, 2, "shared"))
        bridge._tasks.release_mine.set()
        await asyncio.gather(mine, shared)
        assert bridge._suite_rows == [{"id": "shared", "name": "shared"}]

    asyncio.run(scenario())


def test_refresh_recovers_after_initial_source_outage_without_client_restart(tmp_path):
    class RecoveringSource:
        def __init__(self): self.calls = 0
        def list_suites(self, credentials, scope):
            self.calls += 1
            if self.calls == 1:
                return DataSourceResult.failure(
                    DataSourceError("service_unavailable", retryable=True, stage="login")
                )
            return DataSourceResult.success([{"id": "recovered", "name": scope}])

    async def scenario():
        credentials = AuthenticatedCredentials("coco", "secret")
        source = RecoveringSource()
        bridge = PageBridge(tmp_path, auth_bridge=Auth(credentials), suite_source=source)
        bridge._suite_session_generation = 1
        bridge._suite_view_generation = 1
        await bridge._refresh_suites_task(1, 1, "mine")
        assert bridge._suite_error == "service_unavailable"
        bridge._suite_view_generation = 2
        await bridge._refresh_suites_task(1, 2, "mine")
        assert bridge._suite_error == ""
        assert bridge._suite_rows == [{"id": "recovered", "name": "mine"}]

    asyncio.run(scenario())


def test_refresh_error_keeps_last_successful_rows_in_display_state(tmp_path):
    class FailingSource:
        @staticmethod
        def list_suites(credentials, scope):
            return DataSourceResult.failure(
                DataSourceError("service_unavailable", retryable=True, stage="list")
            )

    async def scenario():
        credentials = AuthenticatedCredentials("coco", "secret")
        bridge = PageBridge(tmp_path, auth_bridge=Auth(credentials), suite_source=FailingSource())
        bridge._suite_rows = [{"id": "last-good", "name": "Cached display row"}]
        await bridge._refresh_suites_task(0, 0, "mine")
        assert bridge._suite_rows == [{"id": "last-good", "name": "Cached display row"}]
        assert bridge._suite_error == "service_unavailable"

    asyncio.run(scenario())


def test_suite_invalid_credentials_uses_auth_owner_but_service_failure_does_not(tmp_path):
    class Source:
        result = DataSourceResult.failure(
            DataSourceError("invalid_credentials", retryable=False, stage="login", http_status=401)
        )

        @classmethod
        def list_suites(cls, credentials, scope):
            return cls.result

    async def scenario():
        credentials = AuthenticatedCredentials("coco", "secret")
        auth = Auth(credentials)
        bridge = PageBridge(tmp_path, auth_bridge=auth, suite_source=Source())
        await bridge._refresh_suites_task(0, 0, "mine")
        assert auth.invalidations == ["invalid_credentials"]
        Source.result = DataSourceResult.failure(
            DataSourceError("service_unavailable", retryable=True, stage="list")
        )
        await bridge._refresh_suites_task(0, 0, "mine")
        assert auth.invalidations == ["invalid_credentials"]

    asyncio.run(scenario())


def test_suite_refresh_logs_generation_and_final_error_state(tmp_path):
    class FailingSource:
        @staticmethod
        def list_suites(credentials, scope):
            return DataSourceResult.failure(
                DataSourceError("service_unavailable", retryable=True, stage="list")
            )

    async def scenario():
        credentials = AuthenticatedCredentials("coco", "secret")
        bridge = PageBridge(tmp_path, auth_bridge=Auth(credentials), suite_source=FailingSource())
        bridge._suite_session_generation = 7
        bridge._suite_view_generation = 9
        records = []
        bridge._trace = lambda stage, **values: records.append((stage, values))
        await bridge._refresh_suites_task(7, 9, "mine")
        assert records == [
            ("suite_refresh_start", {"generation": 7, "view_generation": 9,
                                     "scope": "mine"}),
            ("suite_refresh_done", {"generation": 7, "view_generation": 9,
                                    "current": True,
                                    "final_error": "service_unavailable"}),
        ]

    asyncio.run(scenario())


def test_repeated_refresh_is_coalesced_while_one_refresh_is_running(tmp_path):
    credentials = AuthenticatedCredentials("coco", "secret")
    bridge = PageBridge(tmp_path, auth_bridge=Auth(credentials), suite_source=object())
    scheduled = []

    def capture(coroutine, *, label):
        scheduled.append(label)
        coroutine.close()

    bridge._create_task = capture
    bridge.refreshSuites()
    bridge.refreshSuites()
    assert scheduled == ["suite_refresh"]


def test_scope_change_during_refresh_queues_latest_scope(tmp_path):
    credentials = AuthenticatedCredentials("coco", "secret")
    bridge = PageBridge(tmp_path, auth_bridge=Auth(credentials), suite_source=object())
    bridge._suite_refresh_running = True
    bridge._suite_view_generation = 1
    scheduled = []

    def capture(coroutine, *, label):
        scheduled.append((label, bridge._suite_scope))
        coroutine.close()

    bridge._create_task = capture
    bridge.setSuiteScope("shared")
    asyncio.run(bridge._refresh_suites_task(0, 1, "mine"))
    assert scheduled == [("suite_refresh", "shared")]


def test_bridge_passes_current_credentials_to_authenticated_suite_actions(tmp_path):
    credentials = AuthenticatedCredentials("coco", "secret")

    class Source:
        def __init__(self): self.calls = []
        def create_suite(self, received, payload):
            self.calls.append(("create", received, payload))
            return DataSourceResult.success({"id": "suite-1", "revision": 1})
        def list_suites(self, received, scope):
            self.calls.append(("list", received, scope))
            return DataSourceResult.success([])

    class ImmediateTasks:
        @staticmethod
        async def to_thread(label, function, *args):
            return function(*args)

    source = Source()
    bridge = PageBridge(tmp_path, auth_bridge=Auth(credentials), suite_source=source)
    bridge._tasks = ImmediateTasks()
    scheduled = []
    bridge._create_task = lambda coroutine, *, label: scheduled.append(coroutine)
    bridge._start_suite_action("create", source.create_suite, {"name": "Suite"})
    asyncio.run(scheduled[0])
    assert source.calls == [
        ("create", credentials, {"name": "Suite"}),
        ("list", credentials, "mine"),
    ]
