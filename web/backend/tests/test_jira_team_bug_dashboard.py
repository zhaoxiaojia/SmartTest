from smarttest_web.database import WebDatabase
from smarttest_web.jira.team_bug_dashboard import (
    JiraTeamBugDashboardRepository, JiraTeamBugDashboardService, JiraTeamBugTasks,
)
from core.jira.services.team_bug_service import QARoster
from core.product_lines import DASHBOARD_PRODUCT_LINES


class DeferredTasks:
    def __init__(self): self.runners, self.calls = {}, 0
    def submit_once(self, account, fingerprint, runner):
        self.calls += 1
        self.runners.setdefault((account, fingerprint), runner)
        return f"task-{account}"
    def status(self, account, fingerprint):
        return None if (account, fingerprint) not in self.runners else {"id": f"task-{account}", "state": "running", "progress": {"processed": 0, "total": 0}}
    def publish_if_current(self, account, fingerprint, publish):
        if (account, fingerprint) not in self.runners: return False
        publish()
        return True


class Gateway:
    def __init__(self, issues): self.issues, self.calls, self.args = issues, 0, None
    def validate_jql(self, jql):
        self.validated = jql
        return {"valid": True, "errors": []}
    def search_all_payloads(self, jql, *, fields=None, progress=None):
        self.calls += 1
        self.args = (jql, fields)
        if progress: progress(len(self.issues), len(self.issues))
        return self.issues


def test_empty_roster_does_not_start_dashboard_query_or_keep_old_counts(tmp_path):
    repository = JiraTeamBugDashboardRepository(WebDatabase(tmp_path / 'web.db'))
    repository.replace('alice', 'old', overview(99))
    gateway, tasks = Gateway([]), DeferredTasks()
    service = JiraTeamBugDashboardService(repository, lambda *_args: gateway, tasks,
                                         lambda: QARoster((), 'empty'))
    result = service.state('alice', 'secret')
    assert result['state'] == 'failed'
    assert result['error'] == 'empty_fae_qa_roster'
    assert result['teamTotal'] == 0
    assert gateway.calls == tasks.calls == 0


def overview(total=0):
    return {"teamTotal": total, "productLines": [
        {"id": line.name, "label": line.name, "people": []}
        for line in DASHBOARD_PRODUCT_LINES
    ]}


class RegisteredTaskManager:
    def __init__(self): self.runners, self.states, self.cancelled = {}, {}, []
    def submit(self, _label, runner):
        task_id = f"task-{len(self.runners) + 1}"
        future = object()
        self.runners[task_id] = (future, runner)
        self.states[task_id] = "running"
        return future
    def task_id(self, future):
        return next(task_id for task_id, (candidate, _runner) in self.runners.items() if candidate is future)
    def snapshot(self, task_id):
        return type("Snapshot", (), {"state": self.states[task_id]})()
    def cancel(self, task_id):
        self.cancelled.append(task_id)
        self.states[task_id] = "cancelled"


def test_existing_account_snapshot_is_returned_without_remote_access(tmp_path):
    repository = JiraTeamBugDashboardRepository(WebDatabase(tmp_path / "web.db"))
    payload = overview(1)
    payload["productLines"][0]["people"] = [{"identity": "a", "displayName": "Alice", "bugCount": 1,
        "resolvedCount": 0, "p0Count": 0, "invalidCount": 0}]
    repository.replace("alice", "roster-a", payload)
    gateway = Gateway([])
    service = JiraTeamBugDashboardService(repository, lambda *_: gateway, DeferredTasks(), lambda: QARoster(("a",), "roster-a"))

    result = service.state("alice", "secret")

    assert result["state"] == "ready"
    assert result["teamTotal"] == 1
    assert gateway.calls == 0


def test_missing_snapshot_starts_only_one_account_task_and_uses_minimal_bug_query(tmp_path):
    repository = JiraTeamBugDashboardRepository(WebDatabase(tmp_path / "web.db"))
    tasks, gateway = DeferredTasks(), Gateway([])
    service = JiraTeamBugDashboardService(repository, lambda *_: gateway, tasks, lambda: QARoster(("amy", "zed"), "roster-a"))

    assert service.state("alice", "secret")["state"] == "loading"
    assert service.state("alice", "secret")["state"] == "loading"
    assert tasks.calls == 1
    tasks.runners[("alice", "roster-a")](None, lambda *_: None)

    expected = 'issuetype = Bug AND reporter IN ("amy", "zed") AND "Channel of Reporter" = "Self-Test" AND created >= startOfYear() AND created <= endOfYear()'
    assert gateway.args == (expected, ["project", "reporter", "priority", "resolution"])
    assert gateway.validated == repository.read("alice", "roster-a")["effectiveJql"] == expected
    assert repository.read("alice", "roster-a")["teamTotal"] == 0


def test_dashboard_sqlite_replays_wireless_unknown_project_and_missing_reporter_counts(tmp_path):
    repository = JiraTeamBugDashboardRepository(WebDatabase(tmp_path / 'web.db'))
    tasks = DeferredTasks()
    gateway = Gateway([{'fields': {'project': {'key': 'unknown'}, 'reporter': {'name': 'wifi'}}},
                       {'fields': {'project': {'key': 'unknown'}}}])
    from core.product_lines import WIRELESS_CONNECTION
    roster = QARoster(('wifi',), 'roster', (('wifi', (WIRELESS_CONNECTION.name,)),))
    service = JiraTeamBugDashboardService(repository, lambda *_args: gateway, tasks, lambda: roster)
    service.state('alice', 'secret')
    tasks.runners[('alice', 'roster')](None, lambda *_args: None)
    restored = service.state('alice', 'secret')
    displayed = sum(person['bugCount'] for line in restored['productLines'] for person in line['people'])
    assert restored['teamTotal'] == displayed + restored['unmappedCount'] + restored['unassignedCount'] == 2
    assert restored['unmappedCount'] == 0
    assert restored['productLines'][4]['people'][0]['identity'] == 'wifi'
    assert restored['effectiveJql'] == gateway.validated == gateway.args[0]


def test_dashboard_metadata_migration_preserves_legacy_snapshot(tmp_path):
    database = WebDatabase(tmp_path / 'web.db')
    repository = JiraTeamBugDashboardRepository(database)
    repository.replace('alice', 'legacy', overview(17))
    with database.transaction() as connection:
        for column in ('effective_jql', 'unmapped_count', 'unassigned_count'):
            connection.execute(f'ALTER TABLE jira_team_bug_snapshots DROP COLUMN {column}')
    migrated = JiraTeamBugDashboardRepository(database).read('alice', 'legacy')
    assert migrated['teamTotal'] == 17
    assert migrated['effectiveJql'] == ''
    assert migrated['unmappedCount'] == migrated['unassignedCount'] == 0


def test_snapshots_are_account_isolated_and_failed_replace_preserves_active(tmp_path):
    repository = JiraTeamBugDashboardRepository(WebDatabase(tmp_path / "web.db"))
    repository.replace("alice", "roster-a", overview(2))
    repository.record_failure("alice", "roster-a", "jira_search_failed")
    repository.replace("bob", "roster-a", overview(1))

    assert repository.read("alice", "roster-a")["teamTotal"] == 2
    assert repository.read("bob", "roster-a")["teamTotal"] == 1
    assert repository.read("alice", "changed-roster") is None
    repository.delete_account("alice")
    assert repository.read("alice", "roster-a") is None
    assert repository.read("bob", "roster-a")["teamTotal"] == 1


def test_roster_change_invalidates_snapshot_and_starts_one_new_task(tmp_path):
    repository = JiraTeamBugDashboardRepository(WebDatabase(tmp_path / "web.db"))
    repository.replace("alice", "old-roster", overview(2))
    tasks = DeferredTasks()
    service = JiraTeamBugDashboardService(
        repository, lambda *_: Gateway([]), tasks,
        lambda: QARoster(("amy",), "new-roster"),
    )

    first = service.state("alice", "secret")
    assert first["state"] == "loading"
    assert first["teamTotal"] == 2
    assert service.state("alice", "secret")["state"] == "loading"
    assert tasks.calls == 1
    tasks.runners[("alice", "new-roster")](None, lambda *_: None)
    assert service.state("alice", "secret")["teamTotal"] == 0
    assert service.state("alice", "secret")["state"] == "ready"


def test_old_roster_generation_cannot_publish_after_new_generation_is_registered(tmp_path):
    repository = JiraTeamBugDashboardRepository(WebDatabase(tmp_path / "web.db"))
    manager = RegisteredTaskManager()
    tasks = JiraTeamBugTasks(manager)
    tasks.submit_once("alice", "old", lambda *_: None)
    tasks.submit_once("alice", "new", lambda *_: None)

    old_published = tasks.publish_if_current(
        "alice", "old", lambda: repository.replace("alice", "old", overview(99)),
    )
    new_published = tasks.publish_if_current(
        "alice", "new", lambda: repository.replace("alice", "new", overview(1)),
    )

    assert old_published is False
    assert new_published is True
    assert repository.read("alice", "new")["teamTotal"] == 1
    assert repository.read("alice", "old") is None


def test_failed_initial_task_is_reported_without_automatic_retry(tmp_path):
    repository = JiraTeamBugDashboardRepository(WebDatabase(tmp_path / "web.db"))
    tasks = DeferredTasks()
    service = JiraTeamBugDashboardService(repository, lambda *_: Gateway([]), tasks, lambda: QARoster(("alice",), "roster-a"))
    service.state("alice", "secret")
    repository.record_failure("alice", "roster-a", "jira_search_failed")
    tasks.status = lambda _account, _fingerprint: {"id": "task-alice", "state": "failed", "progress": {"processed": 0, "total": 0}}

    result = service.state("alice", "secret")

    assert result == {"state": "failed", "task": tasks.status("alice", "roster-a"), "error": "jira_search_failed"}
    assert tasks.calls == 1

    restarted_tasks = DeferredTasks()
    restarted = JiraTeamBugDashboardService(
        repository, lambda *_: Gateway([]), restarted_tasks,
        lambda: QARoster(("alice",), "roster-a"),
    )
    assert restarted.state("alice", "secret")["state"] == "failed"
    assert restarted_tasks.calls == 0


def test_failed_refresh_keeps_same_account_last_sqlite_statistics(tmp_path):
    repository = JiraTeamBugDashboardRepository(WebDatabase(tmp_path / "web.db"))
    repository.replace("alice", "old", overview(4))
    repository.record_failure("alice", "new", "jira_search_failed")
    tasks = DeferredTasks()
    service = JiraTeamBugDashboardService(repository, lambda *_: Gateway([]), tasks,
                                         lambda: QARoster(("alice",), "new"))
    result = service.state("alice", "secret")
    assert result["state"] == "failed"
    assert result["error"] == "jira_search_failed"
    assert result["teamTotal"] == 4
    assert tasks.calls == 0
