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
    def search_all_payloads(self, jql, *, fields=None, progress=None):
        self.calls += 1
        self.args = (jql, fields)
        if progress: progress(len(self.issues), len(self.issues))
        return self.issues


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

    assert gateway.args == ('issuetype = Bug AND assignee IN ("amy", "zed") AND project IN ("IPTV", "SH", "TV", "OTT")', ["project", "issuetype", "assignee", "priority", "resolution"])
    assert repository.read("alice", "roster-a")["teamTotal"] == 0


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

    assert service.state("alice", "secret")["state"] == "loading"
    assert service.state("alice", "secret")["state"] == "loading"
    assert tasks.calls == 1


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
