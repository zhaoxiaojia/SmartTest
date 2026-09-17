from concurrent.futures import Future
from threading import Event
import time

from smarttest_web.jira.analytics_service import JiraAnalyticsService
from core.jira.services.filter_service import build_basic_jql
from core.async_tasks import AsyncTaskManager
from smarttest_web.jira.analytics_tasks import JiraAnalyticsTasks


def test_builds_fixed_basic_jql_deterministically():
    assert build_basic_jql({
        "project": ["SH", "TV"], "issueType": ["Bug"], "status": ["Open"],
        "resolution": ["Unresolved"], "assignee": ["coco"], "containsText": 'wifi "drop"',
    }, {}) == ('project IN ("SH", "TV") AND issuetype IN ("Bug") AND status IN ("Open") '
               'AND assignee IN ("coco") AND text ~ "wifi \\"drop\\"" AND resolution IN ("Unresolved")')


def test_builds_supported_dynamic_fields_and_rejects_advanced_only():
    fields = {"customfield_1": {"control": "number", "queryable": True},
              "customfield_2": {"control": "advanced", "queryable": False}}
    assert build_basic_jql({"more": {"customfield_1": 7}}, fields) == 'customfield_1 = 7'
    try:
        build_basic_jql({"more": {"customfield_2": "x"}}, fields)
    except ValueError as error:
        assert str(error) == "advanced_only:customfield_2"
    else:
        raise AssertionError("advanced-only field accepted")


def test_builds_dynamic_user_values_returned_by_jira_as_a_multi_value_clause():
    fields = {"reporter": {"control": "user", "queryable": True}}

    assert build_basic_jql({"more": {"reporter": ["coco", "mason"]}}, fields) == (
        'reporter IN ("coco", "mason")'
    )


class Repo:
    def __init__(self): self.calls = []
    def begin(self, *args, **kwargs): self.calls.append(("begin", args, kwargs)); return "snapshot"
    def set_task(self, *args): self.calls.append(("task", args))
    def write_batch(self, *args): self.calls.append(("write", args))
    def activate(self, *args): self.calls.append(("activate", args)); return True
    def finish(self, *args): self.calls.append(("finish", args))
    def state(self, *_args, **_kwargs): return {"activeSnapshotId": "old", "activeJql": "old", "pendingSnapshotId": "", "taskId": ""}


class Tasks:
    def submit(self, session, runner, *, card_key=""):
        self.runner = runner; return "task-1"


class Filter:
    def fields(self): return []
    def validate(self, jql): return {"valid": jql != "bad", "errors": ["bad jql"] if jql == "bad" else []}


class Gateway:
    def search_all_payloads(self, _jql, *, progress=None):
        return [{"id": "1", "key": "SH-1", "fields": {"summary": "One", "project": {}, "status": {}, "issuetype": {}}}]


class Mapper:
    def from_search(self, payload): return payload


def test_card_tasks_are_independent_with_the_same_session_and_user_conditions():
    manager = AsyncTaskManager(max_workers=2)
    tasks = JiraAnalyticsTasks(manager)
    entered = [Event(), Event()]
    release = Event()
    try:
        def runner(index):
            def run(token, report):
                entered[index].set()
                assert release.wait(2)
                token.raise_if_cancelled()
            return run
        first = tasks.submit("session", runner(0), card_key="first")
        second = tasks.submit("session", runner(1), card_key="second")
        assert all(event.wait(2) for event in entered)
        assert tasks.status("session", first, card_key="second") is None
        assert tasks.cancel("session", second, card_key="first") is False
        release.set()
        for _ in range(100):
            states = [tasks.status("session", first, card_key="first")["state"],
                      tasks.status("session", second, card_key="second")["state"]]
            if states == ["completed", "completed"]:
                break
            time.sleep(0.01)
        assert states == ["completed", "completed"]
    finally:
        release.set()
        manager.close()


def test_search_validates_before_snapshot_and_immediately_submits_task():
    repo, tasks = Repo(), Tasks()
    service = JiraAnalyticsService(Filter(), Gateway(), Mapper(), repo, tasks)

    invalid = service.search("s", "alice", 100, {"mode": "advanced", "jql": "bad"})
    valid = service.search("s", "alice", 100, {"mode": "advanced", "jql": "project = SH"})

    assert invalid["validation"]["valid"] is False
    assert repo.calls[0][0] == "begin"
    assert valid["taskId"] == "task-1"
    tasks.runner(type("Token", (), {"raise_if_cancelled": lambda self: None})(), lambda *_: None)
    assert [call[0] for call in repo.calls] == ["begin", "task", "write", "activate"]


def test_preview_returns_server_built_jql_without_creating_snapshot():
    repo = Repo()
    service = JiraAnalyticsService(Filter(), Gateway(), Mapper(), repo, Tasks())

    result = service.preview({"mode": "basic", "basic": {"project": ["SH"]}})

    assert result == {"valid": True, "errors": [], "jql": 'project IN ("SH")', "userJql": 'project IN ("SH")'}
    assert repo.calls == []


def test_background_failure_is_recorded_and_forwarded_to_auth_lifecycle():
    class BrokenGateway:
        def search_all_payloads(self, _jql, *, progress=None): raise RuntimeError("offline")
    failures = []; repo, tasks = Repo(), Tasks()
    service = JiraAnalyticsService(Filter(), BrokenGateway(), Mapper(), repo, tasks, on_error=failures.append)
    service.search("s", "alice", 100, {"mode": "advanced", "jql": "project = SH"})

    try: tasks.runner(type("Token", (), {"raise_if_cancelled": lambda self: None})(), lambda *_: None)
    except RuntimeError: pass

    assert repo.calls[-1][0] == "finish"
    assert len(failures) == 1


def test_card_conditions_are_applied_once_for_preview_search_and_sqlite_effective_scope():
    repo, tasks = Repo(), Tasks()
    class RecordingFilter(Filter):
        def validate(self, jql):
            assert jql == '(project = A OR project = B) AND (channel = "Self-Test") ORDER BY created DESC'
            return {"valid": True, "errors": []}
    service = JiraAnalyticsService(RecordingFilter(), Gateway(), Mapper(), repo, tasks,
                                   fixed_conditions='channel = "Self-Test"')
    draft = 'project = A OR project = B ORDER BY created DESC'
    preview = service.preview({"mode": "advanced", "jql": draft})
    service.search("s", "alice", 100, {"mode": "advanced", "jql": draft})
    assert preview["userJql"] == draft
    assert repo.calls[0][1][2] == preview["jql"]
    assert repo.calls[0][2]["user_jql"] == draft


def test_unselected_basic_conditions_add_only_card_fixed_conditions():
    service = JiraAnalyticsService(Filter(), Gateway(), Mapper(), Repo(), Tasks(),
                                   fixed_conditions='channel = "Self-Test"')
    assert service.preview({"mode": "basic", "basic": {}})["jql"] == 'channel = "Self-Test"'


def test_remote_pagination_progress_is_published_before_sqlite_writes():
    repo, tasks = Repo(), Tasks(); events = []
    class PagedGateway:
        def search_all_payloads(self, _jql, *, progress):
            progress(1, 2)
            assert repo.calls[-1][0] == "task"
            return []
    service = JiraAnalyticsService(Filter(), PagedGateway(), Mapper(), repo, tasks)
    service.search("s", "alice", 100, {"mode": "advanced", "jql": "project = A"})
    tasks.runner(type("Token", (), {"raise_if_cancelled": lambda self: None})(), lambda *args: events.append(args))
    assert events == [(1, 2)]
