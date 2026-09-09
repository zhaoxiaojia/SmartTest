"""Persistent one-time events; claimed events are never replayed."""

import asyncio
import json
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.logging import smart_log
from core.weekly_audit import fixed_weekly_audit_scope


_TIMER_EARLY_TOLERANCE_SECONDS = 0.05


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
            connection.execute('''CREATE TABLE IF NOT EXISTS audit_email_schedules (
                id TEXT PRIMARY KEY, account TEXT UNIQUE NOT NULL, enabled INTEGER NOT NULL,
                payload TEXT NOT NULL)''')
            connection.execute('''CREATE TABLE IF NOT EXISTS audit_email_schedule_meta (
                key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
            connection.execute("DELETE FROM audit_email_schedule_meta WHERE key='default_created'")

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

    def get_schedule(self, account):
        with self.database.connect() as connection:
            row = connection.execute(
                'SELECT payload FROM audit_email_schedules WHERE account=?', (account,),
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def get_or_create_default_schedule(self, account):
        marker = f'default:{account.casefold()}'
        with self.database.transaction() as connection:
            row = connection.execute(
                'SELECT payload FROM audit_email_schedules WHERE account=?', (account,),
            ).fetchone()
            if row is not None:
                schedule = json.loads(row[0])
            else:
                state = connection.execute(
                    'SELECT value FROM audit_email_schedule_meta WHERE key=?', (marker,),
                ).fetchone()
                if state is not None and state[0] == 'deleted':
                    return None
                schedule = {
                    'id': str(uuid4()), 'account': account, 'weekday': 4, 'time': '15:00',
                    'timezone': 'Asia/Shanghai', 'enabled': True, 'lastOccurrence': None,
                    'lastRunId': None, 'lastState': None,
                }
                schedule['nextRunAt'] = self._next_occurrence(schedule).isoformat()
                connection.execute(
                    'INSERT INTO audit_email_schedules(id,account,enabled,payload) VALUES(?,?,1,?)',
                    (schedule['id'], account, json.dumps(schedule, ensure_ascii=False)),
                )
                connection.execute(
                    '''INSERT INTO audit_email_schedule_meta(key,value) VALUES(?,'created')
                       ON CONFLICT(key) DO UPDATE SET value='created' ''', (marker,),
                )
        self._arm_schedule(schedule)
        return schedule

    def save_schedule(self, account, values):
        weekday = values.get('weekday')
        enabled = values.get('enabled')
        clock = values.get('time')
        if not isinstance(weekday, int) or not 0 <= weekday <= 6 or not isinstance(enabled, bool):
            raise ValueError('invalid_schedule')
        try:
            hour, minute = (int(part) for part in clock.split(':'))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError('invalid_schedule') from error
        if not 0 <= hour <= 23 or not 0 <= minute <= 59 or clock != f'{hour:02d}:{minute:02d}':
            raise ValueError('invalid_schedule')
        current = self.get_schedule(account) or {}
        schedule = {
            'id': current.get('id') or str(uuid4()), 'account': account, 'weekday': weekday,
            'time': clock, 'timezone': 'Asia/Shanghai', 'enabled': enabled,
            'lastOccurrence': current.get('lastOccurrence'), 'lastRunId': current.get('lastRunId'),
            'lastState': current.get('lastState'),
        }
        schedule['nextRunAt'] = self._next_occurrence(schedule).isoformat() if enabled else None
        with self.database.transaction() as connection:
            connection.execute(
                '''INSERT INTO audit_email_schedules(id,account,enabled,payload) VALUES(?,?,?,?)
                   ON CONFLICT(account) DO UPDATE SET enabled=excluded.enabled,payload=excluded.payload''',
                (schedule['id'], account, int(enabled), json.dumps(schedule, ensure_ascii=False)),
            )
            connection.execute(
                '''INSERT INTO audit_email_schedule_meta(key,value) VALUES(?,'created')
                   ON CONFLICT(key) DO UPDATE SET value='created' ''',
                (f'default:{account.casefold()}',),
            )
        self._arm_schedule(schedule)
        return schedule

    def delete_schedule(self, account):
        schedule = self.get_schedule(account)
        if schedule:
            handle = self.handles.pop(f"schedule:{schedule['id']}", None)
            if handle:
                handle.cancel()
        with self.database.transaction() as connection:
            deleted = connection.execute(
                'DELETE FROM audit_email_schedules WHERE account=?', (account,),
            ).rowcount
            connection.execute(
                '''INSERT INTO audit_email_schedule_meta(key,value) VALUES(?,'deleted')
                   ON CONFLICT(key) DO UPDATE SET value='deleted' ''',
                (f'default:{account.casefold()}',),
            )
        return bool(deleted)

    def _next_occurrence(self, schedule, *, after=None):
        after = (after or self.now()).astimezone(ZoneInfo('Asia/Shanghai'))
        hour, minute = (int(part) for part in schedule['time'].split(':'))
        candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        candidate += timedelta(days=(schedule['weekday'] - candidate.weekday()) % 7)
        if candidate <= after:
            candidate += timedelta(days=7)
        return candidate

    def _arm_schedule(self, schedule):
        key = f"schedule:{schedule['id']}"
        handle = self.handles.pop(key, None)
        if handle:
            handle.cancel()
        if not schedule['enabled']:
            return
        due = datetime.fromisoformat(schedule['nextRunAt'])
        delay = max(0, (due - self.now()).total_seconds())
        self.handles[key] = self.schedule(
            delay, lambda: self.fire_schedule(schedule['id'], due.isoformat()),
        )

    def fire_schedule(self, schedule_id, occurrence):
        due = datetime.fromisoformat(occurrence).astimezone(ZoneInfo('Asia/Shanghai'))
        event_id = f'weekly:{schedule_id}:{due.isoformat()}'
        with self.database.transaction() as connection:
            row = connection.execute(
                'SELECT payload FROM audit_email_schedules WHERE id=? AND enabled=1', (schedule_id,),
            ).fetchone()
            if row is None:
                return
            schedule = json.loads(row[0])
            if schedule.get('nextRunAt') != due.isoformat():
                return
            event = {
                'id': event_id, 'account': schedule['account'], 'dueAt': due.isoformat(),
                'createdAt': self.now().isoformat(), 'state': 'pending', 'source': 'weekly',
                'scheduleId': schedule_id, 'filterScope': fixed_weekly_audit_scope(due),
                'runId': None, 'deliveries': {},
            }
            inserted = connection.execute(
                '''INSERT OR IGNORE INTO audit_email_events(id,account,due_at,state,payload)
                   VALUES(?,?,?,?,?)''',
                (event_id, event['account'], event['dueAt'], 'pending', json.dumps(event, ensure_ascii=False)),
            ).rowcount
            if not inserted:
                return
            schedule.update(lastOccurrence=due.isoformat(), lastState='running')
            schedule['nextRunAt'] = self._next_occurrence(schedule, after=due).isoformat()
            connection.execute(
                'UPDATE audit_email_schedules SET payload=? WHERE id=?',
                (json.dumps(schedule, ensure_ascii=False), schedule_id),
            )
        self._arm_schedule(schedule)
        self.fire(event_id)

    def create(self, account, due_at, filter_scope):
        due = datetime.fromisoformat(due_at)
        due = due.replace(tzinfo=ZoneInfo('Asia/Shanghai')) if due.tzinfo is None else due.astimezone(ZoneInfo('Asia/Shanghai'))
        if due <= self.now():
            raise ValueError('future_time_required')
        event = {'id': str(uuid4()), 'account': account, 'dueAt': due.isoformat(),
                 'createdAt': self.now().isoformat(), 'state': 'pending', 'source': 'one_time',
                 'filterScope': filter_scope, 'runId': None, 'deliveries': {}}
        with self.database.transaction() as connection:
            connection.execute('INSERT INTO audit_email_events(id,account,due_at,state,payload) VALUES(?,?,?,?,?)',
                               (event['id'], account, event['dueAt'], event['state'], json.dumps(event)))
        self._log(event, 'created', due_at=event['dueAt'])
        self._arm(event)
        return event

    def _arm(self, event):
        delay = max(0, (datetime.fromisoformat(event['dueAt']) - self.now()).total_seconds())
        self.handles[event['id']] = self.schedule(delay, lambda: self._scheduled_fire(event['id']))
        self._log(event, 'waiting', due_at=event['dueAt'], delay_seconds=delay)

    def _scheduled_fire(self, event_id):
        try:
            self.fire(event_id)
        except Exception as error:
            handle = self.handles.pop(event_id, None)
            if handle:
                handle.cancel()
            with self.database.transaction() as connection:
                row = connection.execute(
                    "SELECT payload FROM audit_email_events WHERE id=? AND state='pending'", (event_id,),
                ).fetchone()
                if row is None:
                    return
                event = json.loads(row[0])
                event.update(state='failed', error=type(error).__name__, finishedAt=self.now().isoformat())
                connection.execute(
                    'UPDATE audit_email_events SET state=?,payload=? WHERE id=?',
                    (event['state'], json.dumps(event, ensure_ascii=False), event['id']),
                )
            self._log(event, 'finished', state='failed', error_code=type(error).__name__)

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
        with self.database.connect() as connection:
            schedules = connection.execute(
                'SELECT payload FROM audit_email_schedules WHERE enabled=1',
            ).fetchall()
        for row in schedules:
            schedule = json.loads(row[0])
            schedule['nextRunAt'] = self._next_occurrence(schedule).isoformat()
            with self.database.transaction() as connection:
                connection.execute(
                    'UPDATE audit_email_schedules SET payload=? WHERE id=?',
                    (json.dumps(schedule, ensure_ascii=False), schedule['id']),
                )
            self._arm_schedule(schedule)

    def fire(self, event_id):
        handle = self.handles.pop(event_id, None)
        if handle:
            handle.cancel()
        with self.database.transaction() as connection:
            row = connection.execute("SELECT payload FROM audit_email_events WHERE id=? AND state='pending'", (event_id,)).fetchone()
            if row is None:
                return
            event = json.loads(row[0])
            remaining = (datetime.fromisoformat(event['dueAt']) - self.now()).total_seconds()
            if remaining > _TIMER_EARLY_TOLERANCE_SECONDS:
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
        self._update_schedule_result(event, run_id=run['id'], state='running')

    def delivery(self, event, run):
        event['deliveries'] = run['deliveries']
        self._save(event)

    def finish(self, event, result):
        event.update(state=result['state'], deliveries=result.get('deliveries', {}),
                     finishedAt=self.now().isoformat())
        if result.get('error'):
            event['error'] = result['error']
        self._save(event)
        self._update_schedule_result(event, run_id=event.get('runId'), state=event['state'])
        self._log(event, 'finished', state=event['state'], error_code=event.get('error', ''),
                  duration_ms=round((self.now() - datetime.fromisoformat(event['startedAt'])).total_seconds() * 1000, 3))

    def _update_schedule_result(self, event, *, run_id, state):
        schedule_id = event.get('scheduleId')
        if not schedule_id:
            return
        with self.database.transaction() as connection:
            row = connection.execute(
                'SELECT payload FROM audit_email_schedules WHERE id=?', (schedule_id,),
            ).fetchone()
            if row is None:
                return
            schedule = json.loads(row[0])
            schedule.update(lastRunId=run_id, lastState=state)
            connection.execute(
                'UPDATE audit_email_schedules SET payload=? WHERE id=?',
                (json.dumps(schedule, ensure_ascii=False), schedule_id),
            )

    def close(self):
        for handle in self.handles.values():
            handle.cancel()
        self.handles.clear()
