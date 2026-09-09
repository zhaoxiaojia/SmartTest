"""Shared audit/report orchestration for manual runs and one-time events."""

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter

from core.confluence.audit.models import AuditPeriod
from core.email.audit_report import summarize_audit
from core.logging import smart_log

from ..task_manager import WEB_TASKS
class AuditEmailJob:
    def __init__(self, history):
        self.history = history
        self.root = history.database.path.parent / 'audit-email-reports'
        self._tasks = set()
        self._lock = Lock()

    def trigger(self, account, filter_scope, access, password, expires_at, facts, jira_factory, confluence_factory,
                *, event_id=None, trigger_source=None, on_created=None, on_delivery=None, on_finished=None):
        scope = filter_scope
        period = AuditPeriod(datetime.fromisoformat(scope['startDate']), datetime.fromisoformat(scope['endDate']))
        result = self.history.create(account, scope)
        if event_id:
            result.update(source=trigger_source or 'one_time', eventId=event_id, deliveries={})
            self.history.save(account, result)
        if on_created:
            on_created(result)

        def execute(token, progress):
            try:
                self._run(account, result, access, password, expires_at, facts, jira_factory,
                          confluence_factory, token, period, on_delivery)
            except Exception as error:
                result.update(state='failed', error=type(error).__name__)
                self.history.save(account, result)
            finally:
                if on_finished:
                    on_finished(result)

        future = WEB_TASKS.submit_coordinator('weekly-audit-email', execute)
        with self._lock:
            self._tasks.add(future)
        return self.history.get(account, result['id'])

    def close(self):
        with self._lock:
            tasks = tuple(self._tasks)
        for future in tasks:
            WEB_TASKS.cancel(WEB_TASKS.task_id(future))
        for future in tasks:
            WEB_TASKS.join(WEB_TASKS.task_id(future))
        with self._lock:
            self._tasks.difference_update(tasks)

    def _run(self, account, result, access, password, expires_at, facts, jira_factory, confluence_factory, token, period, on_delivery):
        started = perf_counter()
        result['state'] = 'running'
        scope = result['scope']

        def record(kind, stage, **fields):
            entry = {'run_id': result['id'], 'event_id': result.get('eventId', ''), 'trigger_source': result['source'], 'report_type': kind,
                     'stage': stage, **fields}
            result['evidence'] += '\n' + ' '.join(f'{key}={value}' for key, value in entry.items())
            self.history.save(account, result)
            smart_log('Weekly audit email ' + ' '.join(f'{key}={value}' for key, value in entry.items()),
                      platform='web', domain='audit', source='audit_email',
                      emit_runtime_event=False, extra=entry)

        record('both', 'started', start_date=scope['startDate'], end_date=scope['endDate'])
        for kind in ('jira', 'confluence'):
            stage = 'resolving_scope'
            try:
                token.raise_if_cancelled()
                access.require_active()
                result['reports'][kind]['state'] = 'running'
                record(kind, stage)
                if kind == 'jira':
                    owner = jira_factory(account, password)
                    resolved = owner.resolve(scope['jira']['jql'])
                    scope['jiraTemplate'] = scope['jira']['jql']
                    scope['jiraInput'] = resolved.jql
                    record(kind, 'scope_resolved', jql=resolved.jql)
                else:
                    owner = confluence_factory(access, password)
                    resolved = owner.resolve({**scope, **scope['confluence']})
                    record(kind, 'scope_resolved', project_count=len(getattr(resolved, 'projects', ())))
                stage = 'auditing'
                report = owner.run(resolved, token, lambda step, done=0, total=0: record(kind, step, processed=done, total=total))
                token.raise_if_cancelled()
                access.require_active()
                stage = 'exporting'
                directory = self.root / result['id'] / kind
                directory.mkdir(parents=True, exist_ok=True)
                paths = ([owner.export(report, directory / f'Jira_Weekly_Review_{result["id"]}.xlsx')]
                         if kind == 'jira' else owner.export(report, directory))
                attachments = [Path(path).name for path in paths]
                token.raise_if_cancelled()
                access.require_active()
                summary = summarize_audit(kind, report)
                self.history.complete_report(account, result, kind, summary, attachments)
                record(kind, 'report_saved', attachments=attachments, duration_ms=round((perf_counter() - started) * 1000, 3))
            except Exception as error:
                # External audit/export boundary: retain the other report and safe error evidence.
                code = str(error) if str(error) in {'invalid_input', 'permission_denied', 'reauthentication_required',
                       'remote_unavailable', 'cancelled'} else type(error).__name__
                result['reports'][kind] = {'state': 'failed', 'html': '', 'error': code, 'stage': stage, 'attachments': []}
                result['summary'].pop(kind, None)
                record(kind, 'failed', error_code=code, failure_stage=stage)
        completed = sum(report['state'] == 'completed' for report in result['reports'].values())
        result['state'] = 'completed' if completed == 2 else 'partial' if completed else 'failed'
        if result.get('eventId'):
            result['state'] = 'running'
            from core.email.outlook import send_email
            for kind, report in result['reports'].items():
                delivery = {'state': 'skipped', 'error': 'report_unavailable'}
                if report['state'] == 'completed':
                    delivery = {'state': 'sending', 'startedAt': datetime.now(timezone.utc).isoformat(),
                                'recipients': ['chao.li@amlogic.com', 'ping.xiong@amlogic.com']}
                    result['deliveries'][kind] = delivery
                    record(kind, 'smtp_started')
                    if on_delivery:
                        on_delivery(result)
                    try:
                        token.raise_if_cancelled()
                        send_email(subject=report['subject'], body=report['html'], body_format='html', template=None,
                                   to=delivery['recipients'],
                                   attachments=[self.root / result['id'] / kind / name for name in report['attachments']])
                        delivery['state'] = 'accepted'
                    except Exception as error:
                        delivery.update(state='failed', error=type(error).__name__)
                    delivery['finishedAt'] = datetime.now(timezone.utc).isoformat()
                result['deliveries'][kind] = delivery
                record(kind, f"smtp_{delivery['state']}", error_code=delivery.get('error', ''))
                if on_delivery:
                    on_delivery(result)
            accepted = sum(item['state'] == 'accepted' for item in result['deliveries'].values())
            result['state'] = 'completed' if accepted == 2 else 'partial' if accepted else 'failed'
        record('both', 'finished', state=result['state'], email='recorded' if result.get('eventId') else 'not_sent',
               duration_ms=round((perf_counter() - started) * 1000, 3))
