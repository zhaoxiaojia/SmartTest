"""Persistent audit email history, separate from disposable query caches."""

import json
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.email.audit_report import render_history_report


class AuditEmailHistory:
    def __init__(self, database):
        self.database = database
        with database.transaction() as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS audit_email_runs (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE, account TEXT NOT NULL,
                label TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL
            )''')
            summaries = []
            for label, total, passed, rate, confluence in (
                ('0807', 261, 58, '22.22%', None),
                ('0814', 151, 53, '35.10%', None),
                ('0824', 191, 79, '41.36%', {'TV': [7, 176], 'OOPL': [29, 152], 'DOPL': [0, 16], 'SDPL': [5, 152]}),
                ('0828', 118, 58, '49.15%', {'TV': [12, 168], 'OOPL': [6, 128], 'DOPL': [0, 8], 'SDPL': [11, 128]}),
            ):
                run_id = f'screenshot-{label}'
                summaries.insert(0, {'id': run_id, 'label': label,
                                     'jira': {'total': total, 'passed': passed, 'failed': total - passed, 'rate': rate},
                                     'confluence': confluence})
                reports = self._render(summaries)
                if confluence is None:
                    reports['confluence'] = render_history_report('confluence', [])
                payload = {'id': run_id, 'label': label, 'state': 'historical_seed',
                           'source': 'screenshot', 'createdAt': None,
                           'reports': reports, 'summary': summaries[0],
                           'evidence': '截图历史；无执行时间、审查明细、附件或发送记录。Jira 年份未确认；Confluence 截图年份为 2026。'}
                connection.execute(
                    'INSERT OR IGNORE INTO audit_email_runs(id,account,label,state,payload) VALUES(?,?,?,?,?)',
                    (run_id, '', label, 'historical_seed', json.dumps(payload, ensure_ascii=False)),
                )

    @staticmethod
    def _render(summaries):
        return {kind: render_history_report(kind, [
            {'id': row['id'], 'label': row['label'], 'summary': row[kind]}
            for row in summaries if row[kind] is not None
        ]) for kind in ('jira', 'confluence')}

    def list_runs(self, account, offset=0):
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id,label,state,payload FROM audit_email_runs WHERE account IN ('',?) ORDER BY sequence DESC LIMIT 4 OFFSET ?",
                (account, offset),
            ).fetchall()
            total = connection.execute(
                "SELECT COUNT(*) FROM audit_email_runs WHERE account IN ('',?)", (account,),
            ).fetchone()[0]
        return {'runs': [dict(id=row[0], label=row[1], state=row[2],
                             source=json.loads(row[3])['source']) for row in rows], 'total': total}

    def get(self, account, run_id):
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM audit_email_runs WHERE id=? AND account IN ('',?)", (run_id, account),
            ).fetchone()
        if row is None:
            raise LookupError(run_id)
        return json.loads(row[0])

    def create(self, account, scope):
        run_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        result = {'id': run_id, 'label': now, 'createdAt': now, 'source': 'manual',
                  'state': 'queued', 'scope': scope, 'summary': {}, 'evidence': '',
                  'reports': {kind: {'state': 'queued', 'html': '', 'attachments': []}
                              for kind in ('jira', 'confluence')}}
        with self.database.transaction() as connection:
            connection.execute(
                'INSERT INTO audit_email_runs(id,account,label,state,payload) VALUES(?,?,?,?,?)',
                (run_id, account, now, result['state'], json.dumps(result, ensure_ascii=False)),
            )
        return result

    def save(self, account, result):
        with self.database.transaction() as connection:
            connection.execute('UPDATE audit_email_runs SET state=?,payload=? WHERE id=? AND account=?',
                               (result['state'], json.dumps(result, ensure_ascii=False), result['id'], account))

    def complete_report(self, account, result, kind, summary, attachments):
        with self.database.transaction() as connection:
            previous = connection.execute(
                """SELECT payload FROM audit_email_runs WHERE account IN ('',?) AND sequence <
                (SELECT sequence FROM audit_email_runs WHERE id=?) ORDER BY sequence DESC""",
                (account, result['id']),
            ).fetchall()
            label = datetime.fromisoformat(result['createdAt']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
            records = [{'id': result['id'], 'label': label, 'summary': summary}]
            for row in previous:
                old = json.loads(row[0])
                if (old.get('summary', {}).get(kind) is not None
                        and old['reports'][kind]['state'] in {'completed', 'historical_preview'}):
                    old_label = old['label']
                    if old.get('createdAt'):
                        old_label = datetime.fromisoformat(old['createdAt']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
                    records.append({'id': old['id'], 'label': old_label, 'summary': old['summary'][kind]})
                if len(records) == 4:
                    break
            rendered = render_history_report(kind, records, current=True)
            result['summary'][kind] = summary
            result['reports'][kind] = {**rendered, 'attachments': attachments}
            self.save(account, result)
