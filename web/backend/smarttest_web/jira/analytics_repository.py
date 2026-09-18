from __future__ import annotations

import json
import time
from datetime import datetime
from uuid import uuid4

from .issue_repository import JiraIssueRepository
from .schema import initialize_jira_schema


class JiraAnalyticsRepository:
    def __init__(self, database, *, now=time.time):
        self.database, self._now = database, now
        initialize_jira_schema(database)
        self.issues = JiraIssueRepository(database)

    @staticmethod
    def _scope(session_hash, card_key, account):
        return f"account:{str(account).casefold()}:card:{card_key}" if card_key else str(session_hash)

    def publish_conditions(self, session_hash, account, conditions, *, expires_at):
        session_hash = self._scope(session_hash, "conditions", account)
        with self.database.transaction() as connection:
            connection.execute("""INSERT INTO jira_analytics_queries
                (session_hash,account,expires_at,user_conditions_json) VALUES(?,?,?,?)
                ON CONFLICT(session_hash) DO UPDATE SET account=excluded.account,
                expires_at=excluded.expires_at,user_conditions_json=excluded.user_conditions_json""",
                (str(session_hash), str(account).casefold(), float(expires_at),
                 json.dumps(conditions, ensure_ascii=False, sort_keys=True)))

    def published_conditions(self, session_hash, account):
        session_hash = self._scope(session_hash, "conditions", account)
        with self.database.connect() as connection:
            row = connection.execute("""SELECT user_conditions_json FROM jira_analytics_queries
                WHERE session_hash=? AND account=?""",
                (str(session_hash), str(account).casefold())).fetchone()
        return json.loads(row[0]) if row and row[0] is not None else None

    def begin(self, session_hash, account, jql, basic, source_filter_id, *, expires_at, user_jql=None, card_key="", roster_fingerprint=""):
        snapshot_id = uuid4().hex
        now = self._now()
        task_session_hash = str(session_hash)
        session_hash = self._scope(session_hash, card_key, account)
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_analytics_queries WHERE expires_at<=? AND card_key='' AND user_conditions_json IS NULL", (now,))
            connection.execute("""INSERT INTO jira_analytics_queries
                (session_hash,account,pending_snapshot_id,expires_at,card_key,task_session_hash) VALUES(?,?,?,?,?,?)
                ON CONFLICT(session_hash) DO UPDATE SET account=excluded.account,
                pending_snapshot_id=excluded.pending_snapshot_id,task_id='',expires_at=excluded.expires_at,
                task_session_hash=excluded.task_session_hash""",
                (str(session_hash), str(account).casefold(), snapshot_id, float(expires_at), str(card_key), task_session_hash))
            connection.execute("""INSERT INTO jira_analytics_snapshots
                (snapshot_id,session_hash,account,jql,basic_json,source_filter_id,state,created_at,user_jql,card_key,roster_fingerprint)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (snapshot_id, str(session_hash), str(account).casefold(),
                str(jql), json.dumps(basic or {}, ensure_ascii=False, sort_keys=True),
                str(source_filter_id or ""), "pending", now, user_jql, str(card_key), str(roster_fingerprint)))
        return snapshot_id

    def set_task(self, snapshot_id, task_id, *, session_hash=None):
        with self.database.transaction() as connection:
            connection.execute("""UPDATE jira_analytics_queries SET task_id=?,task_session_hash=COALESCE(?,task_session_hash)
                WHERE pending_snapshot_id=?""", (str(task_id), session_hash, str(snapshot_id)))

    def write_batch(self, snapshot_id, issues):
        rows = list(issues)
        self.issues.save_core(rows)
        with self.database.transaction() as connection:
            offset = int(connection.execute(
                "SELECT count(*) FROM jira_analytics_snapshot_issues WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()[0])
            for index, issue in enumerate(rows, offset):
                connection.execute("""INSERT OR IGNORE INTO jira_analytics_snapshot_issues
                    (snapshot_id,issue_id,ordinal) VALUES(?,?,?)""",
                    (snapshot_id, issue.identity.id, index))

    def activate(self, snapshot_id):
        with self.database.transaction() as connection:
            cursor = connection.execute("""UPDATE jira_analytics_queries
                SET active_snapshot_id=?,pending_snapshot_id='',task_id=''
                WHERE pending_snapshot_id=?""", (snapshot_id, snapshot_id))
            if not cursor.rowcount:
                connection.execute("UPDATE jira_analytics_snapshots SET state='stale' WHERE snapshot_id=?", (snapshot_id,))
                return False
            connection.execute("UPDATE jira_analytics_snapshots SET state='active' WHERE snapshot_id=?", (snapshot_id,))
            return True

    def finish(self, snapshot_id, state, error=""):
        with self.database.transaction() as connection:
            connection.execute("UPDATE jira_analytics_snapshots SET state=?,error=? WHERE snapshot_id=?",
                               (str(state), str(error), str(snapshot_id)))
            connection.execute("""UPDATE jira_analytics_queries SET pending_snapshot_id='',task_id=''
                WHERE pending_snapshot_id=?""", (str(snapshot_id),))

    def state(self, session_hash, account, *, card_key=""):
        task_session_hash = str(session_hash)
        session_hash = self._scope(session_hash, card_key, account)
        with self.database.connect() as connection:
            row = connection.execute("""SELECT active_snapshot_id,pending_snapshot_id,task_id,task_session_hash
                FROM jira_analytics_queries WHERE session_hash=? AND account=? AND (card_key!='' OR expires_at>?)""",
                (str(session_hash), str(account).casefold(), self._now())).fetchone()
            if row is None:
                return {"activeSnapshotId": "", "pendingSnapshotId": "", "taskId": "", "activeJql": "",
                        "userJql": None, "latestState": "", "error": "", "rosterFingerprint": ""}
            active_jql = ""
            user_jql = None
            fingerprint = ""
            if row[0]:
                value = connection.execute("SELECT jql,user_jql,roster_fingerprint FROM jira_analytics_snapshots WHERE snapshot_id=?", (row[0],)).fetchone()
                active_jql = value[0] if value else ""
                user_jql = value[1] if value else None
                fingerprint = value[2] if value else ""
            latest = connection.execute("""SELECT state,error FROM jira_analytics_snapshots
                WHERE session_hash=? AND account=? ORDER BY created_at DESC,rowid DESC LIMIT 1""",
                (str(session_hash), str(account).casefold())).fetchone()
            return {"activeSnapshotId": row[0], "pendingSnapshotId": row[1],
                    "taskId": row[2] if not card_key or row[3] == task_session_hash else "", "activeJql": active_jql,
                    "userJql": user_jql, "latestState": latest[0] if latest else "", "error": latest[1] if latest else "",
                    "rosterFingerprint": fingerprint}

    def issue_keys(self, session_hash, account, *, card_key=""):
        session_hash = self._scope(session_hash, card_key, account)
        with self.database.connect() as connection:
            return [row[0] for row in connection.execute("""SELECT i.issue_key
                FROM jira_analytics_queries q
                JOIN jira_analytics_snapshot_issues m ON m.snapshot_id=q.active_snapshot_id
                JOIN jira_issues i ON i.issue_id=m.issue_id
                WHERE q.session_hash=? AND q.account=? AND (q.card_key!='' OR q.expires_at>?)
                ORDER BY m.ordinal""", (str(session_hash), str(account).casefold(), self._now()))]

    def delete_session(self, session_hash):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_analytics_queries WHERE session_hash=? OR session_hash LIKE ?",
                               (str(session_hash), f"{session_hash}:card:%"))

    def interrupt_pending(self):
        """Called before serving requests: runtime tasks do not survive restart."""
        with self.database.transaction() as connection:
            connection.execute("""UPDATE jira_analytics_snapshots SET state='failed',error='query_interrupted'
                WHERE snapshot_id IN (SELECT pending_snapshot_id FROM jira_analytics_queries
                WHERE pending_snapshot_id!='')""")
            connection.execute("""UPDATE jira_analytics_queries SET pending_snapshot_id='',task_id=''
                WHERE pending_snapshot_id!=''""")

    def statistics_issues(self, session_hash, account, *, card_key=""):
        """Read the authenticated account card or session's active SQLite collection."""
        session_hash = self._scope(session_hash, card_key, account)
        with self.database.connect() as connection:
            rows = connection.execute("""SELECT i.project_key,i.issue_type_name,
                i.reporter_account,i.reporter_identity,i.reporter_display_name,
                i.resolution_name,i.priority_name
                FROM jira_analytics_queries q
                JOIN jira_analytics_snapshot_issues m ON m.snapshot_id=q.active_snapshot_id
                JOIN jira_issues i ON i.issue_id=m.issue_id
                WHERE q.session_hash=? AND q.account=? AND (q.card_key!='' OR q.expires_at>?)
                ORDER BY m.ordinal""", (str(session_hash), str(account).casefold(), self._now())).fetchall()
        return [{"fields": {"project": {"key": row[0]}, "issuetype": {"name": row[1]},
                 "reporter": {"name": row[2] or row[3], "displayName": row[4]} if row[2] or row[3] else None,
                 "resolution": {"name": row[5]}, "priority": {"name": row[6]}}} for row in rows]

    def statistics_summary(self, session_hash, account, *, card_key):
        """Legacy count-only summaries are never authoritative resource collections."""
        with self.database.connect() as connection:
            row = connection.execute("""SELECT s.statistics_json FROM jira_analytics_queries q
                JOIN jira_analytics_snapshots s ON s.snapshot_id=q.active_snapshot_id
                WHERE q.session_hash=? AND q.account=?""",
                (self._scope(session_hash, card_key, account), str(account).casefold())).fetchone()
        return json.loads(row[0]) if row and row[0] else None

    def migrate_self_test(self, roster):
        """Preserve valid legacy data in this owner without querying or inventing IDs."""
        from core.jira.services.filter_service import compose_jql
        from core.jira.services.team_bug_service import self_test_jira_conditions
        if not roster.accounts:
            return
        fixed = self_test_jira_conditions(roster.accounts)
        year = datetime.fromtimestamp(self._now()).year
        with self.database.transaction() as connection:
            candidates = connection.execute("""SELECT q.account,q.session_hash,s.snapshot_id,s.jql,s.user_jql,
                s.source_filter_id,s.created_at,s.roster_fingerprint
                FROM jira_analytics_queries q JOIN jira_analytics_snapshots s ON s.snapshot_id=q.active_snapshot_id
                WHERE q.card_key='self-test' ORDER BY s.created_at DESC""").fetchall()
            migrated = set()
            for account, old_scope, snapshot_id, jql, user_jql, source, created, fingerprint in candidates:
                account = str(account).casefold()
                if account in migrated or user_jql is None or jql != compose_jql(user_jql, fixed):
                    continue
                if fingerprint and fingerprint != roster.fingerprint:
                    continue
                if datetime.fromtimestamp(created).year != year:
                    continue
                scope = self._scope('', 'self-test', account)
                connection.execute("""INSERT INTO jira_analytics_queries
                    (session_hash,account,active_snapshot_id,expires_at,card_key) VALUES(?,?,?,0,'self-test')
                    ON CONFLICT(session_hash) DO UPDATE SET active_snapshot_id=excluded.active_snapshot_id""",
                    (scope, account, snapshot_id))
                connection.execute("""UPDATE jira_analytics_snapshots SET session_hash=?,roster_fingerprint=?
                    WHERE snapshot_id=?""", (scope, roster.fingerprint, snapshot_id))
                conditions_scope = self._scope('', 'conditions', account)
                old_session = old_scope.rsplit(':card:', 1)[0]
                published = connection.execute("""SELECT user_conditions_json FROM jira_analytics_queries
                    WHERE session_hash=? AND account=?""", (old_session, account)).fetchone()
                conditions = published[0] if published and published[0] else json.dumps({
                    'mode': 'advanced', 'jql': user_jql, 'userJql': user_jql, 'sourceFilterId': source})
                connection.execute("""INSERT INTO jira_analytics_queries
                    (session_hash,account,expires_at,user_conditions_json) VALUES(?,?,0,?)
                    ON CONFLICT(session_hash) DO NOTHING""", (conditions_scope, account, conditions))
                migrated.add(account)

            legacy = connection.execute("""SELECT a.account,s.snapshot_id,s.team_total,s.created_at,
                s.effective_jql,s.unmapped_count,s.unassigned_count FROM jira_team_bug_accounts a
                JOIN jira_team_bug_snapshots s ON s.snapshot_id=a.active_snapshot_id
                WHERE s.roster_fingerprint=? AND s.effective_jql=?""", (roster.fingerprint, fixed)).fetchall()
            for account, legacy_id, total, created, jql, unmapped, missing in legacy:
                account = str(account).casefold()
                snapshot_id = f'legacy-dashboard:{legacy_id}'
                if account in migrated:
                    connection.execute("UPDATE jira_team_bug_accounts SET active_snapshot_id='' WHERE account=?", (account,))
                    continue
                if connection.execute(
                        'SELECT 1 FROM jira_analytics_snapshots WHERE snapshot_id=?', (snapshot_id,)).fetchone():
                    continue
                scope = self._scope('', 'self-test', account)
                lines = connection.execute('SELECT product_line FROM jira_team_bug_lines WHERE snapshot_id=? ORDER BY ordinal',
                                           (legacy_id,)).fetchall()
                rows = connection.execute("""SELECT product_line,identity,display_name,bug_count,resolved_count,p0_count,invalid_count
                    FROM jira_team_bug_rows WHERE snapshot_id=? ORDER BY product_line,ordinal""", (legacy_id,)).fetchall()
                by_line = {}
                for line, *values in rows:
                    by_line.setdefault(line, []).append(dict(zip(
                        ('identity', 'displayName', 'bugCount', 'resolvedCount', 'p0Count', 'invalidCount'), values)))
                summary = {'teamTotal': total, 'unmappedCount': unmapped, 'unassignedCount': missing,
                           'productLines': [{'id': line[0], 'label': line[0], 'people': by_line.get(line[0], [])} for line in lines]}
                connection.execute("""INSERT INTO jira_analytics_queries
                    (session_hash,account,active_snapshot_id,expires_at,card_key) VALUES(?,?,?,0,'self-test')
                    ON CONFLICT(session_hash) DO UPDATE SET active_snapshot_id=excluded.active_snapshot_id""", (scope, account, snapshot_id))
                connection.execute("""INSERT INTO jira_analytics_snapshots
                    (snapshot_id,session_hash,account,jql,basic_json,state,created_at,user_jql,card_key,statistics_json,roster_fingerprint)
                    VALUES(?,?,?,?,'{}','active',?,'','self-test',?,?)""",
                    (snapshot_id, scope, account, jql, created, json.dumps(summary), roster.fingerprint))
                connection.execute("UPDATE jira_team_bug_accounts SET active_snapshot_id='' WHERE account=?", (account,))
                connection.execute("""INSERT INTO jira_analytics_queries
                    (session_hash,account,expires_at,user_conditions_json) VALUES(?,?,0,?)
                    ON CONFLICT(session_hash) DO NOTHING""",
                    (self._scope('', 'conditions', account), account, json.dumps({'mode': 'basic', 'basic': {}, 'userJql': ''})))

    def delete_account(self, account):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_analytics_queries WHERE account=?", (str(account).casefold(),))

    def cleanup(self):
        with self.database.transaction() as connection:
            return connection.execute("DELETE FROM jira_analytics_queries WHERE expires_at<=? AND card_key='' AND user_conditions_json IS NULL", (self._now(),)).rowcount
