from dataclasses import replace
from datetime import datetime
import time
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from core.confluence.audit.models import AuditBatch, AuditFinding, AuditStatus, ProjectAudit
from core.confluence.audit import manual_audit_period
from core.confluence.audit.exporter import export_audit_xlsx_by_product_line
from core.confluence.project import Project, ProjectIdentity, ProductSpaceRef, ConfluencePageRef
from core.confluence.project_catalog import default_weekly_audit_filters, weekly_audit_projects, query_project_facts
from core.jira.audit.models import IssueAuditResult
from smarttest_web.app import create_app
from test_web_session import FakeAuthenticator, FakeFactsOwner
from test_manual_audit_api import JiraOwner


class ActualJira(JiraOwner):
    def run(self, scope, cancellation, progress):
        report = super().run(scope, cancellation, progress)
        return replace(report, issues=(IssueAuditResult('SH-1', 'https://jira.amlogic.com/browse/SH-1', 'test', 'QA', True, ()),))


class Facts(FakeFactsOwner):
    def refresh(self, access, password):
        pass

    def query(self, access, **kwargs):
        return {'state': 'ready', 'projects': [{'project_id': 'P1', 'fields': {'current stage': '2 DEVELOPMENT'}}]}


class Confluence:
    def resolve(self, payload):
        assert payload['projectIds'] == ['P1']
        return manual_audit_period(datetime.fromisoformat(payload['startDate']).date(), datetime.fromisoformat(payload['endDate']).date())

    def run(self, period, cancellation, progress):
        project = Project(ProjectIdentity('1', 'P1'), 'Project', ProductSpaceRef('TV'), ConfluencePageRef('1'))
        finding = AuditFinding('P1', 'Test', 'test.weekly', AuditStatus.UPDATED, 'changed')
        return AuditBatch('batch', period, datetime.now(), (ProjectAudit(project, (finding,)),))

    def export(self, report, directory):
        return export_audit_xlsx_by_product_line(report, directory)


def make_app(**kwargs):
    return create_app(authenticator=FakeAuthenticator, project_facts_owner=Facts,
                      jira_audit_owner=lambda *_: ActualJira(), confluence_audit_owner=lambda *_: Confluence(), **kwargs)


def login(client):
    client.post('/api/auth/login', json={'username': 'coco', 'password': 'secret'})
    client.put('/api/preferences/jira.html', json={'items': {'auditInput': 'project=SH'}, 'schemaVersion': 1})


def trigger(client):
    response = client.post('/api/audit-email/runs')
    assert response.status_code == 200
    run_id = response.json()['id']
    for _ in range(200):
        result = client.get(f'/api/audit-email/runs/{run_id}').json()
        if result['state'] not in {'queued', 'running'}:
            return result
        time.sleep(.01)
    raise AssertionError('audit did not finish')


def test_real_dual_runs_keep_five_records_and_attachments_after_restart():
    with TestClient(make_app(), base_url='https://testserver') as client:
        assert client.post('/api/audit-email/runs').status_code == 401
        assert client.get('/api/audit-email/runs').status_code == 401
        login(client)
        assert len(client.get('/api/audit-email/runs').json()['runs']) == 4
        runs = [trigger(client) for _ in range(5)]
        assert len({run['id'] for run in runs}) == 5
        for run in runs:
            assert run['state'] == 'completed', run['evidence']
            assert run['summary']['jira']['total'] == 1
            assert run['summary']['confluence']['TV'] == [1, 1]
            assert run['reports']['jira']['sourceIds'][0] == run['id']
            assert len(run['reports']['jira']['sourceIds']) == 4
            assert 'project=SH' in run['reports']['jira']['html']
        assert len(runs[0]['reports']['confluence']['sourceIds']) == 3
        assert len(runs[-1]['reports']['confluence']['sourceIds']) == 4
        first = runs[0]
        for kind in ('jira', 'confluence'):
            assert first['reports'][kind]['attachments']
            name = first['reports'][kind]['attachments'][0]
            assert client.get(f'/api/audit-email/runs/{first["id"]}/attachments/{kind}/{name}').content[:2] == b'PK'
    with TestClient(make_app(), base_url='https://testserver') as client:
        login(client)
        assert client.get(f'/api/audit-email/runs/{first["id"]}').json() == first
        listing = client.get('/api/audit-email/runs').json()
        assert listing['total'] == 9
        assert len(listing['runs']) == 4
        assert len(client.get('/api/audit-email/runs?offset=4').json()['runs']) == 4
        name = first['reports']['jira']['attachments'][0]
        assert client.get(f'/api/audit-email/runs/{first["id"]}/attachments/jira/{name}').content[:2] == b'PK'
        assert client.get(f'/api/audit-email/runs/{first["id"]}/attachments/jira/no.xlsx').status_code == 404
        assert client.get('/api/audit-email/runs/missing').status_code == 404


def test_seed_details_never_invent_missing_history():
    with TestClient(make_app(), base_url='https://testserver') as client:
        login(client)
        rows = client.get('/api/audit-email/runs').json()['runs']
        detail = client.get(f'/api/audit-email/runs/{rows[-1]["id"]}').json()
        assert detail['label'] == '0807'
        assert detail['reports']['confluence']['state'] == 'unavailable'
        assert detail['reports']['confluence']['html'] == ''
        latest = client.get(f'/api/audit-email/runs/{rows[0]["id"]}').json()
        assert '12 / 168' in latest['reports']['confluence']['html']
        assert '49.15%' in latest['reports']['jira']['html']


def test_missing_jira_input_keeps_confluence_actual_result_and_failed_history():
    with TestClient(make_app(), base_url='https://testserver') as client:
        client.post('/api/auth/login', json={'username': 'coco', 'password': 'secret'})
        result = trigger(client)
        assert result['state'] == 'partial'
        assert result['reports']['jira']['error'] == 'saved_jira_input_missing'
        assert result['reports']['confluence']['state'] == 'completed'
        assert 'jira' not in result['summary']


def test_another_account_cannot_read_run_or_attachment():
    auth = FakeAuthenticator()
    app = create_app(authenticator=lambda: auth, project_facts_owner=Facts,
                     jira_audit_owner=lambda *_: ActualJira(), confluence_audit_owner=lambda *_: Confluence())
    with TestClient(app, base_url='https://testserver') as client:
        login(client)
        result = trigger(client)
        client.post('/api/auth/logout')
        auth.result = {'success': True, 'username': 'other', 'display_name': 'Other', 'avatar_bytes': b''}
        client.post('/api/auth/login', json={'username': 'other', 'password': 'secret'})
        assert client.get(f'/api/audit-email/runs/{result["id"]}').status_code == 404
        name = result['reports']['jira']['attachments'][0]
        assert client.get(f'/api/audit-email/runs/{result["id"]}/attachments/jira/{name}').status_code == 404
        assert client.get('/api/audit-email/runs').json()['total'] == 4


def test_trigger_uses_same_window_for_both_reports_without_overwriting_saved_jql():
    template = 'project=SH AND created >=2026-08-28 AND created <=2026-09-4 order by updated DESC'
    with TestClient(make_app(), base_url='https://testserver') as client:
        login(client)
        client.put('/api/preferences/jira.html', json={'items': {'auditInput': template}, 'schemaVersion': 1})
        result = trigger(client)
        assert result['state'] == 'completed'
        scope = result['scope']
        expected = f'project=SH AND created >="{scope["startDate"]}" AND created <"{scope["endDate"]}" order by updated DESC'
        assert scope['jiraInput'] == result['summary']['jira']['scope'] == expected
        assert scope['jiraTemplate'] == template
        assert client.get('/api/preferences/jira.html').json()['items']['auditInput'] == template


def test_restored_client_defaults_exclude_late_stages_without_new_stage_rules():
    filters = default_weekly_audit_filters(datetime(2026, 9, 7, tzinfo=ZoneInfo('Asia/Shanghai')))
    rows = [{'project_id': name, 'fields': {'date of commercial approval': year + '-01-01', 'support mode': support,
            'project status': 'NORMAL', 'current stage': stage}}
            for name, year, support, stage in [('yes', '2025', 'A', '3 DEVELOPMENT'), ('old', '2024', 'A', '2'),
                                               ('late', '2026', 'A', '4 CLOSED'), ('b', '2026', 'B', '2')]]
    selected = query_project_facts({'projects': rows}, filters=filters)['projects']
    assert [row['project_id'] for row in weekly_audit_projects(selected)] == ['yes']
