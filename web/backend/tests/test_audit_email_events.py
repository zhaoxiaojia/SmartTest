from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time

from fastapi.testclient import TestClient
from test_audit_email_api import make_app, login


def test_create_event_requires_auth_and_future_beijing_time():
    with TestClient(make_app(), base_url='https://testserver') as client:
        assert client.get('/api/audit-email/events').status_code == 401
        client.post('/api/auth/login', json={'username': 'coco', 'password': 'secret'})
        due = (datetime.now(ZoneInfo('Asia/Shanghai')) + timedelta(days=1)).replace(microsecond=0).isoformat()
        response = client.post('/api/audit-email/events', json={'dueAt': due})
        assert response.status_code == 200
        assert response.json()['filterScope']['endDate'] == due
        assert client.post('/api/audit-email/events', json={'dueAt': '2000-01-01T10:00'}).status_code == 422
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


def test_weekly_schedule_persists_updates_deletes_and_exposes_next_run(tmp_path):
    from smarttest_web.database import WebDatabase
    from smarttest_web.audit.email_history import AuditEmailHistory
    clock = Clock()
    history = AuditEmailHistory(WebDatabase(tmp_path / 'schedule.db'))
    owner = clock.factory(history, lambda event, done: None)

    assert owner.get_schedule('coco') is None
    created = owner.save_schedule('coco', {'weekday': 4, 'time': '15:00', 'enabled': True})
    assert created['timezone'] == 'Asia/Shanghai'
    assert created['nextRunAt'] == '2026-09-11T15:00:00+08:00'

    restored = clock.factory(history, lambda event, done: None)
    restored.start()
    assert restored.get_schedule('coco')['time'] == '15:00'
    changed = restored.save_schedule('coco', {'weekday': 2, 'time': '09:30', 'enabled': False})
    assert changed['nextRunAt'] is None
    assert restored.delete_schedule('coco') is True
    assert restored.get_schedule('coco') is None
    assert clock.factory(history, lambda event, done: None).get_schedule('coco') is None


def test_screenshot_only_history_creates_default_for_authenticated_account_once(tmp_path):
    from smarttest_web.database import WebDatabase
    from smarttest_web.audit.email_history import AuditEmailHistory
    database = WebDatabase(tmp_path / 'upgrade.db')
    history = AuditEmailHistory(database)
    clock = Clock()

    first = clock.factory(history, lambda event, done: None)
    schedule = first.get_or_create_default_schedule('coco')
    same = first.get_or_create_default_schedule('coco')

    assert schedule['weekday'] == 4
    assert schedule['time'] == '15:00'
    assert schedule['enabled'] is True
    assert same['id'] == schedule['id']
    with database.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM audit_email_schedules').fetchone()[0] == 1


def test_deleted_default_is_not_recreated_by_later_authenticated_get(tmp_path):
    from smarttest_web.database import WebDatabase
    from smarttest_web.audit.email_history import AuditEmailHistory
    history = AuditEmailHistory(WebDatabase(tmp_path / 'deleted.db'))
    clock = Clock()
    owner = clock.factory(history, lambda event, done: None)
    owner.get_or_create_default_schedule('coco')

    assert owner.delete_schedule('coco') is True
    assert owner.get_or_create_default_schedule('coco') is None
    restored = clock.factory(history, lambda event, done: None)
    assert restored.get_or_create_default_schedule('coco') is None


def test_weekly_schedule_claims_each_occurrence_once_across_restart(tmp_path):
    from smarttest_web.database import WebDatabase
    from smarttest_web.audit.email_history import AuditEmailHistory
    clock = Clock()
    clock.value = datetime(2026, 9, 11, 14, 59, tzinfo=ZoneInfo('Asia/Shanghai'))
    history = AuditEmailHistory(WebDatabase(tmp_path / 'schedule.db'))
    launched = []
    owner = clock.factory(history, lambda event, done: launched.append(event))
    schedule = owner.save_schedule('coco', {'weekday': 4, 'time': '15:00', 'enabled': True})

    clock.value = datetime(2026, 9, 11, 15, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
    owner.fire_schedule(schedule['id'], '2026-09-11T15:00:00+08:00')
    owner.fire_schedule(schedule['id'], '2026-09-11T15:00:00+08:00')
    restored = clock.factory(history, lambda event, done: launched.append(event))
    restored.start()
    restored.fire_schedule(schedule['id'], '2026-09-11T15:00:00+08:00')

    assert len(launched) == 1
    assert launched[0]['source'] == 'weekly'
    assert launched[0]['filterScope']['endDate'] == '2026-09-11T15:00:00+08:00'
    saved = restored.get_schedule('coco')
    assert saved['lastRunId'] is None
    assert saved['lastState'] == 'running'
    assert saved['nextRunAt'] == '2026-09-18T15:00:00+08:00'


def test_weekly_occurrence_uses_shared_email_job_and_records_latest_result(monkeypatch):
    import core.email.outlook as outlook
    monkeypatch.setattr(outlook, 'send_email', lambda **kwargs: None)
    clock = Clock()
    clock.value = datetime(2026, 9, 11, 14, 59, tzinfo=ZoneInfo('Asia/Shanghai'))
    with TestClient(make_app(email_events_factory=clock.factory), base_url='https://testserver') as client:
        login(client)
        schedule = client.put('/api/audit-email/schedule', json={
            'weekday': 4, 'time': '15:00', 'enabled': True,
        }).json()['schedule']
        clock.value = datetime(2026, 9, 11, 15, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
        clock.owners[-1].fire_schedule(schedule['id'], schedule['nextRunAt'])
        event = wait_event(client)
        run = client.get(f"/api/audit-email/runs/{event['runId']}").json()
        latest = client.get('/api/audit-email/schedule').json()['schedule']

        assert run['source'] == 'weekly'
        assert event['source'] == 'weekly'
        assert latest['lastRunId'] == run['id']
        assert latest['lastState'] == 'completed'
        assert client.delete('/api/audit-email/schedule').json() == {'deleted': True}
        assert client.get(f"/api/audit-email/runs/{run['id']}").status_code == 200


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
    event = owner.create('coco', '2026-09-07T12:01', {'jira': {'filters': {'project': ['SH']}, 'jql': ''},
        'confluence': {'filters': {}, 'search': '', 'projectIds': ['P1']}})
    clock.value += timedelta(minutes=1)
    owner.fire(event['id'])
    owner.close()
    restored = clock.factory(history, lambda event, done: calls.append(event))
    restored.start()
    restored.fire(event['id'])
    assert len(calls) == 1
    assert restored.list_events('coco')['events'][0]['error'] == 'interrupted'
    assert restored.list_events('other')['events'] == []


def test_timer_firing_within_clock_resolution_claims_event_once(tmp_path):
    from smarttest_web.database import WebDatabase
    from smarttest_web.audit.email_history import AuditEmailHistory
    clock = Clock()
    history = AuditEmailHistory(WebDatabase(tmp_path / 'events.db'))
    launched = []
    owner = clock.factory(history, lambda event, done: launched.append(event['id']))
    event = owner.create('coco', '2026-09-07T12:01:00', {})

    clock.value = datetime(2026, 9, 7, 12, 0, 59, 985000, tzinfo=ZoneInfo('Asia/Shanghai'))
    clock.calls[-1][1]()
    clock.calls[-1][1]()

    assert launched == [event['id']]
    assert owner.list_events('coco')['events'][0]['state'] == 'running'


def test_scheduled_callback_failure_marks_pending_event_failed(tmp_path, monkeypatch):
    from smarttest_web.database import WebDatabase
    from smarttest_web.audit.email_history import AuditEmailHistory
    clock = Clock()
    history = AuditEmailHistory(WebDatabase(tmp_path / 'events.db'))
    owner = clock.factory(history, lambda event, done: None)
    event = owner.create('coco', '2026-09-07T12:01:00', {})
    monkeypatch.setattr(owner, 'fire', lambda _event_id: (_ for _ in ()).throw(RuntimeError('boom')))

    clock.calls[-1][1]()

    saved = owner.list_events('coco')['events'][0]
    assert saved['id'] == event['id']
    assert saved['state'] == 'failed'
    assert saved['error'] == 'RuntimeError'


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
        from core.weekly_audit import fixed_weekly_audit_scope
        job.trigger('coco', fixed_weekly_audit_scope(
            datetime(2026, 9, 7, 12, tzinfo=ZoneInfo('Asia/Shanghai')),
        ), None, '', 0, None, None, None)
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
