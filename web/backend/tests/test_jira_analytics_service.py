from concurrent.futures import Future

from smarttest_web.jira.analytics_service import JiraAnalyticsService, build_basic_jql


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
    def state(self, *_args): return {"activeSnapshotId": "old", "activeJql": "old", "pendingSnapshotId": "", "taskId": ""}


class Tasks:
    def submit(self, session, runner):
        self.runner = runner; return "task-1"


class Filter:
    def fields(self): return []
    def validate(self, jql): return {"valid": jql != "bad", "errors": ["bad jql"] if jql == "bad" else []}


class Gateway:
    def search_all_payloads(self, _jql):
        return [{"id": "1", "key": "SH-1", "fields": {"summary": "One", "project": {}, "status": {}, "issuetype": {}}}]


class Mapper:
    def from_search(self, payload): return payload


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

    assert result == {"valid": True, "errors": [], "jql": 'project IN ("SH")'}
    assert repo.calls == []


def test_background_failure_is_recorded_and_forwarded_to_auth_lifecycle():
    class BrokenGateway:
        def search_all_payloads(self, _jql): raise RuntimeError("offline")
    failures = []; repo, tasks = Repo(), Tasks()
    service = JiraAnalyticsService(Filter(), BrokenGateway(), Mapper(), repo, tasks, on_error=failures.append)
    service.search("s", "alice", 100, {"mode": "advanced", "jql": "project = SH"})

    try: tasks.runner(type("Token", (), {"raise_if_cancelled": lambda self: None})(), lambda *_: None)
    except RuntimeError: pass

    assert repo.calls[-1][0] == "finish"
    assert len(failures) == 1
