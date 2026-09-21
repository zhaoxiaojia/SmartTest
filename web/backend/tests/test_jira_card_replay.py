from threading import Event

from fastapi.testclient import TestClient
from smarttest_web.database import WebDatabase
from test_jira_analytics_api import Gateway, client, query_card, wait_terminal


def test_period_cache_is_exact_and_search_refreshes_it(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(Gateway, 'search_all_payloads', lambda _self, jql, **_kw: calls.append(jql) or [])
    api = client(tmp_path)
    api.post('/api/jira/analytics/search', json={'mode': 'basic', 'basic': {}})
    ids = {}
    for period in ['month', 'week']:
        payload = api.post('/api/jira/cards/self-test/query', json={'period': period, 'intent': 'reuse'}).json()
        assert wait_terminal(api, payload['taskId']) == 'completed'
        ids[period] = payload['snapshotId']
    from test_jira_analytics_api import FilterOwner
    def reject(*_args, **_kwargs):
        raise AssertionError('cache hit must not validate remotely')
    with monkeypatch.context() as scoped:
        scoped.setattr(FilterOwner, 'validate', reject)
        payload = api.post('/api/jira/cards/self-test/query', json={'period': 'month', 'intent': 'reuse'}).json()
        assert payload['state'] == 'ready'
        assert payload['query']['activeSnapshotId'] == ids['month']
    assert len(calls) == 2
    refreshed = api.post('/api/jira/cards/self-test/query', json={'intent': 'refresh'}).json()
    assert wait_terminal(api, refreshed['taskId']) == 'completed'
    assert len(calls) == 3
    api.post('/api/auth/logout')
    api.post('/api/auth/login', json={'username': 'coco', 'password': 'secret'})
    restored = api.post('/api/jira/cards/self-test/query', json={'period': 'week', 'intent': 'reuse'}).json()
    assert restored['query']['activeSnapshotId'] == ids['week']
    assert restored['state'] == 'ready'
    assert len(calls) == 3
    api.post('/api/jira/analytics/search', json={'mode': 'advanced', 'jql': 'status = Open'})
    changed = api.post('/api/jira/cards/self-test/query', json={'period': 'month', 'intent': 'reuse'}).json()
    assert wait_terminal(api, changed['taskId']) == 'completed'
    assert len(calls) == 4


def test_card_period_defaults_to_month_and_restores_independently_without_get_fetch(tmp_path, monkeypatch):
    from datetime import date
    calls = []
    monkeypatch.setattr(Gateway, 'search_all_payloads', lambda _self, jql, **_kw: calls.append(jql) or [])
    api = client(tmp_path)
    api.put('/api/preferences/jira/cards/customer', json={'items': {'period': 'quarter'}})
    assert api.get('/api/jira/cards/self-test/statistics').json()['period'] == 'month'
    api.post('/api/jira/analytics/search', json={'mode': 'advanced', 'jql': 'status = Open OR status = Closed ORDER BY created DESC'})
    periods = [('week', 'created >= "-7d"'), ('month', 'created >= "-30d"'),
               ('quarter', 'created >= startOfDay("-3M")'),
               ('year', f'created >= "{date.today().year}-01-01"')]
    for period, condition in periods:
        started = api.post('/api/jira/cards/self-test/query', json={'period': period}).json()
        assert wait_terminal(api, started['taskId']) == 'completed'
        payload = api.get('/api/jira/cards/self-test/statistics').json()
        assert payload['period'] == period
        assert condition in payload['query']['activeJql']
        assert payload['query']['activeJql'].endswith('ORDER BY created DESC')
    api.post('/api/auth/logout')
    api.post('/api/auth/login', json={'username': 'coco', 'password': 'secret'})
    assert api.get('/api/jira/cards/self-test/statistics').json()['period'] == 'year'
    assert len(calls) == 4
    assert api.post('/api/jira/cards/self-test/query', json={'period': 'invalid'}).status_code == 422
    assert len(calls) == 4
    api.post('/api/auth/logout')
    api.post('/api/auth/login', json={'username': 'bob', 'password': 'secret'})
    assert api.get('/api/jira/cards/self-test/statistics').json()['period'] == 'month'
    assert len(calls) == 4


def test_same_account_relogin_restores_conditions_and_card_without_remote_fetch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(Gateway, 'search_all_payloads', lambda _self, jql, **_kw: calls.append(jql) or [])
    api = client(tmp_path)
    draft = {'mode': 'advanced', 'jql': 'reporter = "fan.xu"'}
    started = query_card(api, draft).json()
    assert wait_terminal(api, started['taskId']) == 'completed'
    original = api.get('/api/jira/cards/self-test/statistics').json()
    api.post('/api/auth/logout')
    api.post('/api/auth/login', json={'username': 'coco', 'password': 'secret'})
    restored = api.get('/api/jira/cards/self-test/statistics').json()
    assert restored == original
    assert api.get('/api/jira/analytics/state').json()['conditions']['jql'] == draft['jql']
    assert len(calls) == 1
    assert api.get('/api/dashboard/jira-team-bugs').status_code == 404
    assert restored['state'] == 'ready'
    assert restored['teamTotal'] == 0


def test_annual_snapshot_is_not_replayed_as_a_rolling_result_or_queried_by_get(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(Gateway, 'search_all_payloads', lambda _self, jql, **_kw: calls.append(jql) or [])
    api = client(tmp_path)
    started = query_card(api, {'mode': 'basic', 'basic': {}}).json()
    assert wait_terminal(api, started['taskId']) == 'completed'
    database = WebDatabase(tmp_path / 'web.db')
    with database.transaction() as connection:
        connection.execute('UPDATE jira_analytics_snapshots SET jql=replace(jql,?,?) WHERE snapshot_id=?',
                           ('created >= "-30d" AND created <= now()', 'created >= startOfYear() AND created <= endOfYear()', started['snapshotId']))
    payload = api.get('/api/jira/cards/self-test/statistics').json()
    assert payload['state'] == 'no_snapshot'
    assert 'productLines' not in payload
    assert len(calls) == 1


def test_another_session_can_read_same_account_result_but_not_task_or_cancel(tmp_path, monkeypatch):
    release = Event()
    def collect(_self, _jql, **_kwargs):
        assert release.wait(5)
        return []
    monkeypatch.setattr(Gateway, 'search_all_payloads', collect)
    first = client(tmp_path)
    second = TestClient(first.app, base_url='https://testserver')
    second.post('/api/auth/login', json={'username': 'coco', 'password': 'secret'})
    try:
        started = query_card(first, {'mode': 'basic', 'basic': {}}).json()
        for _ in range(3):
            shared = second.get('/api/jira/cards/self-test/statistics').json()
            assert shared['state'] == 'loading'
            assert shared['query']['taskId'] == ''
            assert shared['query']['pendingSnapshotId'] == started['snapshotId']
        assert second.get(f"/api/jira/cards/self-test/tasks/{started['taskId']}").status_code == 404
        assert second.delete(f"/api/jira/cards/self-test/tasks/{started['taskId']}").status_code == 404
        assert first.get(f"/api/jira/cards/self-test/tasks/{started['taskId']}").status_code == 200
    finally:
        release.set()
    assert wait_terminal(first, started['taskId']) == 'completed'
    assert second.get('/api/jira/cards/self-test/statistics').json()['state'] == 'ready'


def test_login_and_session_restore_do_not_fetch_organization_architecture_or_jira(tmp_path, monkeypatch):
    def reject(*_args, **_kwargs):
        raise AssertionError('remote fetch must not start')
    monkeypatch.setattr('core.confluence.gateway.ConfluenceGateway.get_page', reject)
    monkeypatch.setattr(Gateway, 'search_all_payloads', reject)
    api = client(tmp_path)
    assert api.get('/api/auth/session').json()['authenticated'] is True
    assert api.get('/api/jira/cards/self-test/statistics').json() == {'state': 'no_snapshot', 'period': 'month'}
