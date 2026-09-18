from threading import Event

from fastapi.testclient import TestClient
from test_jira_analytics_api import Gateway, client, query_card, wait_terminal


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
    assert api.get('/api/jira/cards/self-test/statistics').json() == {'state': 'no_snapshot'}
