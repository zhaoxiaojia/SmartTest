from fastapi.testclient import TestClient
import time
import pytest
from threading import Event
from core.async_tasks import TaskCancelled
from smarttest_web.database import WebDatabase
from smarttest_web.jira.analytics_repository import JiraAnalyticsRepository

from core.product_lines import PRODUCT_LINES
from core.jira.services.team_bug_service import load_fae_qa_roster, self_test_jira_conditions, QARoster

from smarttest_web.app import create_app
from smarttest_web.session import PersistentSessionStore
from test_web_session import FakeAuthenticator


class FilterOwner:
    def fields(self): return [{"id": "customfield_1", "name": "Team", "control": "advanced", "queryable": False, "options": [], "schema": {}}]
    def saved_filters(self): return [{"id": "7", "name": "Mine", "owner": "Coco"}]
    def saved_filter(self, value): return {"id": value, "name": "Mine", "jql": "project = SH"}
    def validate(self, jql):
        valid = jql != "bad" and not jql.startswith("(bad)")
        return {"valid": valid, "errors": [] if valid else ["Bad JQL"]}
    def suggestions(self, field_name, query):
        return [{"value": f"{field_name}:1", "displayName": query or "All"}]


class Gateway:
    def search_all_payloads(self, _jql, *, progress=None): return []


def client(tmp_path):
    app = create_app(
        authenticator=FakeAuthenticator,
        session_store=lambda: PersistentSessionStore(tmp_path / "web.db"),
        jira_filter_owner=lambda _u, _p: (FilterOwner(), Gateway()),
    )
    result = TestClient(app, base_url="https://testserver")
    result.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    return result


def query_card(api, payload):
    published = api.post("/api/jira/analytics/search", json=payload)
    return api.post("/api/jira/cards/self-test/query") if published.json().get("applied") else published


def wait_terminal(api, task_id):
    for _ in range(100):
        task = api.get(f"/api/jira/cards/self-test/tasks/{task_id}").json()
        if task["state"] not in {"queued", "running"}:
            return task["state"]
        time.sleep(0.01)
    raise AssertionError("query did not finish")


def test_public_search_only_publishes_conditions_and_card_queries_its_own_effective_scope(tmp_path, monkeypatch):
    queries = []
    monkeypatch.setattr(Gateway, "search_all_payloads", lambda _self, jql, **_kw: queries.append(jql) or [])
    api = client(tmp_path)
    published = api.post("/api/jira/analytics/search", json={"mode": "basic", "basic": {}}).json()
    assert published["applied"] is True
    assert "taskId" not in published
    assert queries == []
    started = api.post("/api/jira/cards/self-test/query", json={"jql": "", "fixed_conditions": ""}).json()
    assert started["validation"]["valid"] is True
    assert wait_terminal(api, started["taskId"]) == "completed"
    assert queries == [self_test_jira_conditions(load_fae_qa_roster().accounts)]
    assert 'reporter IN (' in queries[0]
    assert 'assignee IN (' not in queries[0]
    assert api.post("/api/jira/cards/customer/query").status_code == 404
    replay = api.get("/api/jira/cards/self-test/statistics").json()
    assert replay["state"] == "ready"
    assert len(queries) == 1


def test_empty_qa_roster_does_not_query_unbounded_self_test_data(tmp_path, monkeypatch):
    queries = []
    monkeypatch.setattr('core.jira.services.team_bug_service.load_fae_qa_roster', lambda: QARoster((), 'empty'))
    monkeypatch.setattr(Gateway, 'search_all_payloads', lambda _self, jql, **_kwargs: queries.append(jql) or [])
    api = client(tmp_path)
    response = query_card(api, {"mode": "basic", "basic": {}})
    assert response.status_code == 422
    assert response.json()["detail"]["state"] == "empty_fae_qa_roster"
    assert queries == []


def test_old_snapshot_without_qa_reporter_boundary_is_not_replayed_or_requeried(tmp_path, monkeypatch):
    queries = []
    api = client(tmp_path)
    api.post('/api/jira/analytics/search', json={'mode': 'basic', 'basic': {}})
    database = WebDatabase(tmp_path / 'web.db')
    with database.connect() as connection:
        session_hash = connection.execute("SELECT session_hash FROM jira_analytics_queries WHERE card_key=''").fetchone()[0]
    repository = JiraAnalyticsRepository(database)
    old = repository.begin(session_hash, 'coco', '"Channel of Reporter" = "Self-Test"', {}, '',
                           expires_at=time.time() + 100, user_jql='', card_key='self-test')
    repository.activate(old)
    monkeypatch.setattr(Gateway, 'search_all_payloads', lambda _self, jql, **_kwargs: queries.append(jql) or [])
    replay = api.get('/api/jira/cards/self-test/statistics').json()
    assert replay['state'] == 'no_snapshot'
    assert 'productLines' not in replay
    assert queries == []


def test_effective_bug_query_validation_execution_sqlite_and_explicit_unmapped_total_match(tmp_path, monkeypatch):
    validated, executed = [], []
    def validate(_self, jql):
        validated.append(jql)
        return {"valid": True, "errors": []}
    candidates = []
    for index, (kind, project, reporter) in enumerate([
        ('Bug', PRODUCT_LINES[0].jira_project_keys[0], 'fan.xu'),
        ('Bug', 'unknown', 'meng.wang1'),
        ('Task', PRODUCT_LINES[2].jira_project_keys[0], 'meng.wang1'),
        ('Epic', PRODUCT_LINES[2].jira_project_keys[0], 'meng.wang1'),
    ]):
        candidates.append({'id': str(index), 'key': f'ISSUE-{index}', 'fields': {
            'summary': kind, 'issuetype': {'name': kind}, 'project': {'key': project},
            'reporter': {'name': reporter, 'displayName': reporter},
        }})
    def collect(_self, jql, *, progress=None):
        executed.append(jql)
        assert jql == validated[-1]
        assert 'issuetype = Bug' in jql
        rows = [row for row in candidates if row['fields']['issuetype']['name'] == 'Bug']
        if progress: progress(len(rows), len(rows))
        return rows
    monkeypatch.setattr(FilterOwner, 'validate', validate)
    monkeypatch.setattr(Gateway, 'search_all_payloads', collect)
    api = client(tmp_path)
    user = 'reporter = "meng.wang1" OR reporter = "fan.xu" ORDER BY created DESC'
    started = query_card(api, {'mode': 'advanced', 'jql': user}).json()
    assert wait_terminal(api, started['taskId']) == 'completed'
    statistics = api.get('/api/jira/cards/self-test/statistics').json()
    with WebDatabase(tmp_path / 'web.db').connect() as connection:
        saved = connection.execute('SELECT count(*) FROM jira_analytics_snapshot_issues').fetchone()[0]
        effective = connection.execute("SELECT jql FROM jira_analytics_snapshots WHERE card_key='self-test'").fetchone()[0]
    displayed = sum(person['bugCount'] for line in statistics['productLines'] for person in line['people'])
    assert saved == statistics['teamTotal'] == 2
    assert saved == displayed + statistics['unmappedCount'] + statistics['unassignedCount']
    assert statistics['unmappedCount'] == 0
    assert statistics['productLines'][4]['people'][0]['identity'] == 'meng.wang1'
    assert statistics['productLines'][4]['people'][0]['bugCount'] == 1
    assert effective == executed[0] == validated[-1]
    assert effective.startswith('(reporter = "meng.wang1" OR reporter = "fan.xu") AND (issuetype = Bug')
    assert effective.endswith('ORDER BY created DESC')

@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
@pytest.mark.parametrize("previous", [False, True])
def test_statistics_exposes_query_terminal_state_and_retains_previous_snapshot(tmp_path, monkeypatch, terminal, previous):
    api = client(tmp_path)
    if previous:
        initial = query_card(api, {"mode": "basic", "basic": {}}).json()
        assert wait_terminal(api, initial["taskId"]) == "completed"
    def broken(_self, _jql, *, progress=None):
        raise TaskCancelled() if terminal == "cancelled" else RuntimeError("offline")
    monkeypatch.setattr(Gateway, "search_all_payloads", broken)
    started = query_card(api, {"mode": "advanced", "jql": "project = A"}).json()
    assert wait_terminal(api, started["taskId"]) == terminal
    payload = api.get("/api/jira/cards/self-test/statistics").json()
    assert payload["state"] == terminal
    assert payload["error"]
    assert ("productLines" in payload) is previous


def test_lost_task_is_interrupted_without_requery_and_previous_progress_does_not_finish_new_task(tmp_path, monkeypatch):
    api = client(tmp_path)
    first = query_card(api, {"mode": "basic", "basic": {}}).json()
    assert wait_terminal(api, first["taskId"]) == "completed"
    statistics = api.get("/api/jira/cards/self-test/statistics").json()
    assert statistics["state"] == "ready"
    assert statistics["teamTotal"] == 0
    restored = api.get("/api/jira/cards/self-test/statistics").json()["query"]
    assert restored["activeJql"] == self_test_jira_conditions(load_fae_qa_roster().accounts)
    assert restored["userJql"] == ""
    entered, release = Event(), Event()
    def blocked(_self, _jql, *, progress=None):
        entered.set()
        assert release.wait(3)
        return []
    monkeypatch.setattr(Gateway, "search_all_payloads", blocked)
    current = query_card(api, {"mode": "basic", "basic": {}}).json()
    try:
        assert entered.wait(1)
        assert api.get(f"/api/jira/cards/self-test/tasks/{first['taskId']}").status_code == 404
        assert api.get("/api/jira/cards/self-test/statistics").json()["state"] == "loading"
        assert api.get("/api/jira/cards/self-test/statistics").json()["query"]["pendingSnapshotId"] == current["snapshotId"]
    finally:
        release.set()
    assert wait_terminal(api, current["taskId"]) == "completed"
    database = WebDatabase(tmp_path / "web.db")
    with database.connect() as connection:
        session_hash, account, expires = connection.execute(
            "SELECT session_hash,account,expires_at FROM jira_analytics_queries WHERE card_key=\'\'").fetchone()
    repo = JiraAnalyticsRepository(database)
    snapshot = repo.begin(session_hash, account, "scope", {}, "", expires_at=expires, user_jql="", card_key="self-test")
    repo.set_task(snapshot, "lost-process-task")
    payload = api.get("/api/jira/cards/self-test/statistics").json()
    assert payload["state"] == "failed"
    assert payload["error"] == "query_interrupted"
    assert "productLines" in payload
    assert api.get("/api/jira/cards/self-test/statistics").json()["query"]["pendingSnapshotId"] == ""


def test_app_restart_interrupts_legacy_pending_without_task_id_and_preserves_active_snapshot(tmp_path):
    api = client(tmp_path)
    first = query_card(api, {"mode": "basic", "basic": {}}).json()
    assert wait_terminal(api, first["taskId"]) == "completed"
    database = WebDatabase(tmp_path / "web.db")
    with database.connect() as connection:
        session_hash, account, expires = connection.execute(
            "SELECT session_hash,account,expires_at FROM jira_analytics_queries").fetchone()
    repo = JiraAnalyticsRepository(database)
    repo.begin(session_hash, account, "unfinished", {}, "", expires_at=expires, card_key="self-test")
    assert repo.state(session_hash, account, card_key="self-test")["taskId"] == ""
    create_app(authenticator=FakeAuthenticator,
               session_store=lambda: PersistentSessionStore(tmp_path / "web.db"))
    restored = repo.state(session_hash, account, card_key="self-test")
    assert restored["pendingSnapshotId"] == ""
    assert restored["activeSnapshotId"] == first["snapshotId"]
    assert restored["latestState"] == "failed"
    assert restored["error"] == "query_interrupted"


def test_analytics_endpoints_are_independent_and_search_starts_task(tmp_path):
    api = client(tmp_path)

    assert api.get("/api/jira/analytics/fields").json()["more"][0]["id"] == "customfield_1"
    assert api.get("/api/jira/analytics/suggestions", params={"fieldName": "status", "query": "op"}).json() == [
        {"value": "status:1", "displayName": "op"},
    ]
    assert api.get("/api/jira/analytics/saved-filters").json()[0]["id"] == "7"
    assert api.get("/api/jira/analytics/saved-filters/7").json()["jql"] == "project = SH"
    invalid = query_card(api, {"mode": "advanced", "jql": "bad"})
    assert invalid.json()["validation"]["valid"] is False
    started = query_card(api, {"mode": "advanced", "jql": "project = SH"})
    assert started.status_code == 200
    task_id = started.json()["taskId"]
    assert api.get(f"/api/jira/cards/self-test/tasks/{task_id}").status_code == 200
    assert api.delete(f"/api/jira/cards/self-test/tasks/{task_id}").json() == {"cancelled": True}
    assert api.get("/api/jira/filter-snapshot").json()["snapshot"] is None


def test_analytics_state_is_not_visible_to_another_account(tmp_path):
    first = client(tmp_path)
    query_card(first, {"mode": "advanced", "jql": "project = SH"})
    first.post("/api/auth/logout")
    first.post("/api/auth/login", json={"username": "other", "password": "secret"})

    assert first.get("/api/jira/analytics/state").json()["conditions"] is None
    assert first.get("/api/jira/cards/self-test/statistics").json() == {"state": "no_snapshot"}


def test_statistics_replays_only_the_applied_jql_collection_without_extra_scope(tmp_path, monkeypatch):
    queries = []
    project = PRODUCT_LINES[0].jira_project_keys[0]
    def search(_self, jql, *, progress=None):
        queries.append(jql)
        return [{"id": "1", "key": "ONE-1", "fields": {
            "summary": "One", "project": {"id": "1", "key": project, "name": "One"},
            "issuetype": {"id": "2", "name": "Bug"}, "status": {"id": "1", "name": "Open"},
            "reporter": {"name": "fan.xu", "displayName": "Fan Xu"},
            "assignee": {"name": "outside.qa", "displayName": "Outside QA"},
            "priority": {"id": "1", "name": "P0"}, "resolution": {"id": "1", "name": "Resolved"},
        }}] if jql.startswith("(first)") else []
    monkeypatch.setattr(Gateway, "search_all_payloads", search)
    api = client(tmp_path)
    assert api.get("/api/jira/cards/self-test/statistics").json() == {"state": "no_snapshot"}
    def apply(jql):
        task_id = query_card(api, {"mode": "advanced", "jql": jql}).json()["taskId"]
        assert wait_terminal(api, task_id) == "completed"
    apply("first")
    payload = api.get("/api/jira/cards/self-test/statistics").json()
    assert payload["state"] == "ready"
    assert payload["teamTotal"] == 1
    assert payload["productLines"][0]["people"] == [{"identity": "fan.xu", "displayName": "Fan Xu",
        "bugCount": 1, "resolvedCount": 1, "p0Count": 1, "invalidCount": 0}]
    apply("second")
    assert api.get("/api/jira/cards/self-test/statistics").json()["teamTotal"] == 0
    fixed = self_test_jira_conditions(load_fae_qa_roster().accounts)
    assert queries == [f'(first) AND ({fixed})', f'(second) AND ({fixed})']


def test_suggestions_resolve_the_current_sessions_jira_credentials_on_every_request(tmp_path):
    calls = []

    class AccountAuthenticator:
        def authenticate(self, username, _password):
            return {"success": True, "username": username, "display_name": username, "avatar_bytes": b""}

    def owner(username, password):
        calls.append((username, password))
        return FilterOwner(), Gateway()

    app = create_app(
        authenticator=AccountAuthenticator,
        session_store=lambda: PersistentSessionStore(tmp_path / "web.db"),
        jira_filter_owner=owner,
    )
    api = TestClient(app, base_url="https://testserver")
    api.post("/api/auth/login", json={"username": "alice", "password": "first"})
    api.get("/api/jira/analytics/suggestions", params={"fieldName": "status"})
    api.post("/api/auth/logout")
    api.post("/api/auth/login", json={"username": "bob", "password": "second"})
    api.get("/api/jira/analytics/suggestions", params={"fieldName": "status"})

    assert calls == [("alice", "first"), ("bob", "second")]
