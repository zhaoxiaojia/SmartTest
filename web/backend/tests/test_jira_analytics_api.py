from fastapi.testclient import TestClient
import time
from datetime import date
from copy import deepcopy
import pytest
from threading import Event
from core.async_tasks import TaskCancelled
from smarttest_web.database import WebDatabase
from smarttest_web.jira.analytics_repository import JiraAnalyticsRepository

from core.product_lines import PRODUCT_LINES
from core.jira.services.jql_statistics_cards import card_definition


def self_test_jira_conditions(period="year"):
    return card_definition("self-test").fixed_jql(period)

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
    def search_all_payloads(self, _jql, *, fields=None, expand=None, page_size=None, progress=None): return []
    def user_groups(self, account):
        return {
            "meng.wang1": ("fae-wifi-qa",),
            "fan.xu": ("fae-iptv-qa",),
        }[account]


def client(tmp_path):
    class AccountAuthenticator(FakeAuthenticator):
        def authenticate(self, username, password):
            return {**super().authenticate(username, password), 'username': username}
    app = create_app(
        authenticator=AccountAuthenticator,
        session_store=lambda: PersistentSessionStore(tmp_path / "web.db"),
        jira_filter_owner=lambda _u, _p: (FilterOwner(), Gateway()),
    )
    result = TestClient(app, base_url="https://testserver")
    result.post("/api/auth/login", json={"username": "coco", "password": "secret"})
    return result


def query_card(api, payload):
    published = api.post("/api/jira/analytics/search", json=payload)
    return api.post("/api/jira/cards/self-test/query", json={"period": "year"}) if published.json().get("applied") else published


def dated_rows(rows, query):
    year = date.today().year - (1 if f'created >= "{date.today().year - 1}-01-01"' in query else 0)
    result = deepcopy(rows)
    for row in result:
        row['id'] = f"{row['id']}-{year}"
        row['key'] = f"{row['key']}-{year}"
        row.setdefault('fields', {})['created'] = f"{year}-01-01T00:00:00+08:00"
    return result


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
    assert queries[0] == self_test_jira_conditions()
    assert len(queries) == 4
    assert 'creator IN membersOf("fae-wifi-qa")' in queries[0]
    assert 'reporter IN (' not in queries[0]
    assert 'assignee IN (' not in queries[0]
    assert api.post("/api/jira/cards/unknown/query").status_code == 404
    replay = api.get("/api/jira/cards/self-test/statistics").json()
    assert replay["state"] == "ready"
    assert len(queries) == 4


@pytest.mark.parametrize("card_key,expected", [
    ("self-test", "issuetype = Bug"),
    ("task", "issuetype = Task"),
    ("customer-feedback", '"Channel of Reporter" = "Customer-Feedback"'),
])
def test_registered_cards_share_query_task_and_snapshot_flow(tmp_path, monkeypatch, card_key, expected):
    queries = []
    monkeypatch.setattr(Gateway, "search_all_payloads", lambda _self, jql, **_kw: queries.append(jql) or [])
    api = client(tmp_path)
    api.post("/api/jira/analytics/search", json={"mode": "basic", "basic": {}})
    assert api.get(f"/api/jira/cards/{card_key}/statistics").json()["state"] == "no_snapshot"
    started = api.post(f"/api/jira/cards/{card_key}/query", json={"period": "year"}).json()
    for _ in range(100):
        task = api.get(f"/api/jira/cards/{card_key}/tasks/{started['taskId']}").json()
        if task["state"] not in {"queued", "running"}:
            break
        time.sleep(.01)
    assert task["state"] == "completed"
    assert expected in queries[0]
    replay = api.get(f"/api/jira/cards/{card_key}/statistics").json()
    assert replay["state"] == "ready"


def test_creator_group_failure_is_explicit_and_preserves_previous_snapshot(tmp_path, monkeypatch):
    api = client(tmp_path)
    previous = query_card(api, {"mode": "basic", "basic": {}}).json()
    assert wait_terminal(api, previous["taskId"]) == "completed"
    monkeypatch.setattr(Gateway, 'user_groups', lambda _self, _account: (_ for _ in ()).throw(RuntimeError('offline')))
    monkeypatch.setattr(Gateway, 'search_all_payloads', lambda _self, _jql, **_kwargs: [{
        "id": "1", "key": "TV-1", "fields": {"project": {"key": "TV"}, "issuetype": {"name": "Bug"},
        "creator": {"name": "fan.xu", "displayName": "Fan Xu"},
    }}])
    started = query_card(api, {"mode": "basic", "basic": {}}).json()
    assert wait_terminal(api, started["taskId"]) == "failed"
    response = api.get("/api/jira/cards/self-test/statistics").json()
    assert response["state"] == "failed"
    assert response["error"] == "RuntimeError"
    assert response["teamTotal"] == 0


def test_old_snapshot_without_qa_creator_group_boundary_is_not_replayed_or_requeried(tmp_path, monkeypatch):
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
            'creator': {'name': reporter, 'displayName': reporter},
        }})
    def collect(_self, jql, *, fields=None, expand=None, page_size=None, progress=None):
        executed.append(jql)
        assert 'issuetype = Bug' in jql
        rows = [row for row in candidates if row['fields']['issuetype']['name'] == 'Bug']
        if progress: progress(len(rows), len(rows))
        return dated_rows(rows, jql)
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
    assert saved == 4
    assert statistics['teamTotal'] == 2
    assert statistics['teamTotal'] == displayed + statistics['unmappedCount'] + statistics['unassignedCount']
    assert statistics['unmappedCount'] == 0
    assert statistics['productLines'][4]['people'][0]['identity'] == 'meng.wang1'
    assert statistics['productLines'][4]['people'][0]['bugCount'] == 1
    assert effective == executed[0] == validated[1]
    assert effective.startswith('(reporter = "meng.wang1" OR reporter = "fan.xu") AND (')
    assert 'issuetype = Bug' in effective
    assert effective.endswith('ORDER BY created DESC')

@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
@pytest.mark.parametrize("previous", [False, True])
def test_statistics_exposes_query_terminal_state_and_retains_previous_snapshot(tmp_path, monkeypatch, terminal, previous):
    api = client(tmp_path)
    if previous:
        initial = query_card(api, {"mode": "basic", "basic": {}}).json()
        assert wait_terminal(api, initial["taskId"]) == "completed"
    def broken(_self, _jql, *, fields=None, expand=None, page_size=None, progress=None):
        raise TaskCancelled() if terminal == "cancelled" else RuntimeError("offline")
    monkeypatch.setattr(Gateway, "search_all_payloads", broken)
    started = query_card(api, {"mode": "basic", "basic": {}}).json()
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
    assert restored["activeSnapshotId"] == first["snapshotId"]
    entered, release = Event(), Event()
    def blocked(_self, _jql, *, fields=None, expand=None, page_size=None, progress=None):
        entered.set()
        assert release.wait(3)
        return []
    monkeypatch.setattr(Gateway, "search_all_payloads", blocked)
    current = query_card(api, {"mode": "advanced", "jql": "project = A"}).json()
    try:
        assert entered.wait(1)
        assert api.get(f"/api/jira/cards/self-test/tasks/{first['taskId']}").status_code == 404
        assert api.get("/api/jira/cards/self-test/statistics").json()["state"] == "loading"
        loading = api.get("/api/jira/cards/self-test/statistics").json()
        assert loading["query"]["pendingSnapshotId"] == current["snapshotId"]
        assert loading["query"]["activeSnapshotId"] == first["snapshotId"]
    finally:
        release.set()
    assert wait_terminal(api, current["taskId"]) == "completed"
    completed = api.get("/api/jira/cards/self-test/statistics").json()["query"]
    assert completed["activeSnapshotId"] == current["snapshotId"]
    database = WebDatabase(tmp_path / "web.db")
    with database.connect() as connection:
        session_hash, account, expires = connection.execute(
            "SELECT session_hash,account,expires_at FROM jira_analytics_queries WHERE card_key=\'\'").fetchone()
    repo = JiraAnalyticsRepository(database)
    active = repo.state(session_hash, account, card_key="self-test")
    snapshot = repo.begin(session_hash, account, active["activeJql"], {}, "", expires_at=expires,
                          user_jql=active["userJql"], card_key="self-test", roster_fingerprint=active["rosterFingerprint"],
                          comparison_jql=active["activeComparisonJql"])
    from smarttest_web.app import _session_owner
    repo.set_task(snapshot, "lost-process-task", session_hash=_session_owner(api.cookies.get('smarttest_session')))
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
    assert first.get("/api/jira/cards/self-test/statistics").json() == {"state": "no_snapshot", "period": "month"}


def test_statistics_replays_only_the_applied_jql_collection_without_extra_scope(tmp_path, monkeypatch):
    queries = []
    project = PRODUCT_LINES[0].jira_project_keys[0]
    def search(_self, jql, *, fields=None, expand=None, page_size=None, progress=None):
        queries.append(jql)
        return dated_rows([{"id": "1", "key": "ONE-1", "fields": {
            "summary": "One", "project": {"id": "1", "key": project, "name": "One"},
            "issuetype": {"id": "2", "name": "Bug"}, "status": {"id": "1", "name": "Open"},
            "reporter": {"name": "outside", "displayName": "Outside"},
            "creator": {"name": "fan.xu", "displayName": "Fan Xu"},
            "assignee": {"name": "outside.qa", "displayName": "Outside QA"},
            "priority": {"id": "1", "name": "P0"}, "resolution": {"id": "1", "name": "Resolved"},
        }}], jql) if jql.startswith("(first)") else []
    monkeypatch.setattr(Gateway, "search_all_payloads", search)
    api = client(tmp_path)
    assert api.get("/api/jira/cards/self-test/statistics").json() == {"state": "no_snapshot", "period": "month"}
    def apply(jql):
        task_id = query_card(api, {"mode": "advanced", "jql": jql}).json()["taskId"]
        assert wait_terminal(api, task_id) == "completed"
    apply("first")
    payload = api.get("/api/jira/cards/self-test/statistics").json()
    assert payload["state"] == "ready"
    assert payload["teamTotal"] == 1
    assert payload["productLines"][0]["people"] == [{"identity": "fan.xu", "displayName": "Fan Xu",
        "bugCount": 1, "commentCount": 0, "verifyCount": 0, "invalidCount": 0}]
    monkeypatch.setattr(Gateway, "user_groups", lambda _self, _account: (_ for _ in ()).throw(AssertionError("reuse queried Jira")))
    reused = api.post("/api/jira/cards/self-test/query", json={"intent": "reuse"}).json()
    assert reused["state"] == "ready"
    monkeypatch.setattr(Gateway, "user_groups", lambda self, account: {
        "meng.wang1": ("fae-wifi-qa",), "fan.xu": ("fae-iptv-qa",),
    }[account])
    apply("second")
    assert api.get("/api/jira/cards/self-test/statistics").json()["teamTotal"] == 0
    fixed = self_test_jira_conditions()
    assert queries[0] == f'(first) AND ({fixed})'
    assert queries[4] == f'(second) AND ({fixed})'
    assert len(queries) == 8


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


@pytest.mark.parametrize("card_key", ["self-test", "task", "customer-feedback"])
def test_cards_exclude_non_qa_at_task_aggregation_and_reject_old_aggregation_snapshot(tmp_path, monkeypatch, card_key):
    executed = []
    rows = [{"id": str(index), "key": f"TV-{index}", "fields": {
        "project": {"key": "TV"}, "issuetype": {"name": "Bug"},
        "creator": {"name": account, "displayName": account}, "labels": ["Customer_W1"],
    }} for index, account in enumerate(["qa", "outside", "wifi"], 1)]
    monkeypatch.setattr(Gateway, "search_all_payloads", lambda _self, jql, **_kw: executed.append(jql) or dated_rows(rows, jql))
    monkeypatch.setattr(Gateway, "user_groups", lambda _self, account: {
        "qa": ("fae-tv-qa",), "outside": ("jira-users",), "wifi": ("fae-wifi-qa",),
    }[account])
    api = client(tmp_path)
    api.post("/api/jira/analytics/search", json={"mode": "advanced", "jql": "status = Open ORDER BY created DESC"})
    started = api.post(f"/api/jira/cards/{card_key}/query", json={"period": "year"}).json()
    for _ in range(100):
        task = api.get(f"/api/jira/cards/{card_key}/tasks/{started['taskId']}").json()
        if task["state"] not in {"queued", "running"}: break
        time.sleep(.01)
    assert task["state"] == "completed"
    assert len(executed) == 4
    from core.jira.services.jql_statistics_cards import FAE_QA_GROUPS
    for query in executed:
        assert all(f'creator IN membersOf("{group}")' in query for group in FAE_QA_GROUPS)
        assert query.endswith("ORDER BY created DESC")
    replay = api.get(f"/api/jira/cards/{card_key}/statistics").json()
    for period in ["current", "previous"]:
        summary = replay[period]
        assert {person["identity"] for line in summary["productLines"] for person in line["people"]} == {"qa", "wifi"}
        assert summary["teamTotal"] == 2
        assert summary["productLines"][2]["people"][0]["identity"] == "qa"
        assert summary["productLines"][4]["people"][0]["identity"] == "wifi"
    with WebDatabase(tmp_path / "web.db").transaction() as connection:
        connection.execute("UPDATE jira_analytics_snapshots SET roster_fingerprint='old-aggregation' WHERE snapshot_id=?", (started["snapshotId"],))
    stale = api.get(f"/api/jira/cards/{card_key}/statistics").json()
    assert stale["state"] == "no_snapshot"
    assert "productLines" not in stale
    assert len(executed) == 4
    missing = api.post(f"/api/jira/cards/{card_key}/query", json={"intent": "reuse"}).json()
    assert missing["state"] == "no_snapshot" and "taskId" not in missing
    replacement = api.post(f"/api/jira/cards/{card_key}/query", json={"intent": "refresh"}).json()
    assert replacement["snapshotId"] != started["snapshotId"]
    for _ in range(100):
        task = api.get(f"/api/jira/cards/{card_key}/tasks/{replacement['taskId']}").json()
        if task["state"] not in {"queued", "running"}: break
        time.sleep(.01)
    assert task["state"] == "completed"
    reused = api.post(f"/api/jira/cards/{card_key}/query", json={"intent": "reuse"}).json()
    assert reused["query"]["activeSnapshotId"] == replacement["snapshotId"]
    assert len(executed) == 8


@pytest.mark.parametrize("card_key", ["self-test", "task", "customer-feedback"])
def test_card_bulk_query_requests_comments_and_replays_comment_authors(tmp_path, monkeypatch, card_key):
    from core.jira.gateway import JiraGateway
    requested = []
    def search(_self, _query, *, fields=None, expand=None, page_size=None, progress=None):
        requested.append((fields, expand, page_size))
        return dated_rows([{"id": "1", "key": "TV-1", "fields": {
            "project": {"key": "TV"}, "creator": {"name": "fan.xu"},
            "comment": {"comments": [{"id": "c1", "author": {"name": "meng.wang1"}, "created": "2020-01-01T00:00:00Z"}]},
        }, "changelog": {"histories": [{"author": {"name": "meng.wang1"},
            "created": "2026-09-01T00:00:00Z", "items": [{"field": "status", "fromString": "Resolved", "toString": "Verified"}]}]}}], _query)
    monkeypatch.setattr(Gateway, "search_all_payloads", search)
    api = client(tmp_path)
    api.post("/api/jira/analytics/search", json={"mode": "basic", "basic": {}})
    started = api.post(f"/api/jira/cards/{card_key}/query", json={"period": "year"}).json()
    for _ in range(100):
        task = api.get(f"/api/jira/cards/{card_key}/tasks/{started['taskId']}").json()
        if task["state"] not in {"queued", "running"}: break
        time.sleep(.01)
    assert task["state"] == "completed"
    assert requested == ([([*JiraGateway.CORE_FIELDS, "comment"], None, 100)] * 2
                         + [(["key"], ["changelog"], 100)] * 2)
    replay = api.get(f"/api/jira/cards/{card_key}/statistics").json()
    for period in ["current", "previous"]:
        people = replay[period]["productLines"][2]["people"]
        commenter = next(person for person in people if person["identity"] == "meng.wang1")
        assert commenter["commentCount"] == 1
        assert commenter["verifyCount"] == 1
        assert all("p0Count" not in person for person in people)
        assert all("resolvedCount" not in person for person in people)
    assert len(requested) == 4


def test_card_replays_each_persisted_layer_while_later_layers_are_running(tmp_path, monkeypatch):
    gates = [Event() for _ in range(3)]
    entered = [Event() for _ in range(3)]
    calls = []
    def search(_self, query, **kwargs):
        index = len(calls)
        calls.append((query, kwargs))
        if index:
            entered[index - 1].set()
            assert gates[index - 1].wait(5)
        if index < 2:
            return dated_rows([{"id": "1", "key": "TV-1", "fields": {"project": {"key": "TV"},
                "creator": {"name": "fan.xu"}, "comment": {"comments": []}}}], query)
        return dated_rows([{"id": "1", "key": "TV-1", "changelog": {"histories": [{
            "author": {"name": "meng.wang1"}, "created": "2026-09-01T00:00:00Z",
            "items": [{"field": "status", "fromString": "Resolved", "toString": "Verified"}],
        }]}}], query)
    monkeypatch.setattr(Gateway, "search_all_payloads", search)
    api = client(tmp_path)
    try:
        started = query_card(api, {"mode": "basic", "basic": {}}).json()
        for stage in range(3):
            assert entered[stage].wait(2)
            response = api.get("/api/jira/cards/self-test/statistics").json()
            assert response["state"] == "loading"
            assert response["current"]["teamTotal"] == 1
            assert response["availability"]["current"] == {"basic": True, "verify": stage == 2}
            assert response["availability"]["previous"] == {"basic": stage >= 1, "verify": False}
            assert all("verifyCount" not in person for line in response["previous"]["productLines"] for person in line["people"])
            gates[stage].set()
        assert wait_terminal(api, started["taskId"]) == "completed"
        ready = api.get("/api/jira/cards/self-test/statistics").json()
        assert all(value["verify"] for value in ready["availability"].values())
        assert ready["current"]["teamTotal"] == ready["previous"]["teamTotal"] == 1
        assert [kwargs["expand"] for _, kwargs in calls] == [None, None, ["changelog"], ["changelog"]]
        assert len(calls) == 4
    finally:
        for gate in gates: gate.set()


@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
@pytest.mark.parametrize("has_active", [False, True])
def test_interrupted_layers_restore_complete_active_or_keep_first_basic_preview(tmp_path, monkeypatch, terminal, has_active):
    calls = []
    def search(_self, _query, **kwargs):
        calls.append(kwargs)
        if len(calls) == (7 if has_active else 3):
            raise TaskCancelled() if terminal == "cancelled" else RuntimeError("offline")
        return dated_rows([{"id": "1", "key": "TV-1", "fields": {
            "project": {"key": "TV"}, "creator": {"name": "fan.xu"}}}], _query)
    monkeypatch.setattr(Gateway, "search_all_payloads", search)
    api = client(tmp_path)
    if has_active:
        first = query_card(api, {"mode": "basic", "basic": {}}).json()
        assert wait_terminal(api, first["taskId"]) == "completed"
    started = query_card(api, {"mode": "basic", "basic": {}}).json()
    assert wait_terminal(api, started["taskId"]) == terminal
    payload = api.get("/api/jira/cards/self-test/statistics").json()
    assert payload["state"] == terminal
    assert payload["teamTotal"] == 1
    assert payload["availability"]["current"] == {"basic": True, "verify": has_active}
    assert payload["availability"]["previous"] == {"basic": True, "verify": has_active}
    people = [person for line in payload["productLines"] for person in line["people"]]
    assert all(("verifyCount" in person) == has_active for person in people)
    assert bool(payload["query"]["activeSnapshotId"]) == has_active


def test_incremental_card_aggregation_loads_each_account_groups_once_per_task(tmp_path, monkeypatch):
    groups = []
    def user_groups(_self, account):
        groups.append(account)
        return ("fae-tv-qa",) if account != "outside" else ()
    monkeypatch.setattr(Gateway, "user_groups", user_groups)
    monkeypatch.setattr(Gateway, "search_all_payloads", lambda _self, _query, **kwargs: [{
        "id": "1", "key": "TV-1", "fields": {"project": {"key": "TV"}, "creator": {"name": "creator"},
            "comment": {"comments": [{"author": {"name": "outside"}, "created": "2026-09-01T00:00:00Z"}]}},
        "changelog": {"histories": [{"author": {"name": "verifier"}, "created": "2026-09-01T00:00:00Z",
            "items": [{"field": "status", "fromString": "Resolved", "toString": "Verified"}]}]}
            if kwargs.get("expand") else {},
    }])
    api = client(tmp_path)
    for completed_tasks in (1, 2):
        started = query_card(api, {"mode": "basic", "basic": {}}).json()
        assert wait_terminal(api, started["taskId"]) == "completed"
        assert {account: groups.count(account) for account in groups} == {
            "creator": completed_tasks, "outside": completed_tasks, "verifier": completed_tasks}
