from core.domain.values import NamedValue
from core.jira.domain import Issue, IssueIdentity, JiraProjectRef
from smarttest_web.database import WebDatabase
from smarttest_web.jira.analytics_repository import JiraAnalyticsRepository
from core.jira.services.team_bug_service import QARoster, self_test_jira_conditions


def test_reuse_selects_exact_valid_history_after_failure_and_old_task_cannot_override(tmp_path):
    repo = JiraAnalyticsRepository(WebDatabase(tmp_path / 'web.db'))
    cached = repo.begin('first', 'alice', 'month effective', {}, '', expires_at=100,
                        user_jql='', card_key='self-test', roster_fingerprint='roster')
    repo.write_batch(cached, [issue('A-1')]); repo.activate(cached)
    failed = repo.begin('first', 'alice', 'month effective', {}, '', expires_at=100,
                        user_jql='', card_key='self-test', roster_fingerprint='roster')
    repo.finish(failed, 'failed', 'query_failed')
    assert repo.state('second', 'alice', card_key='self-test')['latestState'] == 'failed'
    assert repo.reuse('second', 'alice', 'month effective', card_key='self-test', roster_fingerprint='roster')
    assert repo.state('second', 'alice', card_key='self-test')['latestState'] == 'active'
    assert repo.issue_keys('second', 'alice', card_key='self-test') == ['A-1']
    assert not repo.reuse('second', 'alice', 'month effective', card_key='self-test', roster_fingerprint='changed')
    assert not repo.reuse('second', 'bob', 'month effective', card_key='self-test', roster_fingerprint='roster')
    assert not repo.reuse('second', 'alice', 'different condition', card_key='self-test', roster_fingerprint='roster')
    old = repo.begin('first', 'alice', 'week effective', {}, '', expires_at=100, card_key='self-test')
    assert repo.reuse('second', 'alice', 'month effective', card_key='self-test', roster_fingerprint='roster')
    assert not repo.activate(old)
    assert repo.state('second', 'alice', card_key='self-test')['activeSnapshotId'] == cached
    assert repo.state('second', 'alice', card_key='self-test')['latestState'] == 'active'


def seed_dashboard(database, account, *, fingerprint, jql, total=5370):
    with database.transaction() as connection:
        connection.execute("INSERT INTO jira_team_bug_accounts(account,active_snapshot_id) VALUES(?,?)", (account, account))
        connection.execute("""INSERT INTO jira_team_bug_snapshots
            (snapshot_id,account,roster_fingerprint,team_total,created_at,effective_jql,unmapped_count)
            VALUES(?,?,?,?,10,?,360)""", (account, account, fingerprint, total, jql))
        connection.execute("INSERT INTO jira_team_bug_lines VALUES(?,0,'Wireless Connection','')", (account,))
        connection.execute("INSERT INTO jira_team_bug_rows VALUES(?,'Wireless Connection',0,'qa','QA',5010,5,2,0)", (account,))


def issue(key):
    return Issue(identity=IssueIdentity(key, key, ""), summary=key,
                 project=JiraProjectRef("P", "p", "Project"),
                 status=NamedValue("1", "Open"), issue_type=NamedValue("2", "Bug"))


def test_snapshots_are_isolated_by_session_and_account(tmp_path):
    repo = JiraAnalyticsRepository(WebDatabase(tmp_path / "web.db"), now=lambda: 10)
    first = repo.begin("session-a", "alice", "project = A", {}, "", expires_at=100)
    second = repo.begin("session-b", "bob", "project = B", {}, "", expires_at=100)
    repo.write_batch(first, [issue("A-1")]); repo.activate(first)
    repo.write_batch(second, [issue("B-1")]); repo.activate(second)

    assert repo.state("session-a", "alice")["activeJql"] == "project = A"
    assert repo.issue_keys("session-a", "alice") == ["A-1"]
    assert repo.issue_keys("session-b", "bob") == ["B-1"]
    assert len(repo.statistics_issues("session-a", "alice")) == 1
    assert repo.statistics_issues("session-a", "bob") == []
    assert repo.statistics_issues("unknown", "alice") == []
    assert repo.state("session-a", "alice")["userJql"] is None


def test_stale_generation_cannot_replace_active_snapshot(tmp_path):
    repo = JiraAnalyticsRepository(WebDatabase(tmp_path / "web.db"), now=lambda: 10)
    old = repo.begin("s", "alice", "old", {}, "", expires_at=100)
    new = repo.begin("s", "alice", "new", {}, "", expires_at=100)
    repo.write_batch(old, [issue("OLD-1")]); repo.write_batch(new, [issue("NEW-1")])

    assert repo.activate(old) is False
    assert repo.activate(new) is True
    assert repo.issue_keys("s", "alice") == ["NEW-1"]


def test_failed_or_cancelled_pending_query_preserves_active_snapshot(tmp_path):
    repo = JiraAnalyticsRepository(WebDatabase(tmp_path / "web.db"), now=lambda: 10)
    active = repo.begin("s", "alice", "good", {}, "", expires_at=100)
    repo.write_batch(active, [issue("GOOD-1")]); repo.activate(active)

    failed = repo.begin("s", "alice", "bad", {}, "", expires_at=100)
    repo.finish(failed, "failed", "offline")
    cancelled = repo.begin("s", "alice", "cancel", {}, "", expires_at=100)
    repo.finish(cancelled, "cancelled")

    assert repo.state("s", "alice")["activeJql"] == "good"
    assert repo.issue_keys("s", "alice") == ["GOOD-1"]
    assert len(repo.statistics_issues("s", "alice")) == 1


def test_delete_session_and_expiry_remove_analytics_snapshots(tmp_path):
    clock = [10]
    repo = JiraAnalyticsRepository(WebDatabase(tmp_path / "web.db"), now=lambda: clock[0])
    repo.begin("expired", "alice", "x", {}, "", expires_at=11)
    repo.begin("deleted", "alice", "y", {}, "", expires_at=100)
    clock[0] = 12
    repo.cleanup()
    repo.delete_session("deleted")

    assert repo.state("expired", "alice")["pendingSnapshotId"] == ""
    assert repo.state("deleted", "alice")["pendingSnapshotId"] == ""
    assert repo.statistics_issues("expired", "alice") == []
    assert repo.statistics_issues("deleted", "alice") == []


def test_effective_jql_and_empty_user_draft_remain_distinct_after_reopening_database(tmp_path):
    database = WebDatabase(tmp_path / "web.db")
    repo = JiraAnalyticsRepository(database, now=lambda: 10)
    snapshot = repo.begin("s", "alice", 'channel = "Self-Test"', {}, "", expires_at=100, user_jql="")
    repo.activate(snapshot)
    restored = JiraAnalyticsRepository(database, now=lambda: 10).state("s", "alice")
    assert restored["activeJql"] == 'channel = "Self-Test"'
    assert restored["userJql"] == ""
    failed = repo.begin("s", "alice", "bad", {}, "", expires_at=100, user_jql="bad")
    repo.finish(failed, "failed", "offline")
    state = repo.state("s", "alice")
    assert state["latestState"] == "failed"
    assert state["error"] == "offline"
    assert state["activeJql"] == 'channel = "Self-Test"'


def test_card_scopes_do_not_replace_each_others_sqlite_results_or_published_conditions(tmp_path):
    repo = JiraAnalyticsRepository(WebDatabase(tmp_path / "web.db"), now=lambda: 10)
    conditions = {"mode": "basic", "basic": {"project": ["A"]}}
    repo.publish_conditions("s", "alice", conditions, expires_at=100)
    first = repo.begin("s", "alice", "scope A", {}, "", expires_at=100, card_key="first")
    second = repo.begin("s", "alice", "scope B", {}, "", expires_at=100, card_key="second")
    repo.write_batch(first, [issue("A-1")]); repo.activate(first)
    repo.write_batch(second, [issue("B-1")]); repo.activate(second)
    assert repo.issue_keys("s", "alice", card_key="first") == ["A-1"]
    assert repo.issue_keys("s", "alice", card_key="second") == ["B-1"]
    assert repo.issue_keys("s", "bob", card_key="first") == []
    assert repo.published_conditions("s", "alice") == conditions
    old = repo.begin("s", "alice", "old A", {}, "", expires_at=100, card_key="first")
    new = repo.begin("s", "alice", "new A", {}, "", expires_at=100, card_key="first")
    assert repo.activate(old) is False
    assert repo.state("s", "alice", card_key="first")["pendingSnapshotId"] == new
    assert repo.issue_keys("s", "alice", card_key="second") == ["B-1"]
    repo.delete_session("s")
    assert repo.state("relogin", "alice", card_key="first")["activeSnapshotId"] == first
    assert repo.published_conditions("relogin", "alice") == conditions


def test_account_card_replay_survives_session_expiry_but_does_not_expose_other_session_task(tmp_path):
    clock = [10]
    repo = JiraAnalyticsRepository(WebDatabase(tmp_path / "web.db"), now=lambda: clock[0])
    snapshot = repo.begin("old-session", "alice", "scope", {}, "", expires_at=11,
                          user_jql="user", card_key="self-test")
    repo.write_batch(snapshot, [issue("A-1")]); repo.activate(snapshot)
    pending = repo.begin("old-session", "alice", "new", {}, "", expires_at=11, card_key="self-test")
    repo.set_task(pending, "secret-task", session_hash="old-session")
    clock[0] = 12; repo.cleanup()
    replay = repo.state("new-session", "alice", card_key="self-test")
    assert replay["activeJql"] == "scope"
    assert replay["pendingSnapshotId"] == pending
    assert replay["taskId"] == ""
    assert repo.state("old-session", "alice", card_key="self-test")["taskId"] == "secret-task"
    assert repo.issue_keys("new-session", "alice", card_key="self-test") == ["A-1"]
    assert repo.issue_keys("new-session", "bob", card_key="self-test") == []


def test_legacy_dashboard_migrates_exact_valid_counts_once_without_fabricating_issue_ids(tmp_path):
    database = WebDatabase(tmp_path / 'web.db')
    repo = JiraAnalyticsRepository(database, now=lambda: 10)
    roster = QARoster(('qa',), 'current')
    fixed = self_test_jira_conditions(roster.accounts)
    seed_dashboard(database, 'alice', fingerprint='current', jql=fixed)
    seed_dashboard(database, 'old-roster', fingerprint='old', jql=fixed)
    seed_dashboard(database, 'old-query', fingerprint='current', jql='issuetype = Bug')
    repo.migrate_self_test(roster)
    state = repo.state('relogin', 'alice', card_key='self-test')
    assert state['activeJql'] == fixed
    assert state['userJql'] == ''
    assert state['rosterFingerprint'] == 'current'
    summary = repo.statistics_summary('relogin', 'alice', card_key='self-test')
    assert summary['teamTotal'] == 5370
    assert summary['unmappedCount'] == 360
    assert summary['productLines'][0]['people'][0]['bugCount'] == 5010
    assert repo.issue_keys('relogin', 'alice', card_key='self-test') == []
    assert repo.published_conditions('relogin', 'alice')['userJql'] == ''
    assert repo.state('s', 'old-roster', card_key='self-test')['activeSnapshotId'] == ''
    assert repo.state('s', 'old-query', card_key='self-test')['activeSnapshotId'] == ''
    repo.migrate_self_test(roster)
    assert repo.state('another', 'alice', card_key='self-test')['activeSnapshotId'] == state['activeSnapshotId']
    repo.delete_account('alice'); repo.migrate_self_test(roster)
    assert repo.state('s', 'alice', card_key='self-test')['activeSnapshotId'] == ''
    with database.connect() as connection:
        assert connection.execute("SELECT team_total FROM jira_team_bug_snapshots WHERE account='alice'").fetchone()[0] == 5370


def test_valid_legacy_analytics_collection_takes_precedence_and_new_query_replaces_summary(tmp_path):
    database = WebDatabase(tmp_path / 'web.db')
    repo = JiraAnalyticsRepository(database, now=lambda: 10)
    roster = QARoster(('qa',), 'current')
    fixed = self_test_jira_conditions(roster.accounts)
    seed_dashboard(database, 'alice', fingerprint='current', jql=fixed)
    snapshot = repo.begin('old', 'alice', fixed, {}, '', expires_at=11, user_jql='', card_key='self-test')
    repo.write_batch(snapshot, [issue('A-1')]); repo.activate(snapshot)
    with database.transaction() as connection:
        scope = 'old:card:self-test'
        connection.execute("INSERT INTO jira_analytics_queries(session_hash,account,active_snapshot_id,expires_at,card_key) VALUES(?,'alice',?,11,'self-test')", (scope, snapshot))
        connection.execute('UPDATE jira_analytics_snapshots SET session_hash=? WHERE snapshot_id=?', (scope, snapshot))
        connection.execute("DELETE FROM jira_analytics_queries WHERE session_hash='account:alice:card:self-test'")
    repo.migrate_self_test(roster)
    assert repo.issue_keys('new', 'alice', card_key='self-test') == ['A-1']
    assert repo.statistics_summary('new', 'alice', card_key='self-test') is None
    assert repo.state('new', 'alice', card_key='self-test')['rosterFingerprint'] == 'current'
    repo.delete_account('alice'); repo.migrate_self_test(roster)
    assert repo.state('new', 'alice', card_key='self-test')['activeSnapshotId'] == ''

    seed_dashboard(database, 'bob', fingerprint='current', jql=fixed)
    repo.migrate_self_test(roster)
    new = repo.begin('s', 'bob', fixed, {}, '', expires_at=11, user_jql='', card_key='self-test', roster_fingerprint='current')
    repo.write_batch(new, [issue('B-1')]); repo.activate(new)
    assert repo.statistics_summary('s', 'bob', card_key='self-test') is None
    assert repo.issue_keys('new-login', 'bob', card_key='self-test') == ['B-1']
