from __future__ import annotations

import json
import time
from uuid import uuid4

from .issue_repository import JiraIssueRepository
from .schema import initialize_jira_schema


class JiraAnalyticsRepository:
    def __init__(self, database, *, now=time.time):
        self.database, self._now = database, now
        initialize_jira_schema(database)
        self.issues = JiraIssueRepository(database)

    @staticmethod
    def _scope(session_hash, card_key):
        return f"{session_hash}:card:{card_key}" if card_key else str(session_hash)

    def publish_conditions(self, session_hash, account, conditions, *, expires_at):
        with self.database.transaction() as connection:
            connection.execute("""INSERT INTO jira_analytics_queries
                (session_hash,account,expires_at,user_conditions_json) VALUES(?,?,?,?)
                ON CONFLICT(session_hash) DO UPDATE SET account=excluded.account,
                expires_at=excluded.expires_at,user_conditions_json=excluded.user_conditions_json""",
                (str(session_hash), str(account).casefold(), float(expires_at),
                 json.dumps(conditions, ensure_ascii=False, sort_keys=True)))

    def published_conditions(self, session_hash, account):
        with self.database.connect() as connection:
            row = connection.execute("""SELECT user_conditions_json FROM jira_analytics_queries
                WHERE session_hash=? AND account=? AND expires_at>?""",
                (str(session_hash), str(account).casefold(), self._now())).fetchone()
        return json.loads(row[0]) if row and row[0] is not None else None

    def begin(self, session_hash, account, jql, basic, source_filter_id, *, expires_at, user_jql=None, card_key=""):
        snapshot_id = uuid4().hex
        now = self._now()
        session_hash = self._scope(session_hash, card_key)
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_analytics_queries WHERE expires_at<=?", (now,))
            connection.execute("""INSERT INTO jira_analytics_queries
                (session_hash,account,pending_snapshot_id,expires_at,card_key) VALUES(?,?,?,?,?)
                ON CONFLICT(session_hash) DO UPDATE SET account=excluded.account,
                pending_snapshot_id=excluded.pending_snapshot_id,task_id='',expires_at=excluded.expires_at""",
                (str(session_hash), str(account).casefold(), snapshot_id, float(expires_at), str(card_key)))
            connection.execute("""INSERT INTO jira_analytics_snapshots
                (snapshot_id,session_hash,account,jql,basic_json,source_filter_id,state,created_at,user_jql,card_key)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", (snapshot_id, str(session_hash), str(account).casefold(),
                str(jql), json.dumps(basic or {}, ensure_ascii=False, sort_keys=True),
                str(source_filter_id or ""), "pending", now, user_jql, str(card_key)))
        return snapshot_id

    def set_task(self, snapshot_id, task_id):
        with self.database.transaction() as connection:
            connection.execute("""UPDATE jira_analytics_queries SET task_id=?
                WHERE pending_snapshot_id=?""", (str(task_id), str(snapshot_id)))

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
        session_hash = self._scope(session_hash, card_key)
        with self.database.connect() as connection:
            row = connection.execute("""SELECT active_snapshot_id,pending_snapshot_id,task_id
                FROM jira_analytics_queries WHERE session_hash=? AND account=? AND expires_at>?""",
                (str(session_hash), str(account).casefold(), self._now())).fetchone()
            if row is None:
                return {"activeSnapshotId": "", "pendingSnapshotId": "", "taskId": "", "activeJql": "",
                        "userJql": None, "latestState": "", "error": ""}
            active_jql = ""
            user_jql = None
            if row[0]:
                value = connection.execute("SELECT jql,user_jql FROM jira_analytics_snapshots WHERE snapshot_id=?", (row[0],)).fetchone()
                active_jql = value[0] if value else ""
                user_jql = value[1] if value else None
            latest = connection.execute("""SELECT state,error FROM jira_analytics_snapshots
                WHERE session_hash=? AND account=? ORDER BY created_at DESC,rowid DESC LIMIT 1""",
                (str(session_hash), str(account).casefold())).fetchone()
            return {"activeSnapshotId": row[0], "pendingSnapshotId": row[1], "taskId": row[2], "activeJql": active_jql,
                    "userJql": user_jql, "latestState": latest[0] if latest else "", "error": latest[1] if latest else ""}

    def issue_keys(self, session_hash, account, *, card_key=""):
        session_hash = self._scope(session_hash, card_key)
        with self.database.connect() as connection:
            return [row[0] for row in connection.execute("""SELECT i.issue_key
                FROM jira_analytics_queries q
                JOIN jira_analytics_snapshot_issues m ON m.snapshot_id=q.active_snapshot_id
                JOIN jira_issues i ON i.issue_id=m.issue_id
                WHERE q.session_hash=? AND q.account=? AND q.expires_at>?
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
        """Read only the authenticated session's active SQLite collection."""
        session_hash = self._scope(session_hash, card_key)
        with self.database.connect() as connection:
            rows = connection.execute("""SELECT i.project_key,i.issue_type_name,
                i.reporter_account,i.reporter_identity,i.reporter_display_name,
                i.resolution_name,i.priority_name
                FROM jira_analytics_queries q
                JOIN jira_analytics_snapshot_issues m ON m.snapshot_id=q.active_snapshot_id
                JOIN jira_issues i ON i.issue_id=m.issue_id
                WHERE q.session_hash=? AND q.account=? AND q.expires_at>?
                ORDER BY m.ordinal""", (str(session_hash), str(account).casefold(), self._now())).fetchall()
        return [{"fields": {"project": {"key": row[0]}, "issuetype": {"name": row[1]},
                 "reporter": {"name": row[2] or row[3], "displayName": row[4]} if row[2] or row[3] else None,
                 "resolution": {"name": row[5]}, "priority": {"name": row[6]}}} for row in rows]

    def delete_account(self, account):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_analytics_queries WHERE account=?", (str(account).casefold(),))

    def cleanup(self):
        with self.database.transaction() as connection:
            return connection.execute("DELETE FROM jira_analytics_queries WHERE expires_at<=?", (self._now(),)).rowcount
