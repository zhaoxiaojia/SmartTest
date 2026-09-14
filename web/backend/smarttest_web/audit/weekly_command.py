"""Fixed Windows weekly-audit task and unattended command owner."""

from datetime import datetime, timedelta
from pathlib import Path
import os
import subprocess
import time
from zoneinfo import ZoneInfo

from core.weekly_audit import fixed_weekly_audit_scope
from core.logging import smart_log

TASK_NAME = 'SmartTest.WeeklyAuditEmail'
TASK_ACCOUNT = 'ping.xiong'
TASK_WEEKDAY = 'MON'
TASK_TIME = '15:00'
_SHANGHAI = ZoneInfo('Asia/Shanghai')


def weekly_task_definition(python_executable, script):
    executable = Path(python_executable).resolve()
    script_path = Path(script).resolve()
    return {'name': TASK_NAME, 'weekday': TASK_WEEKDAY, 'time': TASK_TIME,
            'command': f'"{executable}" "{script_path}"'}


def install_windows_task(python_executable, script, *, run=subprocess.run):
    definition = weekly_task_definition(python_executable, script)
    run(['schtasks.exe', '/Create', '/F', '/TN', definition['name'], '/SC', 'WEEKLY',
         '/D', definition['weekday'], '/ST', definition['time'], '/TR', definition['command']], check=True)


class ScheduledAuditRunner:
    def __init__(self, history, launch, account=TASK_ACCOUNT):
        self.history = history
        self.launch = launch
        self.account = account

    def run(self, trigger_at):
        trigger = (trigger_at.replace(tzinfo=_SHANGHAI) if trigger_at.tzinfo is None
                   else trigger_at.astimezone(_SHANGHAI))
        occurrence = (trigger.date() - timedelta(days=trigger.weekday())).isoformat()
        if not self.history.claim_scheduled_occurrence(self.account, occurrence):
            smart_log('Weekly audit task occurrence already claimed', platform='web', domain='audit',
                      source='weekly_audit_command', emit_runtime_event=False,
                      extra={'account': self.account, 'occurrence': occurrence})
            return 0
        state = self.launch(trigger, 'scheduled')
        smart_log('Weekly audit task finished', platform='web', domain='audit',
                  source='weekly_audit_command', level='info' if state == 'completed' else 'error',
                  emit_runtime_event=False,
                  extra={'account': self.account, 'occurrence': occurrence, 'state': state})
        return 0 if state == 'completed' else 1


def run_product_weekly_audit(trigger_at=None):
    from smarttest_web.audit.confluence_adapter import WebConfluenceAuditOwner
    from smarttest_web.audit.email_history import AuditEmailHistory
    from smarttest_web.audit.email_job import AuditEmailJob
    from smarttest_web.audit.jira_adapter import WebJiraAuditOwner
    from smarttest_web.database import WebDatabase
    from smarttest_web.project_facts_api import ProjectFactsWebOwner
    from smarttest_web.session import PersistentSessionStore

    sessions = PersistentSessionStore()
    database = WebDatabase(sessions.path)
    history = AuditEmailHistory(database)

    def launch(trigger, source):
        token = sessions.create_from_saved(TASK_ACCOUNT)
        job = AuditEmailJob(history)
        try:
            value = sessions.get(token)
            base = os.getenv('SMARTTEST_CONFLUENCE_BASE_URL', 'https://confluence.amlogic.com')
            access = sessions.resource_access(token, f"confluence:{base.rstrip('/').lower()}", database)
            result = job.trigger(
                value.username, fixed_weekly_audit_scope(trigger), access, value.password,
                value.expires_at, ProjectFactsWebOwner(), WebJiraAuditOwner.from_credentials,
                WebConfluenceAuditOwner.from_credentials,
                trigger_source=source,
            )
            while result['state'] in {'queued', 'running'}:
                time.sleep(0.5)
                result = history.get(value.username, result['id'])
            return result['state']
        finally:
            job.close()
            sessions.delete(token)

    return ScheduledAuditRunner(history, launch).run(trigger_at or datetime.now(_SHANGHAI))
