"""Persistent one-time events; claimed events are never replayed."""

import asyncio
import json
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.logging import smart_log


class AuditEmailEvents:
    def __init__(self, history, launch, *, now=None, schedule=None):
        self.database = history.database
        self.launch = launch
        self.now = now or (lambda: datetime.now(ZoneInfo('Asia/Shanghai')))
        self.schedule = schedule or (lambda delay, callback: asyncio.get_running_loop().call_later(delay, callback))
        self.handles = {}
        with self.database.transaction() as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS audit_email_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                account TEXT NOT NULL, due_at TEXT NOT NULL, state TEXT NOT NULL,
                payload TEXT NOT NULL)''')

    def _log(self, event, stage, **fields):
        entry = {'event_id': event['id'], 'run_id': event.get('runId', ''),
                 'stage': stage, 'trigger_source': 'one_time', **fields}
        smart_log('One-time audit email ' + ' '.join(f'{key}={value}' for key, value in entry.items()),
                  platform='web', domain='audit', source='audit_email', emit_runtime_event=False, extra=entry)

    def _save(self, event):
        with self.database.transaction() as connection:
            connection.execute('UPDATE audit_email_events SET state=?,payload=? WHERE id=?',
                               (event['state'], json.dumps(event, ensure_ascii=False), event['id']))

    def list_events(self, account):
        with self.database.connect() as connection:
            rows = connection.execute('SELECT payload FROM audit_email_events WHERE account=? ORDER BY sequence DESC',
                                      (account,)).fetchall()
        return {'events': [json.loads(row[0]) for row in rows]}

    def create(self, account, due_at, jira_input):
        due = datetime.fromisoformat(due_at)
        due = due.replace(tzinfo=ZoneInfo('Asia/Shanghai')) if due.tzinfo is None else due.astimezone(ZoneInfo('Asia/Shanghai'))
        if due <= self.now():
            raise ValueError('future_time_required')
        event = {'id': str(uuid4()), 'account': account, 'dueAt': due.isoformat(),
                 'createdAt': self.now().isoformat(), 'state': 'pending', 'source': 'one_time',
                 'jiraInput': jira_input, 'runId': None, 'deliveries': {}}
        with self.database.transaction() as connection:
            connection.execute('INSERT INTO audit_email_events(id,account,due_at,state,payload) VALUES(?,?,?,?,?)',
                               (event['id'], account, event['dueAt'], event['state'], json.dumps(event)))
        self._log(event, 'created', due_at=event['dueAt'])
        self._arm(event)
        return event

    def _arm(self, event):
        delay = max(0, (datetime.fromisoformat(event['dueAt']) - self.now()).total_seconds())
        self.handles[event['id']] = self.schedule(delay, lambda: self.fire(event['id']))
        self._log(event, 'waiting', due_at=event['dueAt'], delay_seconds=delay)

    def start(self):
        with self.database.connect() as connection:
            rows = connection.execute("SELECT payload FROM audit_email_events WHERE state IN ('pending','running')").fetchall()
        for row in rows:
            event = json.loads(row[0])
            if event['state'] == 'pending':
                self._arm(event)
            else:
                event.update(state='failed', error='interrupted', finishedAt=self.now().isoformat())
                self._save(event)
                self._log(event, 'finished', state='failed', error_code='interrupted')

    def fire(self, event_id):
        handle = self.handles.pop(event_id, None)
        if handle:
            handle.cancel()
        with self.database.transaction() as connection:
            row = connection.execute("SELECT payload FROM audit_email_events WHERE id=? AND state='pending'", (event_id,)).fetchone()
            if row is None:
                return
            event = json.loads(row[0])
            if datetime.fromisoformat(event['dueAt']) > self.now():
                self._arm(event)
                return
            event.update(state='running', startedAt=self.now().isoformat())
            self._save(event)
        self._log(event, 'due')
        try:
            self.launch(event, lambda result: self.finish(event, result))
        except Exception as error:
            self.finish(event, {'state': 'failed', 'error': type(error).__name__})

    def attach_run(self, event, run):
        event['runId'] = run['id']
        self._save(event)

    def delivery(self, event, run):
        event['deliveries'] = run['deliveries']
        self._save(event)

    def finish(self, event, result):
        event.update(state=result['state'], deliveries=result.get('deliveries', {}),
                     finishedAt=self.now().isoformat())
        if result.get('error'):
            event['error'] = result['error']
        self._save(event)
        self._log(event, 'finished', state=event['state'], error_code=event.get('error', ''),
                  duration_ms=round((self.now() - datetime.fromisoformat(event['startedAt'])).total_seconds() * 1000, 3))

    def close(self):
        for handle in self.handles.values():
            handle.cancel()
        self.handles.clear()
