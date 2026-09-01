from conftest import confirmed_access
from smarttest_web.database import WebDatabase
from core.async_tasks import AsyncTaskSnapshot
from smarttest_web.background_refresh import BackgroundFactsRefresh
import smarttest_web.background_refresh as background_refresh


def test_catalog_refresh_state_is_not_reported_as_detail_sync_status(tmp_path):
    access = confirmed_access(WebDatabase(tmp_path / 'access.db'))
    submitted = []
    refresh = BackgroundFactsRefresh(submit=submitted.append)

    class Owner:
        def refresh(self, _username, _password): return None
        def sync_details(self, *_args, **_kwargs): return {"state": "ready"}

    owner = Owner()
    assert refresh.start(owner, access, "secret")
    assert refresh.state_for(access.session_hash) == "loading"
    assert refresh.status_for(access.session_hash) == {
        "state": "idle", "completed": 0, "total": 0,
    }

    assert refresh.start_details(owner, access, "secret")
    assert refresh.status_for(access.session_hash)["state"] == "loading"


def test_catalog_refresh_has_terminal_ready_state_even_when_owner_returns_no_rows(tmp_path):
    access = confirmed_access(WebDatabase(tmp_path / 'access.db'))
    submitted = []
    refresh = BackgroundFactsRefresh(submit=submitted.append)

    class Owner:
        def refresh(self, _username, _password):
            return {"state": "no_snapshot", "projects": []}

    assert refresh.start(Owner(), access, "secret")
    assert refresh.state_for(access.session_hash) == "loading"
    submitted.pop()()
    assert refresh.state_for(access.session_hash) == "ready"


def test_scoped_detail_job_is_single_flight_reports_progress_and_can_cancel(tmp_path):
    access = confirmed_access(WebDatabase(tmp_path / 'access.db'))
    submitted = []
    refresh = BackgroundFactsRefresh(submit=submitted.append)

    class Owner:
        def sync_details(self, username, password, *, filters, search, cancelled=None, progress=None):
            progress(1, 2)
            assert not cancelled()
            return {"state": "ready"}

    assert refresh.start_details(Owner(), access, "secret", filters={"stage": ["3"]}, search="")
    assert not refresh.start_details(Owner(), access, "secret", filters={}, search="")
    assert refresh.status_for(access.session_hash) == {"state": "loading", "completed": 0, "total": 0}
    submitted.pop()()
    assert refresh.status_for(access.session_hash) == {"state": "ready", "completed": 1, "total": 2}

    assert refresh.start_details(Owner(), access, "secret", filters={}, search="")
    assert refresh.cancel(access.session_hash)
    assert refresh.status_for(access.session_hash)["state"] == "cancelled"


def test_detail_status_exposes_only_the_session_owned_root_snapshot(tmp_path, monkeypatch):
    access = confirmed_access(WebDatabase(tmp_path / "access.db"))

    class Tasks:
        def task_id(self, _future): return "root-task"
        def snapshot(self, task_id):
            assert task_id == "root-task"
            child = AsyncTaskSnapshot("child", "Fetching project A", "running", (99, 100), "root-task")
            return AsyncTaskSnapshot("root-task", "Confluence details", "running", (2, 10), "root-task", visible_child=child, revision=3)

    monkeypatch.setattr(background_refresh, "WEB_TASKS", Tasks())
    refresh = BackgroundFactsRefresh(submit=lambda _work: object())

    class Owner:
        def sync_details(self, *_args, **_kwargs): return None

    assert refresh.start_details(Owner(), access, "secret")
    status = refresh.status_for(access.session_hash)
    assert status["task"] == {
        "state": "running", "progress": {"processed": 2, "total": 10},
        "revision": 3, "visibleChild": {"label": "Fetching project A", "state": "running"},
    }
    assert "id" not in status["task"]
