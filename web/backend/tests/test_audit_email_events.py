from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time

from fastapi.testclient import TestClient
from test_audit_email_api import make_app, login


def test_create_event_requires_auth_and_future_beijing_time():
    with TestClient(make_app(), base_url='https://testserver') as client:
        assert client.get('/api/audit-email/events').status_code == 401
        login(client)
        assert client.post('/api/audit-email/events', json={'dueAt': '2000-01-01T10:00'}).status_code == 422
        due = (datetime.now(ZoneInfo('Asia/Shanghai')) + timedelta(days=1)).replace(microsecond=0).isoformat()
        response = client.post('/api/audit-email/events', json={'dueAt': due})
        assert response.status_code == 200
        event = response.json()
        assert event['state'] == 'pending' and event['dueAt'] == due
        assert client.get('/api/audit-email/events').json()['events'][0]['id'] == event['id']
        assert 'secret' not in response.text

class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 7, 12, tzinfo=ZoneInfo('Asia/Shanghai'))
        self.owners = []
        self.calls = []

    def factory(self, history, launch):
        from smarttest_web.audit.email_events import AuditEmailEvents
        from unittest.mock import Mock
        def schedule(delay, callback):
            self.calls.append((delay, callback))
            return Mock()
        owner = AuditEmailEvents(history, launch, now=lambda: self.value, schedule=schedule)
        self.owners.append(owner)
        return owner


def wait_event(client):
    for _ in range(300):
        event = client.get('/api/audit-email/events').json()['events'][0]
        if event['state'] not in {'pending', 'running'}:
            return event
        time.sleep(.01)
    raise AssertionError('event did not finish')


def test_due_once_restart_and_real_mime(monkeypatch):
    from core.email.outlook import sender
    messages = []
    logs = []
    from smarttest_web.audit import email_job, email_events
    monkeypatch.setattr(email_job, 'smart_log', lambda message, **kw: logs.append(kw['extra']))
    monkeypatch.setattr(email_events, 'smart_log', lambda message, **kw: logs.append(kw['extra']))
    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ('10.18.11.55', 25, 20)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def send_message(self, message, **envelope):
            messages.append((message, envelope))
            return {}
    original = sender.send_built_email
    monkeypatch.setattr(sender, 'send_built_email', lambda built: original(built, smtp_factory=SMTP))
    clock = Clock()
    with TestClient(make_app(email_events_factory=clock.factory), base_url='https://testserver') as client:
        login(client)
        event = client.post('/api/audit-email/events', json={'dueAt': '2026-09-07T12:01'}).json()
        clock.owners[-1].fire(event['id'])
        assert not messages
    clock.value += timedelta(minutes=2)
    with TestClient(make_app(email_events_factory=clock.factory), base_url='https://testserver') as client:
        login(client)
        owner = clock.owners[-1]
        assert clock.calls[-1][0] == 0
        owner.fire(event['id'])
        owner.fire(event['id'])
        done = wait_event(client)
        assert done['state'] == 'completed', done
        assert {kind: item['state'] for kind, item in done['deliveries'].items()} == {'jira': 'accepted', 'confluence': 'accepted'}
        run = client.get(f"/api/audit-email/runs/{done['runId']}").json()
        assert run['source'] == 'one_time' and run['eventId'] == event['id']
        assert run['state'] == 'completed'
        assert len(messages) == 2
        for (message, envelope), kind in zip(messages, ('jira', 'confluence')):
            assert envelope == {'from_addr': 'fae-qa-auto@amlogic.com', 'to_addrs': ['chao.li@amlogic.com', 'ping.xiong@amlogic.com']}
            assert message['Subject'] == run['reports'][kind]['subject']
            attachments = list(message.iter_attachments())
            assert [part.get_filename() for part in attachments] == run['reports'][kind]['attachments']
            assert all(part.get_payload(decode=True)[:2] == b'PK' for part in attachments)
            assert message.get_body(preferencelist=('html',)) is not None
            assert '邮件未发送' not in message.get_body(preferencelist=('html',)).get_content()
            delivery = done['deliveries'][kind]
            assert datetime.fromisoformat(delivery['finishedAt']) >= datetime.fromisoformat(delivery['startedAt'])
        assert {'created', 'waiting', 'due', 'report_saved', 'smtp_started', 'smtp_accepted', 'finished'} <= {entry['stage'] for entry in logs}
        assert all(entry['event_id'] == event['id'] for entry in logs)
        assert 'secret' not in str(logs) and '<html' not in str(logs)
    with TestClient(make_app(email_events_factory=clock.factory), base_url='https://testserver') as client:
        login(client)
        clock.owners[-1].fire(event['id'])
        assert len(messages) == 2
        assert client.get('/api/audit-email/events').json()['events'][0]['state'] == 'completed'


def test_mail_failure_is_independent_and_safe(monkeypatch):
    import core.email.outlook as outlook
    sent = []
    def send(**kwargs):
        sent.append(kwargs)
        if len(sent) == 1:
            raise RuntimeError('secret cookie=<body>')
    monkeypatch.setattr(outlook, 'send_email', send)
    clock = Clock()
    with TestClient(make_app(email_events_factory=clock.factory), base_url='https://testserver') as client:
        login(client)
        event = client.post('/api/audit-email/events', json={'dueAt': '2026-09-07T12:01'}).json()
        clock.value += timedelta(minutes=1)
        clock.owners[-1].fire(event['id'])
        done = wait_event(client)
        assert done['state'] == 'partial'
        assert done['deliveries']['jira']['state'] == 'failed'
        assert done['deliveries']['jira']['error'] == 'RuntimeError'
        assert done['deliveries']['confluence']['state'] == 'accepted'
        run = client.get(f"/api/audit-email/runs/{done['runId']}").json()
        assert all(report['state'] == 'completed' for report in run['reports'].values())
        assert 'secret' not in run['evidence']
        assert len(sent) == 2


def test_run_stays_running_until_smtp_finishes(monkeypatch):
    from threading import Event
    import core.email.outlook as outlook
    entered, release = Event(), Event()
    def send(**kwargs):
        entered.set()
        assert release.wait(5)
    monkeypatch.setattr(outlook, 'send_email', send)
    clock = Clock()
    with TestClient(make_app(email_events_factory=clock.factory), base_url='https://testserver') as client:
        login(client)
        event = client.post('/api/audit-email/events', json={'dueAt': '2026-09-07T12:01'}).json()
        clock.value += timedelta(minutes=1)
        clock.owners[-1].fire(event['id'])
        try:
            assert entered.wait(3)
            event = client.get('/api/audit-email/events').json()['events'][0]
            run = client.get(f"/api/audit-email/runs/{event['runId']}").json()
            assert run['state'] == 'running'
            assert event['deliveries']['jira']['state'] == 'sending'
        finally:
            release.set()
            wait_event(client)


def test_restore_claimed_event_does_not_send_again(tmp_path):
    from smarttest_web.database import WebDatabase
    from smarttest_web.audit.email_history import AuditEmailHistory
    clock = Clock()
    history = AuditEmailHistory(WebDatabase(tmp_path / 'events.db'))
    calls = []
    owner = clock.factory(history, lambda event, done: calls.append(event))
    event = owner.create('coco', '2026-09-07T12:01', 'project=SH')
    clock.value += timedelta(minutes=1)
    owner.fire(event['id'])
    owner.close()
    restored = clock.factory(history, lambda event, done: calls.append(event))
    restored.start()
    restored.fire(event['id'])
    assert len(calls) == 1
    assert restored.list_events('coco')['events'][0]['error'] == 'interrupted'
    assert restored.list_events('other')['events'] == []


def test_live_timer_executes_without_browser_request(monkeypatch):
    from threading import Event
    import core.email.outlook as outlook
    delivered = Event()
    calls = []
    def send(**kwargs):
        calls.append(kwargs['subject'])
        if len(calls) == 2:
            delivered.set()
    monkeypatch.setattr(outlook, 'send_email', send)
    with TestClient(make_app(), base_url='https://testserver') as client:
        login(client)
        due = datetime.now(ZoneInfo('Asia/Shanghai')) + timedelta(seconds=.5)
        assert client.post('/api/audit-email/events', json={'dueAt': due.isoformat()}).status_code == 200
        assert delivered.wait(5)
        assert wait_event(client)['state'] == 'completed'


def test_due_without_saved_credentials_records_failure(monkeypatch):
    from smarttest_web.session import PersistentSessionStore
    clock = Clock()
    with TestClient(make_app(email_events_factory=clock.factory), base_url='https://testserver') as client:
        login(client)
        event = client.post('/api/audit-email/events', json={'dueAt': '2026-09-07T12:01'}).json()
        def unavailable(*args, **kwargs):
            raise RuntimeError('secret credentials missing')
        monkeypatch.setattr(PersistentSessionStore, 'create_from_saved', unavailable)
        clock.value += timedelta(minutes=1)
        clock.owners[-1].fire(event['id'])
        done = wait_event(client)
        assert done['state'] == 'failed' and done['error'] == 'RuntimeError'
        assert done['runId'] is None
        assert 'secret' not in str(done)


def test_job_close_cancels_and_joins_running_coordinator(monkeypatch, tmp_path):
    from threading import Event, Thread, current_thread
    from core.async_tasks import AsyncTaskManager, TaskCancelled
    from smarttest_web.audit import email_job
    from smarttest_web.audit.email_history import AuditEmailHistory
    from smarttest_web.database import WebDatabase
    manager = AsyncTaskManager(max_workers=1)
    monkeypatch.setattr(email_job, 'WEB_TASKS', manager)
    entered, cleaning, release, closed = Event(), Event(), Event(), Event()
    workers = []
    def run(*args):
        token = args[-3]
        workers.append(current_thread())
        entered.set()
        try:
            while True:
                token.raise_if_cancelled()
                time.sleep(.005)
        except TaskCancelled:
            cleaning.set()
            assert release.wait(2)
    job = email_job.AuditEmailJob(AuditEmailHistory(WebDatabase(tmp_path / 'close.db')))
    monkeypatch.setattr(job, '_run', run)
    closer = None
    try:
        job.trigger('coco', 'project=SH', None, '', 0, None, None, None)
        assert entered.wait(1)
        closer = Thread(target=lambda: (job.close(), closed.set()))
        closer.start()
        assert cleaning.wait(1)
        assert not closed.is_set(), 'shutdown returned before the coordinator cleaned up'
        release.set()
        closer.join(1)
        assert closed.is_set()
        assert not workers[0].is_alive()
    finally:
        release.set()
        manager.close()
        if closer:
            closer.join(1)


def test_app_shutdown_cancels_far_future_timer_without_threads():
    from threading import enumerate as threads
    before = set(threads())
    started = time.monotonic()
    with TestClient(make_app(), base_url='https://testserver') as client:
        login(client)
        due = datetime.now(ZoneInfo('Asia/Shanghai')) + timedelta(days=365)
        response = client.post('/api/audit-email/events', json={'dueAt': due.isoformat()})
        assert response.status_code == 200
    assert time.monotonic() - started < 3
    assert not [thread.name for thread in threads() if thread not in before and thread.is_alive()]
